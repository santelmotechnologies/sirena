import os.path
import sys

import gi

gi.require_version('Gst', '1.0')
gi.require_version('Gtk', '3.0')

DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(DIR)

sys.path.insert(0, BASE_DIR)

from sirena import modules

modules.ThreadedModule.gtkExecute
modules.ThreadedModule.threadExecute

from sirena.modules import Covers, CtrlPanel, DBus, DesktopNotification, Equalizer, \
    FileExplorer, GnomeMediaKeys, GSTPlayer, Search, StatusbarTitlebar, \
    TrackLoader, TrackPanel, Tracktree

Covers.Covers
CtrlPanel.CtrlPanel
DBus.DBus
DesktopNotification.DesktopNotification
Equalizer.Equalizer
FileExplorer.FileExplorer
GnomeMediaKeys.GnomeMediaKeys
GSTPlayer.GSTPlayer
Search.Search
StatusbarTitlebar.StatusbarTitlebar
TrackLoader.TrackLoader
TrackPanel.TrackPanel
Tracktree.Tracktree

from sirena.modules.DBus import DBusObjectRoot, DBusObjectTracklist, DBusObjectPlayer

dbor = DBusObjectRoot
dbor.Identity
dbor.Quit
dbor.MprisVersion

dbot = DBusObjectTracklist
dbot.GetMetadata
dbot.GetCurrentTrack
dbot.GetLength
dbot.AddTrack
dbot.DelTrack
dbot.SetLoop
dbot.SetRandom
dbot.Clear
dbot.SetTracks

dbop = DBusObjectPlayer
dbop.Next
dbop.Prev
dbop.Pause
dbop.Stop
dbop.Play
dbop.Repeat
dbop.GetStatus
dbop.GetCaps
dbop.PositionSet
dbop.PositionGet

from sirena.media.track import Track

Track.getAlbumArtist
Track.getMBTrackId
