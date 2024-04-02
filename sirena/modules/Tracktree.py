# -*- coding: utf-8 -*-
#
# Copyright (c) 2007  François Ingelrest (Francois.Ingelrest@gmail.com)
# Copyright (c) 2010  Jendrik Seipp (jendrikseipp@web.de)
# Copyright (C) 2024 Santelmo Technologies <santelmotechnologies@gmail.com>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Library General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301 USA

from gettext import gettext as _
import logging
import os
import traceback

from gi.repository import Gdk, GdkPixbuf
from gi.repository import GObject
from gi.repository import Gtk

from sirena import media, modules, tools
from sirena.gui import fileChooser
from sirena.tools import consts, icons, prefs, pickleLoad, pickleSave, log
from sirena.gui.widgets import TrackTreeView

MOD_INFO = ('Tracktree', 'Tracktree', '', [], True, False)

# The format of a row in the treeview
(
    ROW_ICO,    # Item icon
    ROW_NAME,   # Item name
    ROW_TRK,    # The track object
) = list(range(3))


SAVE_INTERVAL = 600

# Internal d'n'd (reordering)
DND_REORDERING_ID = 1024
DND_INTERNAL_TARGET = (consts.DND_INTERNAL_TARGET_NAME, Gtk.TargetFlags.SAME_WIDGET, DND_REORDERING_ID)


