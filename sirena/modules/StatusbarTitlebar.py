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

from sirena import modules
from sirena.tools import consts, prefs


MOD_INFO = ('Status and Title Bars', 'Status and Title Bars', '', [], True, False)


class StatusbarTitlebar(modules.Module):
    """ This module manages both the status and the title bars """

    def __init__(self):
        """ Constructor """
        handlers = {
            consts.MSG_EVT_PAUSED: self.onPaused,
            consts.MSG_EVT_STOPPED: self.onStopped,
            consts.MSG_EVT_UNPAUSED: self.onUnpaused,
            consts.MSG_EVT_NEW_TRACK: self.onNewTrack,
            consts.MSG_EVT_APP_STARTED: self.onAppStarted,
        }

        modules.Module.__init__(self, handlers)

    def __updateTitlebar(self):
        """ Update the title bar """
        if self.currTrack is None:
            self.window.set_title(consts.appName)
        elif self.paused:
            self.window.set_title('%s %s' % (self.currTrack.get_window_title(), _('[paused]')))
        else:
            self.window.set_title('%s' % self.currTrack.get_window_title())

    # --== Message handlers ==--

    def onAppStarted(self):
        """ Real initialization function, called when this module has been loaded """
        self.window = prefs.getWidgetsTree().get_object('win-main')

        # Current player status
        self.paused = False
        self.currTrack = None

    def onNewTrack(self, track):
        """ A new track is being played """
        self.paused = False
        self.currTrack = track
        self.__updateTitlebar()

    def onPaused(self):
        """ Playback has been paused """
        self.paused = True
        self.__updateTitlebar()

    def onUnpaused(self):
        """ Playback has been unpaused """
        self.paused = False
        self.__updateTitlebar()

    def onStopped(self):
        """ Playback has been stopped """
        self.paused = False
        self.currTrack = None
        self.__updateTitlebar()
