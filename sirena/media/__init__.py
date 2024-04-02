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

import os
import sys
import traceback
import logging
from collections import defaultdict
from os.path import splitext

if __name__ == '__main__':
    base_dir = os.path.abspath(os.path.join(os.path.abspath(__file__), '../../'))
    sys.path.insert(0, base_dir)

from sirena.media.format import monkeysaudio, asf, flac, mp3, mp4, mpc, ogg, wav, wavpack
from sirena.tools.log import logger
from sirena.media.track.fileTrack import FileTrack
from sirena import tools


# Supported formats with associated modules
mFormats = {'.ac3': monkeysaudio, '.ape': monkeysaudio, '.flac': flac,
            '.m4a': mp4, '.mp2': mp3, '.mp3': mp3, '.mp4': mp4, '.mpc': mpc,
            '.oga': ogg, '.ogg': ogg, '.wav': wav, '.wma': asf, '.wv': wavpack}


def isSupported(file):
    """ Return True if the given file is a supported format """
    try:
        return splitext(file.lower())[1] in mFormats
    except:
        return False


# It seems a lock is not really necessary here. It does slow down execution
# a little bit though, so we currently don't use a lock.
_track_cache = {}


def _getTrackFromFile(file):
    """
        Return a Track object, based on the tags of the given file
        The 'file' parameter must be a real file (not a playlist or a directory)
    """
    try:
        return mFormats[splitext(file.lower())[1]].getTrack(file)
    except:
        logger.error('Unable to extract information from %s\n\n%s' % (file, traceback.format_exc()))
        return FileTrack(file)


def getTrackFromFile(file):
    """
        Return a Track object, based on the tags of the given file
        The 'file' parameter must be a real file (not a playlist or a directory)
    """
    if file in _track_cache:
        return _track_cache[file]
    track = _getTrackFromFile(file)
    _track_cache[file] = track
    return track


class TrackDir(object):
    def __init__(self, name='', dir=None, flat=False):
        self.dirname = name or (tools.dirname(dir) if dir else '') or 'noname'

        # If flat is True, add files without directories
        self.flat = flat

        self.tracks = []
        self.subdirs = []

    def empty(self):
        return not self.tracks and not self.subdirs

    def get_all_tracks(self):
        tracks = []
        for track in self.tracks:
            tracks.append(track)
        for subdir in self.subdirs:
            tracks.extend(subdir.get_all_tracks())
        return tracks

    def get_playtime(self):
        time = 0
        for track in self.get_all_tracks():
            time += track.getLength()
        return time

    def export_to_dir(self, outdir):
        import shutil
        sub_outdir = outdir if self.flat else os.path.join(outdir, self.dirname)
        for track in self.tracks:
            src = track.getFilePath()
            if not os.path.exists(src):
                logging.info('Skipping non-existent file %s.' % src)
                continue
            dest = os.path.join(sub_outdir, os.path.basename(src))
            logging.info('Copying %s to %s' % (src, dest))
            tools.makedirs(sub_outdir)
            shutil.copy2(src, dest)
        for subdir in self.subdirs:
            subdir.export_to_dir(sub_outdir)
        if self.flat:
            logging.info('Export finished')

    def __len__(self):
        return len(self.get_all_tracks())

    def __str__(self, indent=0):
        res = ''
        res += '- %s\n' % self.dirname
        for track in self.tracks:
            res += (' ' * indent) + '%s\n' % track
        if self.subdirs:
            for dir in self.subdirs:
                res += (' ' * indent) + '%s' % dir.__str__(indent=indent + 4)
        return res


def preloadTracks(paths):
    '''
    Function for preloading tracks. It is invoked when a dnd action starts
    and preloads the selected tracks in reverse order, so that the tracks are
    loaded, when the real loading function comes to them.
    '''
    for path in reversed(paths):
        if os.path.isdir(path):
            subpaths = [path for (name, path) in tools.listDir(path)]
            preloadTracks(subpaths)
        elif isSupported(path):
            getTrackFromFile(path)


def scanPaths(dir_info, name='', tracks=None):
    if tracks is None:
        tracks = defaultdict(list)

    for (subname, subpath) in dir_info:
        if os.path.isdir(subpath):
            subname = name + ' / ' + subname if name else subname
            tracks.update(scanPaths(tools.listDir(subpath), subname, tracks))
        elif isSupported(subpath):
            track = getTrackFromFile(subpath)
            tracks[name].append(track)
    return tracks


def getTracks(filenames):
    """ Same as getTracksFromFiles(), but works for any kind of filenames (files, playlists, directories) """
    assert isinstance(filenames, list), 'filenames has to be a list'

    tracks = TrackDir(flat=True)

    for path in sorted(filenames):
        if os.path.isdir(path):
            dirname = tools.dirname(path)
            track_dict = scanPaths(tools.listDir(path), name=dirname)
            for name, track_list in sorted(track_dict.items()):
                trackdir = TrackDir(name=name)
                trackdir.tracks = track_list
                tracks.subdirs.append(trackdir)
        elif isSupported(path):
            track = getTrackFromFile(path)
            tracks.tracks.append(track)

    return tracks
