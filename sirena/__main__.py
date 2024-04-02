#!/usr/bin/env python3
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

import logging
import optparse
import os
import traceback

import dbus

import gi
gi.require_version('Gst', '1.0')
gi.require_version('Gtk', '3.0')
from gi.repository import Gst
from gi.repository import Gtk

Gst.init(None)

from sirena import tools
from sirena.tools import consts
from sirena.tools import log

tools.print_platform_info()


# Command line
optparser = optparse.OptionParser(
    usage='Usage: %prog [options] [FILE(s) | ' + ' | '.join(consts.commands) + ']')
optparser.add_option(
    '--multiple-instances',
    action='store_true',
    default=False,
    help='start a new instance even if one is already running')

optOptions, optArgs = optparser.parse_args()


# Check whether Sirena is already running?
if not optOptions.multiple_instances:
    shouldStop = False
    dbusSession = None

    try:
        dbusSession = dbus.SessionBus()
        activeServices = dbusSession.get_object(
            'org.freedesktop.DBus', '/org/freedesktop/DBus').ListNames()

        if consts.dbusService in activeServices:
            shouldStop = True

            window = dbus.Interface(
                dbusSession.get_object(consts.dbusService, '/'), consts.dbusInterface)
            player = dbus.Interface(
                dbusSession.get_object(consts.dbusService, '/Player'), consts.dbusInterface)
            playlist = dbus.Interface(
                dbusSession.get_object(consts.dbusService, '/TrackList'), consts.dbusInterface)

            commands, paths = tools.separate_commands_and_tracks(optArgs)
            for command in commands:
                print(command.capitalize())
                getattr(player, command.capitalize())()

            # Fill the current instance with the given tracks, if any
            if paths:
                # make the paths absolute
                paths = [os.path.abspath(path) for path in paths]
                print('Appending to the playlist:')
                print('\n'.join(paths))
                playNow = 'pause' not in commands and 'stop' not in commands
                playlist.AddTracks(paths, playNow)
                # Raise the window of the already running instance
                window.RaiseWindow()
    except:
        print(traceback.format_exc())

    if dbusSession is not None:
        dbusSession.close()

    if shouldStop:
        import sys
        print('There is already one Sirena instance running. Exiting.')
        sys.exit(1)


# Start a new instance
import gettext
import locale

from gi.repository import Gdk
from gi.repository import GdkPixbuf
from gi.repository import GObject

from sirena.tools import loadGladeFile, prefs

DEFAULT_VIEW_MODE = consts.VIEW_MODE_FULL
DEFAULT_PANED_POS = 370  # 300
DEFAULT_WIN_WIDTH = 900  # 750
DEFAULT_WIN_HEIGHT = 500  # 470
DEFAULT_MAXIMIZED_STATE = False


def realStartup(window, paned):
    """
    Perform all the initialization stuff which is not mandatory to display the
    window. This function should be called within the GTK main loop, once the
    window has been displayed
    """

    # Is the application started for the first time?
    first_start = prefs.get(__name__, 'first-time', True)
    logging.debug('First start: {}'.format(first_start))
    if first_start:
        prefs.set(__name__, 'first-time', False)

        # Enable some modules by default
        prefs.set('modules', 'enabled_modules', ['Covers', 'Desktop Notification'])

    import atexit
    import signal
    import dbus.mainloop.glib

    from sirena import modules

    modules.load_enabled_modules()

    def onDelete(win, event):
        """ Use our own quit sequence, that will itself destroy the window """
        win.hide()
        modules.postQuitMsg()
        return True

    def onResize(win, rect):
        """ Save the new size of the window """
        maximized = win.get_state() & Gdk.WindowState.MAXIMIZED
        if not maximized:
            prefs.set(__name__, 'win-width', rect.width)
            prefs.set(__name__, 'win-height', rect.height)

            view_mode = prefs.get(__name__, 'view-mode', DEFAULT_VIEW_MODE)
            if view_mode in (consts.VIEW_MODE_FULL, consts.VIEW_MODE_PLAYLIST):
                prefs.set(__name__, 'full-win-height', rect.height)

    def onPanedResize(win, rect):
        prefs.set(__name__, 'paned-pos', paned.get_position())

    def onState(win, event):
        """ Save the new state of the window """
        if event.changed_mask & Gdk.WindowState.MAXIMIZED:
            maximized = bool(event.new_window_state & Gdk.WindowState.MAXIMIZED)
            prefs.set(__name__, 'win-is-maximized', maximized)

    def atExit():
        """
        Final function, called just before exiting the Python interpreter
        """
        prefs.save()
        log.logger.info('Stopped')

    # D-Bus
    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)

    # Register some handlers (Signal SIGKILL cannot be caught)
    atexit.register(atExit)
    signal.signal(signal.SIGINT, lambda _sig, _frame: onDelete(window, None))
    signal.signal(signal.SIGTERM, lambda _sig, _frame: onDelete(window, None))

    # GTK handlers
    window.connect('delete-event', onDelete)
    window.connect('size-allocate', onResize)
    window.connect('window-state-event', onState)
    paned.connect('size-allocate', onPanedResize)

    # Let's go
    GObject.idle_add(modules.postMsg, consts.MSG_EVT_APP_STARTED)


# --== Entry point ==--

def main():
    log.logger.info('Started')

    # Localization
    locale.setlocale(locale.LC_ALL, '')
    gettext.textdomain(consts.appNameShort)
    gettext.bindtextdomain(consts.appNameShort, consts.dirLocale)

    # Command line
    prefs.setCmdLine((optOptions, optArgs))

    # Create the GUI
    wTree = loadGladeFile('MainWindow.ui')
    paned = wTree.get_object('pan-main')
    window = wTree.get_object('win-main')
    prefs.setWidgetsTree(wTree)

    window.set_icon_list([
        GdkPixbuf.Pixbuf.new_from_file(consts.fileImgIcon16),
        GdkPixbuf.Pixbuf.new_from_file(consts.fileImgIcon24),
        GdkPixbuf.Pixbuf.new_from_file(consts.fileImgIcon32),
        GdkPixbuf.Pixbuf.new_from_file(consts.fileImgIcon48),
        GdkPixbuf.Pixbuf.new_from_file(consts.fileImgIcon64),
        GdkPixbuf.Pixbuf.new_from_file(consts.fileImgIcon128)])

    # RGBA support
    # TODO: Is this still needed?
    visual = window.get_screen().get_rgba_visual()
    window.set_visual(visual)

    # Show all widgets and restore the window size BEFORE hiding some of them
    # when restoring the view mode
    # Resizing must be done before showing the window to make sure that the WM
    # correctly places the window
    if prefs.get(__name__, 'win-is-maximized', DEFAULT_MAXIMIZED_STATE):
        window.maximize()

    height = prefs.get(__name__, 'win-height', DEFAULT_WIN_HEIGHT)
    window.resize(prefs.get(__name__, 'win-width', DEFAULT_WIN_WIDTH), height)
    window.show_all()

    paned.set_position(prefs.get(__name__, 'paned-pos', DEFAULT_PANED_POS))

    # Initialization done, let's continue the show
    GObject.idle_add(realStartup, window, paned)
    Gtk.main()


if __name__ == '__main__':
    main()
