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
import os.path
import random
import time

from gi.repository import Gtk


# --- Not a constant, but it fits well here
random.seed(int(time.time()))

# --- Miscellaneous
socketTimeout = 10


# --- Strings
appName = 'Sirena'
appVersion = '1.0'
appNameShort = 'sirena'
commands = ['play', 'pause', 'prev', 'next', 'stop']


# --- URLs
urlMain = 'https://github.com/santelmotechnologies/sirena'
urlHelp = 'http://github.com/santelmotechnologies/sirena/issues'


# --- Directories
dirBaseUsr = os.path.expanduser('~')
dirBaseCfg = os.path.join(dirBaseUsr, '.config')
dirBaseSrc = os.path.join(os.path.dirname(__file__), '..')

dirRes = os.path.join(dirBaseSrc, '..', 'res')
dirDoc = os.path.join(dirBaseSrc, '..', 'doc')
dirPix = os.path.join(dirBaseSrc, '..', 'pix')
dirCfg = os.path.join(dirBaseCfg, appNameShort)
dirLog = os.path.join(dirCfg, 'Logs')

dirLocale = os.path.join(dirBaseSrc, '..', 'locale')
if not os.path.isdir(dirLocale):
    dirLocale = os.path.join(dirBaseSrc, '..', '..', 'locale')

# Make sure the config directory exists
if not os.path.exists(dirBaseCfg):
    os.mkdir(dirBaseCfg)

if not os.path.exists(dirCfg):
    os.mkdir(dirCfg)

# Make sure the log directory exists
if not os.path.exists(dirLog):
    os.mkdir(dirLog)


# --- Icons
fileImgIcon16 = os.path.join(dirPix, 'sirena-16.png')
fileImgIcon24 = os.path.join(dirPix, 'sirena-24.png')
fileImgIcon32 = os.path.join(dirPix, 'sirena-32.png')
fileImgIcon48 = os.path.join(dirPix, 'sirena-48.png')
fileImgIcon64 = os.path.join(dirPix, 'sirena-64.png')
fileImgIcon128 = os.path.join(dirPix, 'sirena-128.png')


# --- Files
fileLog = os.path.join(dirLog, 'log')
filePrefs = os.path.join(dirCfg, 'prefs')
fileLicense = os.path.join(dirDoc, 'LICENCE')


# --- DBus constants
dbusService = 'org.mpris.sirena'
dbusInterface = 'org.freedesktop.MediaPlayer'


# --- Tracks
UNKNOWN_DATE = 0
UNKNOWN_GENRE = _('Unknown Genre')
UNKNOWN_TITLE = _('Unknown Title')
UNKNOWN_ALBUM = _('Unknown Album')
UNKNOWN_ARTIST = _('Unknown Artist')
UNKNOWN_LENGTH = 0
UNKNOWN_BITRATE = 0
UNKNOWN_ENC_MODE = 0
UNKNOWN_MB_TRACKID = 0
UNKNOWN_DISC_NUMBER = 0
UNKNOWN_SAMPLE_RATE = 0
UNKNOWN_TRACK_NUMBER = 0
UNKNOWN_ALBUM_ARTIST = _('Unknown Album Artist')


# --- Drag'n'Drop
(
    DND_URI,          # From another application (e.g., from Nautilus)
    DND_sirena_URI,      # Inside sirena when tags are not known (e.g., from the FileExplorer)
) = list(range(2))

DND_TARGETS = {
    DND_URI: ('text/uri-list', 0, DND_URI),
    DND_sirena_URI: ('sirena/uri-list', Gtk.TargetFlags.SAME_APP, DND_sirena_URI),
}

DND_INTERNAL_TARGET_NAME = 'exttreeview-internal'


# --- View modes
(
    VIEW_MODE_FULL,
    VIEW_MODE_PLAYLIST,
) = list(range(2))