class Tracktree(modules.Module):
    """ This module manages the tracklist """

    def __init__(self):
        """ Constructor """
        handlers = {
            consts.MSG_CMD_NEXT: self.jumpToNext,
            consts.MSG_EVT_PAUSED: self.onPaused,
            consts.MSG_EVT_STOPPED: self.onStopped,
            consts.MSG_EVT_UNPAUSED: self.onUnPaused,
            consts.MSG_CMD_PREVIOUS: self.jumpToPrevious,
            consts.MSG_EVT_NEED_BUFFER: self.onBufferingNeeded,
            consts.MSG_EVT_APP_STARTED: self.onAppStarted,
            consts.MSG_EVT_APP_QUIT: self.onAppQuit,
            consts.MSG_CMD_TOGGLE_PAUSE: self.togglePause,
            consts.MSG_CMD_TRACKLIST_DEL: self.remove,
            consts.MSG_CMD_TRACKLIST_ADD: self.insert,
            consts.MSG_CMD_TRACKLIST_SET: self.set,
            consts.MSG_CMD_TRACKLIST_CLR: lambda: self.set(None, None),
            consts.MSG_EVT_TRACK_ENDED_OK: lambda: self.onTrackEnded(False),
            consts.MSG_EVT_TRACK_ENDED_ERROR: lambda: self.onTrackEnded(True),
            consts.MSG_CMD_FILE_EXPLORER_DRAG_BEGIN: self.onDragBegin,
            consts.MSG_EVT_SEARCH_START: self.onSearchStart,
            consts.MSG_EVT_SEARCH_RESET: self.onSearchReset,
        }

        modules.Module.__init__(self, handlers)

    def getTreeDump(self, path=None):
        """ Recursively dump the given tree starting at path (None for the root of the tree) """
        list = []

        for child in self.tree.iterChildren(path):
            row = self.tree.getRow(child)

            if self.tree.getNbChildren(child) == 0:
                grandChildren = None
            else:
                grandChildren = self.getTreeDump(child)

            name = row[ROW_NAME].replace('<b>', '').replace('</b>', '')

            list.append([(name, row[ROW_TRK]), grandChildren])

        return list

    def restoreTreeDump(self, dump, parent=None):
        """ Recursively restore the dump under the given parent (None for the root of the tree) """
        for item in dump:
            (name, track) = item[0]

            if track:
                self.tree.appendRow((icons.nullMenuIcon(), name, track), parent)
            else:
                newNode = self.tree.appendRow((icons.mediaDirMenuIcon(), name, None), parent)

                if item[1] is not None:
                    if len(item[1]) != 0:
                        # We must expand the row before adding the real children,
                        # but this works only if there is already at least one child
                        self.restoreTreeDump(item[1], newNode)

    def select_last_played_track(self):
        last_path = prefs.get(__name__, 'last-played-track', None)
        if last_path:
            parent_path = (last_path[0],)
            GObject.idle_add(self.tree.scroll_to_cell, parent_path)
            self.tree.get_selection().select_path(parent_path)

    def getTrackDir(self, root=None):
        flat = False if root else True
        name = self.tree.getLabel(root) if root else 'playtree'
        name = name.replace('<b>', '').replace('</b>', '')
        trackdir = media.TrackDir(name=name, flat=flat)

        for iter in self.tree.iter_children(root):
            track = self.tree.getTrack(iter)
            if track:
                trackdir.tracks.append(track)
            else:
                subdir = self.getTrackDir(iter)
                trackdir.subdirs.append(subdir)

        return trackdir

    def get_m3u_text(self, root=None):
        text = ''
        for iter in self.tree.iter_children(root):
            track = self.tree.getTrack(iter)
            if track:
                text += '%s\n' % track.getFilePath()
            else:
                dirname = self.tree.getLabel(iter).replace('<b>', '').replace('</b>', '')
                text += '# %s\n%s\n' % (dirname, self.get_m3u_text(iter))
        return text

    def __getNextTrackIter(self):
        """ Return the index of the next track, or -1 if there is none """
        next = None
        while True:
            next = self.tree.get_next_iter(next)
            if not next:
                return None

            # Check track
            error = self.tree.getItem(next, ROW_ICO) == icons.errorMenuIcon()
            track = self.tree.getItem(next, ROW_TRK)
            if track and not error:
                # Row is not a directory
                return next

    def __hasNextTrack(self):
        """ Return whether there is a next track """
        return self.__getNextTrackIter() is not None

    def __getPreviousTrackIter(self):
        """ Return the index of the previous track, or -1 if there is none """
        prev = None
        while True:
            prev = self.tree.get_prev_iter(prev)
            if not prev:
                return None

            # Check track
            error = self.tree.getItem(prev, ROW_ICO) == icons.errorMenuIcon()
            track = self.tree.getItem(prev, ROW_TRK)
            if track and not error:
                # Row is not a directory
                return prev

    def __hasPreviousTrack(self):
        """ Return whether there is a previous track """
        return self.__getPreviousTrackIter() is not None

    def jumpToNext(self):
        """ Jump to the next track, if any """
        where = self.__getNextTrackIter()
        if where:
            self.jumpTo(where)

    def jumpToPrevious(self):
        """ Jump to the previous track, if any """
        where = self.__getPreviousTrackIter()
        if where:
            self.jumpTo(where)

    def set_track_playing(self, iter, playing):
        if not iter:
            return
        track = self.tree.getTrack(iter)
        if not track:
            return

        for parent in self.tree.get_all_parents(iter):
            parent_label = self.tree.getLabel(parent)
            parent_label = tools.htmlUnescape(parent_label)
            is_bold = parent_label.startswith('<b>') and parent_label.endswith('</b>')
            if playing and not is_bold:
                parent_label = tools.htmlEscape(parent_label)
                self.tree.setLabel(parent, '<b>%s</b>' % parent_label)
            elif not playing and is_bold:
                parent_label = tools.htmlEscape(parent_label[3:-4])
                self.tree.setLabel(parent, parent_label)

        parent = self.tree.store.iter_parent(iter)
        parent_label = self.tree.getLabel(parent) if parent else None
        label = track.get_label(parent_label=parent_label, playing=playing)
        if playing:
            self.tree.setLabel(iter, label)
            self.tree.setItem(iter, ROW_ICO, icons.playMenuIcon())
            self.tree.expand(iter)
        else:
            self.tree.setLabel(iter, label)
            icon = self.tree.getItem(iter, ROW_ICO)
            has_error = (icon == icons.errorMenuIcon())
            is_dir = (icon == icons.mediaDirMenuIcon())
            if not is_dir and not has_error:
                self.tree.setItem(iter, ROW_ICO, icons.nullMenuIcon())

    def jumpTo(self, iter, sendPlayMsg=True, forced=True):
        """ Jump to the track located at the given iter """
        if not iter:
            return

        mark = self.tree.getMark()
        if mark:
            self.set_track_playing(mark, False)

        self.tree.setMark(iter)
        self.tree.scroll(iter)

        # Check track
        track = self.tree.getTrack(iter)
        if not track:
            # Row may be a directory
            self.jumpTo(self.__getNextTrackIter())
            return

        self.set_track_playing(iter, True)
        self.paused = False

        if sendPlayMsg:
            modules.postMsg(consts.MSG_CMD_PLAY, {'uri': track.getURI(), 'forced': forced})

        modules.postMsg(consts.MSG_EVT_NEW_TRACK, {'track': track})
        modules.postMsg(consts.MSG_EVT_TRACK_MOVED, {'hasPrevious': self.__hasPreviousTrack(), 'hasNext': self.__hasNextTrack()})

    def insert(self, tracks, target=None, drop_mode=None, playNow=True, highlight=False):
        if type(tracks) == list:
            trackdir = media.TrackDir(None, flat=True)
            trackdir.tracks = tracks
            tracks = trackdir

        children_before = self.tree.store.iter_n_children(target)

        self.tree.get_selection().unselect_all()
        self.insertDir(tracks, target, drop_mode, highlight)
        self.onListModified()

        # We only want to start playback if tracks are appended from DBus
        # or appended (not inserted) into the playlist.
        # In that case target is None. Also don't interrupt playing songs.
        logging.info(
            'playNow: %s, target: %s, self.tree.hasMark(): %s, self.paused: %s' %
            (playNow, target, self.tree.hasMark(), self.paused))
        if playNow and target is None and (not self.tree.hasMark() or self.paused):
            # If the target is None, the tracks have to be appended to the top
            # level and the first new track is the one after the original tracks
            new = self.tree.store.iter_nth_child(target, children_before)
            if new:
                # If new is None, the tracks could not be added
                self.jumpTo(new)

    def insertDir(self, trackdir, target=None, drop_mode=None, highlight=False):
        '''
        Insert a directory recursively, return the iter of the first
        added element
        '''
        model = self.tree.store
        if trackdir.flat:
            new = target
        else:
            string = trackdir.dirname.replace('_', ' ')
            string = tools.htmlEscape(string)
            source_row = (icons.mediaDirMenuIcon(), string, None)

            new = self.tree.insert(target, source_row, drop_mode)
            drop_mode = Gtk.TreeViewDropPosition.INTO_OR_AFTER
            if highlight:
                self.tree.select(new)

        dest = new
        for index, subdir in enumerate(trackdir.subdirs):
            drop = drop_mode if index == 0 else Gtk.TreeViewDropPosition.AFTER
            dest = self.insertDir(subdir, dest, drop, highlight)

        dest = new
        for index, track in enumerate(trackdir.tracks):
            drop = drop_mode if index == 0 else Gtk.TreeViewDropPosition.AFTER
            highlight &= trackdir.flat
            dest = self.insertTrack(track, dest, drop, highlight)

        if not trackdir.flat:
            # Open albums on the first layer
            if target is None or model.iter_depth(new) == 0:
                self.tree.expand(new)

        return new

    def insertTrack(self, track, target=None, drop_mode=None, highlight=False):
        '''
        Insert a new track into the tracktree under parentPath
        '''
        length = track.getLength()
        self.playtime += length

        name = track.get_label()

        row = (icons.nullMenuIcon(), name, track)
        new_iter = self.tree.insert(target, row, drop_mode)
        parent = self.tree.store.iter_parent(new_iter)
        if parent:
            # adjust track label to parent
            parent_label = self.tree.getLabel(parent)
            new_label = track.get_label(parent_label)
            self.tree.setLabel(new_iter, new_label)
        if highlight:
            self.tree.select(new_iter)
        return new_iter

    def set(self, tracks, playNow):
        """ Replace the tracklist, clear it if tracks is None """
        self.playtime = 0

        if type(tracks) == list:
            trackdir = media.TrackDir(None, flat=True)
            trackdir.tracks = tracks
            tracks = trackdir

        if self.tree.hasMark() and ((not playNow) or (tracks is None) or tracks.empty()):
            modules.postMsg(consts.MSG_CMD_STOP)

        self.tree.clear()

        if tracks is not None and not tracks.empty():
            self.insert(tracks, playNow=playNow)

        self.tree.collapse_all()

        self.onListModified()

    def export_playlist_to_m3u(self):
        """ Save the current tracklist to a playlist """
        outfile = fileChooser.save(self.window, _('Export playlist to file'), 'playlist.m3u')

        if outfile is not None:
            tools.write_file(outfile, self.get_m3u_text())

    def export_playlist_to_dir(self):
        """ Save the current tracklist to a playlist """
        outdir = fileChooser.openDirectory(self.window, _('Export playlist to directory'))

        if outdir is not None:
            trackdir = self.getTrackDir()
            trackdir.export_to_dir(outdir)

    def remove(self, iter=None):
        """ Remove the given track, or the selection if iter is None """
        hadMark = self.tree.hasMark()

        iters = [iter] if iter else list(self.tree.iterSelectedRows())

        prev_iter = self.tree.get_prev_iter_or_parent(iters[0])

        # reverse list, so that we remove children before their fathers
        for iter in reversed(iters):
            track = self.tree.getTrack(iter)
            if track:
                self.playtime -= track.getLength()
            self.tree.removeRow(iter)

        self.tree.selection.unselect_all()

        if hadMark and not self.tree.hasMark():
            modules.postMsg(consts.MSG_CMD_STOP)

        # Select new track when old selected is deleted
        if prev_iter:
            self.tree.select(prev_iter)
        else:
            first_iter = self.tree.get_first_iter()
            if first_iter:
                self.tree.select(first_iter)

        self.onListModified()

    def onShowPopupMenu(self, tree, button, time, path):
        # Keep reference after method exits.
        self.popup_menu = Gtk.Menu()

        # Remove
        remove = Gtk.MenuItem.new_with_label(_('Remove'))
        self.popup_menu.append(remove)
        if path is None:
            remove.set_sensitive(False)
        else:
            remove.connect('activate', lambda item: self.remove())

        # Clear
        clear = Gtk.MenuItem.new_with_label(_('Clear Playlist'))
        self.popup_menu.append(clear)

        # Save to m3u
        export_m3u = Gtk.MenuItem.new_with_label(_('Export playlist to file'))
        self.popup_menu.append(export_m3u)

        # Save to dir
        export_dir = Gtk.MenuItem.new_with_label(_('Export playlist to directory'))
        self.popup_menu.append(export_dir)

        if len(tree.store) == 0:
            clear.set_sensitive(False)
            export_m3u.set_sensitive(False)
            export_dir.set_sensitive(False)
        else:
            clear.connect('activate', lambda item: modules.postMsg(consts.MSG_CMD_TRACKLIST_CLR))
            export_m3u.connect('activate', lambda item: self.export_playlist_to_m3u())
            export_dir.connect('activate', lambda item: self.export_playlist_to_dir())

        self.popup_menu.show_all()
        self.popup_menu.popup(None, None, None, None, button, time)

    def togglePause(self):
        """ Start playing if not already playing """
        if len(self.tree) != 0 and not self.tree.hasMark():
            if self.tree.selection.count_selected_rows() > 0:
                model, sel_rows_list = self.tree.selection.get_selected_rows()
                first_sel_iter = self.tree.store.get_iter(sel_rows_list[0])
                self.jumpTo(first_sel_iter)
            else:
                self.jumpTo(self.tree.get_first_iter())

    def save_track_tree(self):
        # Save playing track
        if self.tree.hasMark():
            last_path = tuple(self.tree.mark.get_path())
        else:
            last_path = None
        prefs.set(__name__, 'last-played-track', last_path)

        dump = self.getTreeDump()
        logging.info('Saving playlist')
        pickleSave(self.savedPlaylist, dump)
        # tell gobject to keep saving the content in regular intervals
        return True

    # --== Message handlers ==--

    def onAppStarted(self):
        """ This is the real initialization function, called when the module has been loaded """
        wTree = tools.prefs.getWidgetsTree()
        self.playtime = 0
        self.bufferedTrack = None
        # Retrieve widgets
        self.window = wTree.get_object('win-main')

        columns = (('', [(Gtk.CellRendererPixbuf(), GdkPixbuf.Pixbuf), (Gtk.CellRendererText(), GObject.TYPE_STRING)], True),
                   (None, [(None, GObject.TYPE_PYOBJECT)], False),
                   )

        self.tree = TrackTreeView(columns, use_markup=True)

        self.tree.enableDNDReordering()
        target = Gtk.TargetEntry.new(*DND_INTERNAL_TARGET)
        targets = Gtk.TargetList.new([target])
        self.tree.setDNDSources(targets)

        wTree.get_object('scrolled-tracklist').add(self.tree)

        # GTK handlers
        self.tree.connect('exttreeview-button-pressed', self.onMouseButton)
        self.tree.connect('tracktreeview-dnd', self.onDND)
        self.tree.connect('key-press-event', self.onKeyboard)
        self.tree.get_model().connect('row-deleted', self.onRowDeleted)

        _options, args = prefs.getCmdLine()

        self.savedPlaylist = os.path.join(consts.dirCfg, 'saved-playlist')
        self.paused = False

        # Populate the playlist with the saved playlist
        dump = None
        if os.path.exists(self.savedPlaylist):
            try:
                dump = pickleLoad(self.savedPlaylist)
            except (EOFError, ImportError, IOError):
                msg = '[%s] Unable to restore playlist from %s\n\n%s'
                log.logger.error(msg % (MOD_INFO[modules.MODINFO_NAME],
                                        self.savedPlaylist, traceback.format_exc()))

        if dump:
            self.restoreTreeDump(dump)
            log.logger.info('[%s] Restored playlist' % MOD_INFO[modules.MODINFO_NAME])
            self.tree.collapse_all()
            self.select_last_played_track()
            self.onListModified()

        commands, args = tools.separate_commands_and_tracks(args)

        # Add commandline tracks to the playlist
        if args:
            log.logger.info('[%s] Filling playlist with files given on command line' % MOD_INFO[modules.MODINFO_NAME])
            tracks = media.getTracks([os.path.abspath(arg) for arg in args])
            playNow = 'stop' not in commands and 'pause' not in commands
            modules.postMsg(consts.MSG_CMD_TRACKLIST_ADD, {'tracks': tracks, 'playNow': playNow})
        elif 'play' in commands:
            modules.postMsg(consts.MSG_CMD_TOGGLE_PAUSE)

        # Automatically save the content at regular intervals
        GObject.timeout_add_seconds(SAVE_INTERVAL, self.save_track_tree)

    def onAppQuit(self):
        """ The module is going to be unloaded """
        self.save_track_tree()

    def onTrackEnded(self, withError):
        """ The current track has ended, jump to the next one if any """
        current_iter = self.tree.getMark()

        # If an error occurred with the current track, flag it as such
        if withError and current_iter:
            self.tree.setItem(current_iter, ROW_ICO, icons.errorMenuIcon())

        # Find the next 'playable' track (not already flagged)
        next = self.__getNextTrackIter()
        if next:
            send_play_msg = True
            if current_iter:
                track_name = self.tree.getTrack(current_iter).getURI()
                send_play_msg = (track_name != self.bufferedTrack)
            self.jumpTo(next, sendPlayMsg=send_play_msg, forced=False)
            self.bufferedTrack = None
            return

        self.bufferedTrack = None
        modules.postMsg(consts.MSG_CMD_STOP)

    def onBufferingNeeded(self):
        """ The current track is close to its end, so we try to buffer the next one to avoid gaps """
        where = self.__getNextTrackIter()
        if where:
            self.bufferedTrack = self.tree.getItem(where, ROW_TRK).getURI()
            modules.postMsg(consts.MSG_CMD_BUFFER, {'uri': self.bufferedTrack})

    def onStopped(self):
        """ Playback has been stopped """
        if self.tree.hasMark():
            currTrack = self.tree.getMark()
            self.set_track_playing(currTrack, False)
            self.tree.clearMark()

    def onPausedToggled(self, icon):
        """ Switch between paused and unpaused """
        if self.tree.hasMark():
            self.tree.setItem(self.tree.getMark(), ROW_ICO, icon)

    def highlight(self, query, root=None):
        """Select all rows (and their parents) that contain all parts of *query*."""
        for iter in self.tree.iter_children(root):
            track = self.tree.getTrack(iter)
            if track:
                if all(part in track.get_search_text() for part in query):
                    self.tree.select(iter)
                    # Highlight all parents as well
                    for parent in self.tree.get_all_parents(iter):
                        self.tree.select_synchronously(parent)
            else:
                dirname = self.tree.getLabel(iter).replace('<b>', '').replace('</b>', '')
                if all(part in dirname.lower() for part in query):
                    self.tree.select_synchronously(iter)
                self.highlight(query, iter)

    def onSearchStart(self, query):
        query = [part.strip().lower() for part in query.split()]
        GObject.idle_add(self.highlight, query)
        GObject.idle_add(self.tree.scroll_to_first_selection)

    def onSearchReset(self):
        self.tree.selection.unselect_all()

    def onPaused(self):
        self.paused = True
        self.onPausedToggled(icons.pauseMenuIcon())

    def onUnPaused(self):
        self.paused = False
        self.onPausedToggled(icons.playMenuIcon())

    def onDragBegin(self, paths):
        dir_selected = any(map(os.path.isdir, paths))
        self.tree.dir_selected = dir_selected
        if dir_selected:
            self.tree.collapse_all()

    # --== GTK handlers ==--

    def onMouseButton(self, tree, event, path):
        """ A mouse button has been pressed """
        if event.button == 1 and event.type == Gdk.EventType._2BUTTON_PRESS and path is not None:
            self.jumpTo(self.tree.store.get_iter(path))
        elif event.button == 3:
            self.onShowPopupMenu(tree, event.button, event.time, path)

    def onKeyboard(self, list, event):
        """ Keyboard shortcuts """
        keyname = Gdk.keyval_name(event.keyval)

        if keyname == 'Delete':
            self.remove()
        elif keyname == 'Return':
            self.jumpTo(self.tree.getFirstSelectedRow())
        elif keyname == 'space':
            modules.postMsg(consts.MSG_CMD_TOGGLE_PAUSE)
        elif keyname == 'Escape':
            modules.postMsg(consts.MSG_CMD_STOP)
        elif keyname == 'Left':
            modules.postMsg(consts.MSG_CMD_STEP, {'seconds': -5})
        elif keyname == 'Right':
            modules.postMsg(consts.MSG_CMD_STEP, {'seconds': 5})

    def onListModified(self):
        """ Some rows have been added/removed/moved """
        # Getting the trackdir takes virtually no time, so we can do it on every
        # paylist change
        tracks = self.getTrackDir()
        self.playtime = tracks.get_playtime()

        modules.postMsg(
            consts.MSG_EVT_NEW_TRACKLIST,
            {'tracks': tracks, 'playtime': self.playtime})

        if self.tree.hasMark():
            modules.postMsg(
                consts.MSG_EVT_TRACK_MOVED,
                {'hasPrevious': self.__hasPreviousTrack(), 'hasNext': self.__hasNextTrack()})

    def onDND(self, list, context, x, y, dragData, dndId, time):
        """ External Drag'n'Drop """
        import urllib.request

        uris = dragData.get_uris()

        if not uris:
            context.finish(False, False, time)
            return

        def get_path(uri):
            if uri.startswith('file://'):
                uri = uri[len('file://'):]
            return urllib.request.url2pathname(uri)

        paths = [get_path(uri) for uri in uris]
        tracks = media.getTracks(paths)

        dropInfo = list.get_dest_row_at_pos(x, y)

        # Insert the tracks, but beware of the AFTER/BEFORE mechanism used by GTK
        if dropInfo is None:
            self.insert(tracks, playNow=False, highlight=True)
        else:
            path, drop_mode = dropInfo
            iter = self.tree.store.get_iter(path)
            self.insert(tracks, iter, drop_mode, playNow=False, highlight=True)

        # We want to allow dropping tracks only when we are sure that no dir is
        # selected. This is needed for dnd from nautilus.
        self.tree.dir_selected = True

        context.finish(True, False, time)

    def onRowDeleted(self, model, path):
        """
        Internal drag and drop cannot be caught in PyGTK since the
        "rows-reordered" signal is not emitted and the work-around proposed by
        katsh doesn't work either
        (http://stackoverflow.com/questions/2831779/catch-pygtk-treeview-reorder).
        After a drag and drop operation PyGTK emits the "row-inserted" and
        afterwards "row-deleted" signals, so we catch the latter and update the
        buttons.
        """
        self.onListModified()
