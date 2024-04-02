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
import itertools
import locale
import os
from os.path import isdir, isfile
import urllib.error
import urllib.parse
import urllib.request

from gi.repository import Gdk, GdkPixbuf
from gi.repository import GObject
from gi.repository import Gtk

from sirena.gui import fileChooser, errorMsgBox
from sirena import media
from sirena import modules
from sirena import tools
from sirena.tools import consts, prefs, icons, samefile


MOD_INFO = ('File Explorer', 'File Explorer', 'Browse your file system', [], True, False)


# The format of a row in the treeview
(
    ROW_PIXBUF,    # Item icon
    ROW_NAME,      # Item name
    ROW_TYPE,      # The type of the item (e.g., directory, file)
    ROW_FULLPATH   # The full path to the item
) = list(range(4))


# The possible types for a node of the tree
(
    TYPE_DIR,   # A directory
    TYPE_FILE,  # A media file
    TYPE_NONE,   # A fake item, used to display a '+' in front of a directory when needed
    TYPE_INFO,
) = list(range(4))


class FileExplorer(modules.Module):
    """ This explorer lets the user browse the disk from a given root directory (e.g., ~/, /) """

    def __init__(self):
        """ Constructor """
        handlers = {
            consts.MSG_EVT_APP_QUIT: self.onAppQuit,
            consts.MSG_EVT_APP_STARTED: self.onAppStarted,
            consts.MSG_EVT_SEARCH_START: self.onSearchStart,
            consts.MSG_EVT_SEARCH_APPEND: self.onSearchAppend,
            consts.MSG_EVT_SEARCH_END: self.onSearchEnd,
            consts.MSG_EVT_SEARCH_RESET: self.onSearchReset,
        }

        modules.Module.__init__(self, handlers)

    def createTree(self):
        """ Create the tree used to display the file system """
        from sirena.gui import extTreeview

        columns = (
            ('', [(Gtk.CellRendererPixbuf(), GdkPixbuf.Pixbuf), (Gtk.CellRendererText(), GObject.TYPE_STRING)], True),
            (None, [(None, GObject.TYPE_INT)], False),
            (None, [(None, GObject.TYPE_STRING)], False))

        self.tree = extTreeview.ExtTreeView(columns, True)

        self.scrolled.add(self.tree)

        targets = Gtk.TargetList.new([])
        targets.add_uri_targets(consts.DND_sirena_URI)
        self.tree.setDNDSources(targets)

        self.tree.connect('drag-data-get', self.onDragDataGet)
        self.tree.connect('key-press-event', self.onKeyPressed)
        self.tree.connect('exttreeview-button-pressed', self.onMouseButton)
        self.tree.connect('exttreeview-row-collapsed', self.onRowCollapsed)
        self.tree.connect('exttreeview-row-expanded', self.onRowExpanded)

    def getTreeDump(self, path=None):
        """ Recursively dump the given tree starting at path (None for the root of the tree) """
        list = []

        for child in self.tree.iterChildren(path):
            row = self.tree.getRow(child)

            if row[ROW_TYPE] == TYPE_INFO:
                continue

            if self.tree.getNbChildren(child) == 0:
                grandChildren = None
            elif self.tree.row_expanded(child):
                grandChildren = self.getTreeDump(child)
            else:
                grandChildren = []

            list.append([(row[ROW_NAME], row[ROW_TYPE], row[ROW_FULLPATH]), grandChildren])

        return list

    def restoreTreeDump(self, dump, parent=None):
        """ Recursively restore the dump under the given parent (None for the root of the tree) """
        for item in dump:
            (name, type, path) = item[0]

            if type == TYPE_FILE:
                self.tree.appendRow((icons.mediaFileMenuIcon(), name, TYPE_FILE, path), parent)
            else:
                newNode = self.tree.appendRow((icons.dirMenuIcon(), name, TYPE_DIR, path), parent)

                if item[1] is not None:
                    fakeChild = self.tree.appendRow((icons.dirMenuIcon(), '', TYPE_NONE, ''), newNode)

                    if len(item[1]) != 0:
                        # We must expand the row before adding the real children,
                        # but this works only if there is already at least one child
                        self.tree.expandRow(newNode)
                        self.restoreTreeDump(item[1], newNode)
                        self.tree.removeRow(fakeChild)

    def saveTreeState(self):
        """ Create a dictionary representing the current state of the tree """
        self.treeState = {
            'tree-state': self.getTreeDump(),
            'selected-paths': [tuple(path) for path in self.tree.getSelectedPaths()],
            'vscrollbar-pos': self.scrolled.get_vscrollbar().get_value(),
            'hscrollbar-pos': self.scrolled.get_hscrollbar().get_value(),
        }
        prefs.set(__name__, 'saved-states', self.treeState)
        self.music_paths = self.get_music_paths_from_tree()

    def restore_tree(self):
        self.tree.handler_block_by_func(self.onRowExpanded)
        self.restoreTreeDump(self.treeState['tree-state'])
        self.tree.handler_unblock_by_func(self.onRowExpanded)
        GObject.idle_add(self.scrolled.get_vscrollbar().set_value, self.treeState['vscrollbar-pos'])
        GObject.idle_add(self.scrolled.get_hscrollbar().set_value, self.treeState['hscrollbar-pos'])
        GObject.idle_add(self.tree.selectPaths, self.treeState['selected-paths'])
        GObject.idle_add(self.refresh)
        self.set_info_text()

    def play(self, path=None):
        """
            Replace/extend the tracklist
            If 'path' is None, use the current selection
        """
        if path is None:
            track_paths = [row[ROW_FULLPATH] for row in self.tree.getSelectedRows()]
        else:
            track_paths = [self.tree.getRow(path)[ROW_FULLPATH]]

        modules.postMsg(consts.MSG_EVT_LOAD_TRACKS, {'paths': track_paths})

    # --== Tree management ==--

    def startLoading(self, row):
        """ Tell the user that the contents of row is being loaded """
        name = self.tree.getItem(row, ROW_NAME)
        loading_text = '%s  <span size="smaller" foreground="#909090">%s</span>'
        loading_text %= (name, _('loading...'))
        self.tree.setItem(row, ROW_NAME, loading_text)

    def stopLoading(self, row):
        """ Tell the user that the contents of row has been loaded"""
        try:
            name = self.tree.getItem(row, ROW_NAME)
        except ValueError:
            # If a search is made quickly after launching, the row may have gone.
            return
        index = name.find('<span')

        if index != -1:
            self.tree.setItem(row, ROW_NAME, name[:index - 2])

    def _filename(self, row):
        """
            Compare two filenames:
              - First the lower case version (we want 'bar' to be before 'Foo')
              - Then, if an equality occurs, the normal version (we want 'Foo' and 'foo' to be different folders)
        """
        return row[ROW_NAME].lower(), row[ROW_NAME]

    def __cmpRowsOnFilename(self, r1, r2):
        """
            Compare two filenames:
              - First the lower case version (we want 'bar' to be before 'Foo')
              - Then, if an equality occurs, the normal version (we want 'Foo' and 'foo' to be different folders)
        """
        name1 = r1[ROW_NAME]
        name2 = r2[ROW_NAME]

        result = locale.strcoll(name1, name2)
        assert result == locale.strcoll(name1.lower(), name2.lower()) or locale.strcoll(name1, name2)
        return result

    def getDirContents(self, directory):
        """ Return a tuple of sorted rows (directories, playlists, mediaFiles) for the given directory """
        mediaFiles = []
        directories = []

        for (file, path) in tools.listDir(directory):
            # Make directory names prettier
            junk = ['_']
            pretty_name = file
            for item in junk:
                pretty_name = pretty_name.replace(item, ' ')

            if isdir(path):
                directories.append((icons.dirMenuIcon(), tools.htmlEscape(pretty_name), TYPE_DIR, path))
            elif isfile(path):
                if media.isSupported(file):
                    mediaFiles.append((icons.mediaFileMenuIcon(), tools.htmlEscape(pretty_name), TYPE_FILE, path))

        # Individually sort each type of file by name
        mediaFiles.sort(key=self._filename)
        directories.sort(key=self._filename)

        return (directories, mediaFiles)

    def exploreDir(self, parent, directory, fakeChild=None):
        """
        List the contents of the given directory and append it to the tree as a child of parent
        If fakeChild is not None, remove it when the real contents has been loaded
        """
        directories, mediaFiles = self.getDirContents(directory)

        self.tree.appendRows(directories, parent)
        self.tree.appendRows(mediaFiles, parent)

        if fakeChild is not None:
            self.tree.removeRow(fakeChild)

        GObject.idle_add(self.updateDirNodes(parent).__next__)

    def updateDirNodes(self, parent):
        """
        This generator updates the directory nodes, based on whether they
        should be expandable
        """
        for child in self.tree.iterChildren(parent):
            # Only directories need to be updated and since they all come first,
            # we can stop as soon as we find something else
            if self.tree.getItem(child, ROW_TYPE) != TYPE_DIR:
                break

            # Make sure it's readable
            directory = self.tree.getItem(child, ROW_FULLPATH)
            hasContent = False
            if os.access(directory, os.R_OK | os.X_OK):
                for (file, path) in tools.listDir(directory):
                    if isdir(path) or (isfile(path) and media.isSupported(file)):
                        hasContent = True
                        break

            # Append/remove children if needed
            if hasContent and self.tree.getNbChildren(child) == 0:
                self.tree.appendRow((icons.dirMenuIcon(), '', TYPE_NONE, ''), child)
            elif not hasContent and self.tree.getNbChildren(child) > 0:
                self.tree.removeAllChildren(child)

            yield True

        if parent is not None:
            self.stopLoading(parent)

        yield False

    def refresh(self, treePath=None):
        """ Refresh the tree, starting from treePath """
        if treePath is None:
            # Check all paths in reverse order, because we might remove some
            for child in reversed(list(self.tree.iterChildren(None))):
                path = self.tree.getItem(child, ROW_FULLPATH)
                # Check if path is no separator and does not exist
                if path is not None and not os.path.exists(path):
                    self.tree.removeRow(child)
            # In a second loop (because the iters have changed) we refresh
            # all expanded nodes.
            for child in self.tree.iterChildren(None):
                if self.tree.row_expanded(child):
                    GObject.idle_add(self.refresh, child)
            return

        directory = self.tree.getItem(treePath, ROW_FULLPATH)

        directories, mediaFiles = self.getDirContents(directory)

        disk = directories + mediaFiles
        diskIndex = 0
        childIndex = 0
        childLeftIntentionally = False

        while diskIndex < len(disk):
            rowPath = self.tree.getChild(treePath, childIndex)

            # Did we reach the end of the tree?
            if rowPath is None:
                break

            cmpResult = self.__cmpRowsOnFilename(self.tree.getRow(rowPath), disk[diskIndex])

            if cmpResult < 0:
                # We can't remove the only child left, to prevent the node
                # from being closed automatically
                if self.tree.getNbChildren(treePath) == 1:
                    childLeftIntentionally = True
                    break

                self.tree.removeRow(rowPath)
            else:
                if cmpResult > 0:
                    self.tree.insertRowBefore(disk[diskIndex], treePath, rowPath)
                diskIndex += 1
                childIndex += 1

        # If there are tree rows left, all the corresponding files are no longer there
        if not childLeftIntentionally:
            while childIndex < self.tree.getNbChildren(treePath):
                self.tree.removeRow(self.tree.getChild(treePath, childIndex))

        # Disk files left?
        while diskIndex < len(disk):
            self.tree.appendRow(disk[diskIndex], treePath)
            diskIndex += 1

        # Deprecated child left? (must be done after the addition of left disk files)
        if childLeftIntentionally:
            self.tree.removeRow(self.tree.getChild(treePath, 0))

        # Update nodes' appearance
        if len(directories) != 0:
            GObject.idle_add(self.updateDirNodes(treePath).__next__)

        # Recursively refresh expanded rows
        for child in self.tree.iterChildren(treePath):
            if self.tree.row_expanded(child):
                GObject.idle_add(self.refresh, child)

    # --== GTK handlers ==--

    def onMouseButton(self, tree, event, path):
        """ A mouse button has been pressed """
        if event.button == 3:
            self.onShowPopupMenu(tree, event.button, event.time, path)
        elif path is not None:
            if event.button == 2:
                self.play(path)
            elif event.button == 1 and event.type == Gdk.EventType._2BUTTON_PRESS:
                if tree.getItem(path, ROW_PIXBUF) != icons.dirMenuIcon():
                    self.play()
                elif tree.row_expanded(path):
                    tree.collapse_row(path)
                else:
                    tree.expand_row(path, False)

    def onShowPopupMenu(self, tree, button, time, path):
        """ Show a popup menu """
        if path and self.tree.getItem(path, ROW_FULLPATH) is None:
            # separator selected
            return

        if path and self.tree.getItem(path, ROW_TYPE) == TYPE_INFO:
            # info node selected, make it clickable
            path = None

        # Keep reference after method exits.
        self.popup_menu = Gtk.Menu()

        # Play selection
        play = Gtk.MenuItem.new_with_label(_('Append'))
        self.popup_menu.append(play)
        if path is None:
            play.set_sensitive(False)
        else:
            play.connect('activate', lambda widget: self.play())

        # open containing folder
        show_folder = None
        if path:
            show_folder = Gtk.MenuItem.new_with_label(_('Open containing folder'))
            filepath = self.tree.getItem(path, ROW_FULLPATH)
            parent_path = os.path.dirname(filepath)
            show_folder.connect('activate', lambda widget: tools.open_path(parent_path))

        # Do not show the other options when we are displaying results
        if self.displaying_results:
            if show_folder:
                self.popup_menu.append(show_folder)
            self.popup_menu.show_all()
            self.popup_menu.popup(None, None, None, None, button, time)
            return

        self.popup_menu.append(Gtk.SeparatorMenuItem())

        # Refresh the view
        refresh = Gtk.MenuItem.new_with_label(_('Refresh'))
        refresh.connect('activate', lambda widget: self.refresh())
        self.popup_menu.append(refresh)

        # Add new dir
        dir = Gtk.MenuItem()
        if path is None:
            dir.set_label(_('Add music folder'))
            dir.connect('activate', self.on_add_dir)
            self.popup_menu.append(dir)
        else:
            # Check that the dir is top-level and not $HOME or /
            this_path = self.tree.getItem(path, ROW_FULLPATH)
            static_selected = any([samefile(static_path, this_path)
                                   for static_path in self.static_paths])
            store = self.tree.store
            depth = store.iter_depth(store.get_iter(path))
            top_level = (depth == 0)
            if top_level and not static_selected:
                dir.set_label(_('Hide folder'))
                dir.connect('activate', self.on_remove_dir, path)
                self.popup_menu.append(dir)

        # open containing folder
        if show_folder:
            self.popup_menu.append(show_folder)

        self.popup_menu.show_all()
        self.popup_menu.popup(None, None, None, None, button, time)

    def on_add_dir(self, widget):
        parent = prefs.getWidgetsTree().get_object('win-main')
        path = fileChooser.openDirectory(parent, _('Choose a directory'))
        if path is None:
            return

        if os.path.isdir(path):
            if path in self.static_paths:
                errorMsgBox(None, _('Invalid Folder'),
                            _('You cannot add your root or home folder to the music directories'))
                return
            self.add_dir(path)
            music_paths = self.get_music_paths_from_tree()
            modules.postMsg(consts.MSG_EVT_MUSIC_PATHS_CHANGED, {'paths': music_paths})
            self.set_info_text()
        else:
            errorMsgBox(None, _('This path does not exist'),
                        '"%s"\n' % path + _('Please select an existing directory.'))

    def on_remove_dir(self, widget, path):
        self.tree.removeRow(path)
        music_paths = self.get_music_paths_from_tree()
        modules.postMsg(consts.MSG_EVT_MUSIC_PATHS_CHANGED, {'paths': music_paths})
        self.set_info_text()

    def onKeyPressed(self, tree, event):
        """ A key has been pressed """
        keyname = Gdk.keyval_name(event.keyval)

        if keyname == 'F5':
            self.refresh()
        elif keyname == 'plus':
            tree.expandRows()
        elif keyname == 'Left':
            tree.collapseRows()
        elif keyname == 'Right':
            tree.expandRows()
        elif keyname == 'minus':
            tree.collapseRows()
        elif keyname == 'space':
            tree.switchRows()
        elif keyname == 'Return':
            self.play()

    def onRowExpanded(self, tree, path):
        """ Replace the fake child by the real children """
        self.startLoading(path)
        GObject.idle_add(self.exploreDir, path, tree.getItem(path, ROW_FULLPATH), tree.getChild(path, 0))

    def onRowCollapsed(self, tree, path):
        """ Replace all children by a fake child """
        tree.removeAllChildren(path)
        tree.appendRow((icons.dirMenuIcon(), '', TYPE_NONE, ''), path)

    def onDragDataGet(self, tree, context, selection, info, time):
        """ Provide information about the data being dragged """
        import urllib.request
        selection.set_uris([
            urllib.request.pathname2url(file)
            for file in [row[ROW_FULLPATH] for row in tree.getSelectedRows()]])

    def add_dir(self, path):
        '''
        Add a directory with one fake child to the tree
        '''
        name = tools.dirname(path)
        name = tools.htmlEscape(name)
        parent = self.tree.appendRow((icons.dirMenuIcon(), name, TYPE_DIR, path), None)
        # add fake child
        self.tree.appendRow((icons.dirMenuIcon(), '', TYPE_NONE, ''), parent)

    def _is_separator(self, model, iter):
        return model[iter][ROW_NAME] is None

    def _get_xdg_music_dir(self):
        ''' Read XDG music directory '''
        xdg_file = os.path.join(consts.dirBaseUsr, '.config', 'user-dirs.dirs')
        if not os.path.exists(xdg_file):
            return None

        import re
        folder_regex = re.compile(r'XDG_MUSIC_DIR\=\"\$HOME/(.+)\"')
        with open(xdg_file) as f:
            content = f.read()
            match = folder_regex.search(content)
            if match:
                dirname = match.group(1)
                # Unquote dirname: "My%20folder" -> "My folder"
                dirname = urllib.parse.unquote(dirname)
                path = os.path.join(consts.dirBaseUsr, dirname)
                return path
        return None

    def search_music_paths(self):
        """
        Checks some standard directories and returns them if they contain music
        """
        paths = []
        xdg_music_dir = self._get_xdg_music_dir()
        if xdg_music_dir:
            paths.append(xdg_music_dir)

        # Try other music folders
        names = ['Albums', _('Albums')]
        if not xdg_music_dir:
            names.extend(['Music', _('Music')])

        # Check lowercase names too
        names = [[name, name.lower()] for name in names]
        # Fold into one list again and remove duplicate names
        names = set(itertools.chain(*names))

        for name in names:
            music_folder = os.path.join(consts.dirBaseUsr, name)
            # Check if dir exists and has files
            if os.path.isdir(music_folder) and os.listdir(music_folder):
                paths.append(music_folder)
        return paths

    def populate_tree(self):
        assert self.tree is None
        self.createTree()
        self.tree.set_row_separator_func(self._is_separator)

        # Restore the tree if we have any to restore, else build new one
        if self.treeState:
            self.restore_tree()
            return

        paths = self.static_paths[:]

        music_paths = self.search_music_paths()

        if music_paths:
            # Add separator
            paths.append(None)
            paths.extend(music_paths)

        for path in paths:
            if path is None:
                # Separator
                self.tree.appendRow((icons.nullMenuIcon(), None, TYPE_NONE, None), None)
            else:
                self.add_dir(path)

        self.set_info_text()

    def get_music_paths_from_tree(self):
        music_paths = []
        for child in self.tree.iterChildren(None):
            row = self.tree.getRow(child)
            path = row[ROW_FULLPATH]
            if path and path not in self.static_paths and os.path.isdir(path):
                if not path.endswith('/'):
                    path += '/'
                music_paths.append(path)
        return music_paths

    def set_info_text(self):
        """
        Append an item that explains how to add music folders if no music
        folders are present. Remove the item if music folders are set.
        """
        music_paths = self.get_music_paths_from_tree()

        last_top_node = self.tree.getChild(None, self.tree.getNbChildren(None) - 1)
        path = self.tree.getItem(last_top_node, ROW_FULLPATH)
        typ = self.tree.getItem(last_top_node, ROW_TYPE)
        last_top_node_info = (typ == TYPE_INFO) and not path

        if music_paths:
            for child in reversed(list(self.tree.iterChildren(None))):
                path = self.tree.getItem(child, ROW_FULLPATH)
                typ = self.tree.getItem(child, ROW_TYPE)
                info_node = (typ == TYPE_INFO) and not path
                if info_node:
                    self.tree.removeRow(child)
        elif not music_paths and not last_top_node_info:
            msg = _('Right-click to add music folders')
            self.tree.appendRow((icons.infoMenuIcon(), msg, TYPE_INFO, ''), None)

    # --== Message handlers ==--

    def onAppStarted(self):
        """ The module has been loaded """
        self.tree = None
        self.cfgWin = None
        self.scrolled = Gtk.ScrolledWindow()
        self.treeState = prefs.get(__name__, 'saved-states', None)

        self.scrolled.set_shadow_type(Gtk.ShadowType.IN)
        self.scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        self.scrolled.show()

        left_vbox = prefs.getWidgetsTree().get_object('vbox3')
        left_vbox.pack_start(self.scrolled, True, True, 0)

        self.static_paths = ['/', consts.dirBaseUsr]

        self.displaying_results = False
        self.populate_tree()

        music_paths = self.get_music_paths_from_tree()
        modules.postMsg(consts.MSG_EVT_MUSIC_PATHS_CHANGED, {'paths': music_paths})

        self.tree.connect('drag-begin', self.onDragBegin)

    def onAppQuit(self):
        """ The module is going to be unloaded """
        if not self.displaying_results:
            self.saveTreeState()

    def _remove_searching_node(self):
        # Remove the "Searching ..." node if it still exists
        if (self.tree.isValidPath(self.searching_text_path) and
                self.tree.getItem(self.searching_text_path, ROW_NAME) == self.searching_text):
            self.tree.removeRow(self.searching_text_path)

    def onSearchStart(self, query):
        if not self.displaying_results:
            self.saveTreeState()

        self.tree.clear()
        self.displaying_results = True

        self.searching_text = _('Searching ...')
        self.searching_text_path = self.tree.appendRow((icons.infoMenuIcon(), self.searching_text, TYPE_INFO, ''), None)

    def onSearchAppend(self, results, query):
        self._remove_searching_node()

        # Make sure we never call this method without calling onSearchStart first
        if not self.displaying_results:
            return

        dirs, files = results

        for path, name in dirs:
            new_node = self.tree.appendRow((icons.dirMenuIcon(), name, TYPE_DIR, path), None)
            # add fake child
            self.tree.appendRow((icons.dirMenuIcon(), '', TYPE_NONE, ''), new_node)

        for file, name in files:
            self.tree.appendRow((icons.mediaFileMenuIcon(), name, TYPE_FILE, file), None)

    def onSearchEnd(self):
        self._remove_searching_node()
        if len(self.tree) == 0:
            if self.music_paths:
                text = _('No tracks found')
            else:
                text = _('No music folders have been added')
            self.tree.appendRow((icons.infoMenuIcon(), text, TYPE_INFO, ''), None)
            return

    def onSearchReset(self):
        if self.displaying_results:
            self.tree.clear()
            self.restore_tree()
            self.displaying_results = False

    # --== GTK Handlers ==--

    def onDragBegin(self, tree, context):
        """ A drag'n'drop operation has begun.

        Pass the paths to the track tree to let it decide whether to
        collapse directories.

        """
        paths = [row[ROW_FULLPATH] for row in tree.getSelectedRows()]
        modules.postMsg(consts.MSG_CMD_FILE_EXPLORER_DRAG_BEGIN, {'paths': paths})

        # Preload the tracks to speedup their addition to the playlist.
        import threading
        crawler = threading.Thread(target=media.preloadTracks, args=(paths,))
        crawler.start()