# --- Message that can be sent/received by modules
# --- A message is always associated with a (potentially empty) dictionnary containing its parameters
(
    # --== COMMANDS ==--

    # GStreamer player
    MSG_CMD_PLAY,                # Play a resource                            Parameters: 'uri'
    MSG_CMD_STOP,                # Stop playing                               Parameters:
    MSG_CMD_SEEK,                # Jump to a position                         Parameters: 'seconds'
    MSG_CMD_STEP,                # Step back or forth                         Parameters: 'seconds'
    MSG_CMD_BUFFER,              # Buffer a file                              Parameters: 'filename'
    MSG_CMD_TOGGLE_PAUSE,        # Toggle play/pause                          Parameters:
    MSG_CMD_ENABLE_EQZ,          # Enable the equalizer                       Parameters:
    MSG_CMD_SET_EQZ_LVLS,        # Set the levels of the 10-bands equalizer   Parameters: 'lvls'
    MSG_CMD_ENABLE_RG,           # Enable ReplayGain                          Parameters:

    # Tracklist
    MSG_CMD_NEXT,                # Play the next track             Parameters:
    MSG_CMD_PREVIOUS,            # Play the previous track         Parameters:
    MSG_CMD_TRACKLIST_SET,       # Replace tracklist               Parameters: 'tracks', 'playNow'
    MSG_CMD_TRACKLIST_ADD,       # Extend tracklist                Parameters: 'tracks', 'playNow'
    MSG_CMD_TRACKLIST_DEL,       # Remove a track                  Parameters: 'idx'
    MSG_CMD_TRACKLIST_CLR,       # Clear tracklist                 Parameters:
    MSG_CMD_TRACKLIST_SHUFFLE,   # Shuffle the tracklist           Parameters:
    MSG_CMD_TRACKLIST_REPEAT,    # Set/Unset the repeat function   Parameters: 'repeat'

    # Covers
    MSG_CMD_SET_COVER,           # Cover file for the given track     Parameters: 'track', 'pathThumbnail', 'pathFullSize'

    # Misc
    MSG_CMD_THREAD_EXECUTE,      # An *internal* command for threaded modules     Parameters: N/A


    # --== EVENTS ==--

    # Current track
    MSG_EVT_PAUSED,              # Paused                                             Parameters:
    MSG_EVT_STOPPED,             # Stopped                                            Parameters:
    MSG_EVT_UNPAUSED,            # Unpaused                                           Parameters:
    MSG_EVT_NEW_TRACK,           # The current track has changed                      Parameters: 'track'
    MSG_EVT_NEED_BUFFER,         # The next track should be buffered                  Parameters:
    MSG_EVT_TRACK_POSITION,      # New position in the current track                  Parameters: 'seconds'
    MSG_EVT_TRACK_ENDED_OK,      # The current track has ended                        Parameters:
    MSG_EVT_TRACK_ENDED_ERROR,   # The current track has ended because of an error    Parameters:

    # Tracklist
    MSG_EVT_TRACK_MOVED,         # The position of the current track has changed    Parameters: 'hasPrevious', 'hasNext'
    MSG_EVT_NEW_TRACKLIST,       # A new tracklist has been set                     Parameters: 'tracks', 'playtime'
    MSG_EVT_REPEAT_CHANGED,      # The repeat function has been enabled/disabled    Parameters: 'repeat'

    # Application
    MSG_EVT_APP_QUIT,            # The application is quitting         Parameters:
    MSG_EVT_APP_STARTED,         # The application has just started    Parameters:

    # Modules
    MSG_EVT_MOD_LOADED,          # The module has been loaded by request of the user      Parameters:
    MSG_EVT_MOD_UNLOADED,        # The module has been unloaded by request of the user    Parameters:

    MSG_CMD_FILE_EXPLORER_DRAG_BEGIN,
    MSG_EVT_SEARCH_START,
    MSG_EVT_SEARCH_APPEND,
    MSG_EVT_SEARCH_END,
    MSG_EVT_SEARCH_RESET,

    MSG_EVT_MUSIC_PATHS_CHANGED,
    MSG_EVT_LOAD_TRACKS,

    # End value
    MSG_END_VALUE
) = list(range(42))
