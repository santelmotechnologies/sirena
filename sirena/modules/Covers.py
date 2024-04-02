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
import os
import traceback

from sirena import modules
from sirena import tools
from sirena.tools import consts, prefs
from sirena.tools.log import logger


# Module information
MOD_INFO = ('Covers', _('Covers'), _('Show album covers'), [], False, True)
MOD_NAME = MOD_INFO[modules.MODINFO_NAME]

AS_API_KEY = '4d7befd13245afcc73f9ed7518b6619a'  # Jendrik Seipp's Audioscrobbler API key
AS_TAG_START = '<image size="large">'            # The text that is right before the URL to the cover
AS_TAG_END = '</image>'                          # The text that is right after the URL to the cover

# It seems that a non standard 'user-agent' header may cause problem, so let's cheat
USER_AGENT = 'Mozilla/5.0 (X11; U; Linux i686; en-US; rv:1.9.0.1) Gecko/2008072820 Firefox/3.0.1'

# We store both the paths to the thumbnail and to the full size image
(
    CVR_THUMB,
    CVR_FULL
) = list(range(2))

# Constants for thumbnails
THUMBNAIL_WIDTH = 100  # Width allocated to thumbnails in the model
THUMBNAIL_HEIGHT = 100  # Height allocated to thumbnails in the model

# Constants for full size covers
FULL_SIZE_COVER_WIDTH = 300
FULL_SIZE_COVER_HEIGHT = 300

# File formats we can read
ACCEPTED_FILE_FORMATS = {'.jpg': None, '.jpeg': None, '.png': None, '.gif': None}

# Default preferences
PREFS_DFT_DOWNLOAD_COVERS = True
PREFS_DFT_PREFER_USER_COVERS = True
PREFS_DFT_USER_COVER_FILENAMES = ['folder', 'cover', 'art', 'front', '*']


class Covers(modules.ThreadedModule):

    def __init__(self):
        """ Constructor """
        handlers = {
            consts.MSG_EVT_APP_QUIT: self.onModUnloaded,
            consts.MSG_EVT_NEW_TRACK: self.onNewTrack,
            consts.MSG_EVT_MOD_LOADED: self.onModLoaded,
            consts.MSG_EVT_APP_STARTED: self.onModLoaded,
            consts.MSG_EVT_MOD_UNLOADED: self.onModUnloaded,
        }

        modules.ThreadedModule.__init__(self, handlers)

    def _generateCover(self, inFile, outFile, format, max_width, max_height):
        from PIL import Image

        try:
            # Open the image
            cover = Image.open(inFile)
            width = cover.size[0]
            height = cover.size[1]
            newWidth, newHeight = tools.resize(width, height, max_width, max_height)

            cover = cover.resize((newWidth, newHeight), Image.ANTIALIAS)
            cover.save(outFile, format)
        except Exception:
            # This message will probably be displayed for the thumbnail and the big cover.
            logger.error('[%s] An error occurred while generating the cover for "%s"\n\n%s' %
                         (MOD_NAME, inFile, traceback.format_exc()))
            # Remove corrupted file.
            tools.remove(outFile)

    def generateFullSizeCover(self, inFile, outFile, format):
        """ Resize inFile if needed, and write it to outFile (outFile and inFile may be equal) """
        self._generateCover(inFile, outFile, format, FULL_SIZE_COVER_WIDTH,
                            FULL_SIZE_COVER_HEIGHT)

    def generateThumbnail(self, inFile, outFile, format):
        """
        Generate a thumbnail from inFile (e.g., resize it) and write it to
        outFile (outFile and inFile may be equal).
        """
        self._generateCover(inFile, outFile, format, THUMBNAIL_WIDTH, THUMBNAIL_HEIGHT)

    def getUserCover(self, trackPath):
        """ Return the path to a cover file in trackPath, None if no cover found """
        # Create a dictionary with candidates
        candidates = {}
        for (file, path) in tools.listDir(trackPath, True):
            (name, ext) = os.path.splitext(file.lower())
            if ext in ACCEPTED_FILE_FORMATS:
                candidates[name] = path

        # Check each possible name using the its index in the list as its priority
        for name in prefs.get(__name__, 'user-cover-filenames', PREFS_DFT_USER_COVER_FILENAMES):
            if name in candidates:
                return candidates[name]

            if name == '*' and len(candidates) != 0:
                return next(iter(candidates.values()))

        return None

    def getFromCache(self, artist, album):
        """ Return the path to the cached cover, or None if it's not cached """
        cachePath = os.path.join(self.cacheRootPath, str(abs(hash(artist))))
        cacheIdxPath = os.path.join(cachePath, 'INDEX')

        try:
            cacheIdx = tools.pickleLoad(cacheIdxPath)
            cover = os.path.join(cachePath, cacheIdx[artist + album])
            if os.path.exists(cover):
                return cover
        except:
            pass

        return None

    def __getFromInternet(self, artist, album):
        """
            Try to download the cover from the Internet
            If successful, add it to the cache and return the path to it
            Otherwise, return None
        """
        import urllib.request
        import urllib.error
        import urllib.parse
        import socket

        # Make sure to not be blocked by the request
        socket.setdefaulttimeout(consts.socketTimeout)

        # Request information to Last.fm
        # Beware of UTF-8 characters: we need to percent-encode all characters
        try:
            url = ('http://ws.audioscrobbler.com/2.0/?method=album.getinfo&api_key=%s&artist=%s&album=%s' %
                   (AS_API_KEY, tools.percentEncode(artist), tools.percentEncode(album)))
            request = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
            stream = urllib.request.urlopen(request)
            data = stream.read().decode('utf-8')
        except urllib.error.HTTPError as err:
            if err.code == 400:
                logger.error('[%s] No known cover for %s / %s' % (MOD_NAME, artist, album))
            else:
                logger.error('[%s] Information request failed\n\n%s' % (MOD_NAME, traceback.format_exc()))
            return None
        except urllib.error.URLError:
            logger.info('[%s] Could not fetch cover. No internet connection.' % MOD_NAME)
            return None
        except:
            logger.error('[%s] Information request failed\n\n%s' % (MOD_NAME, traceback.format_exc()))
            return None

        # Extract the URL to the cover image
        malformed = True
        startIdx = data.find(AS_TAG_START)
        endIdx = data.find(AS_TAG_END, startIdx)
        if startIdx != -1 and endIdx != -1:
            coverURL = data[startIdx + len(AS_TAG_START):endIdx]
            coverFormat = os.path.splitext(coverURL)[1].lower()
            if coverURL.startswith(('http://', 'https://')) and coverFormat in ACCEPTED_FILE_FORMATS:
                malformed = False

        if malformed:
            # Do not show the data in the log every time no cover is found
            if coverURL:
                logger.error('[%s] Received malformed data\n\n%s' % (MOD_NAME, data))
            return None

        # Download the cover image
        try:
            request = urllib.request.Request(coverURL, headers={'User-Agent': USER_AGENT})
            stream = urllib.request.urlopen(request)
            data = stream.read()

            if len(data) < 1024:
                raise Exception('The cover image seems incorrect (%u bytes is too small)' % len(data))
        except:
            logger.error('[%s] Cover image request failed' % MOD_NAME)
            return None

        # So far, so good: let's cache the image
        cachePath = os.path.join(self.cacheRootPath, str(abs(hash(artist))))
        cacheIdxPath = os.path.join(cachePath, 'INDEX')

        if not os.path.exists(cachePath):
            os.mkdir(cachePath)

        try:
            cacheIdx = tools.pickleLoad(cacheIdxPath)
        except:
            cacheIdx = {}

        nextInt = len(cacheIdx) + 1
        filename = str(nextInt) + coverFormat
        coverPath = os.path.join(cachePath, filename)

        cacheIdx[artist + album] = filename
        tools.pickleSave(cacheIdxPath, cacheIdx)

        try:
            output = open(coverPath, 'wb')
            output.write(data)
            output.close()
            return coverPath
        except:
            logger.error('[%s] Could not save the downloaded cover\n\n%s' % (MOD_NAME, traceback.format_exc()))

        return None

    def getFromInternet(self, artist, album):
        """ Wrapper for __getFromInternet(), manage blacklist """
        # If we already tried without success, don't try again
        if (artist, album) in self.coverBlacklist:
            return None

        # Otherwise, try to download the cover
        cover = self.__getFromInternet(artist, album)

        # If the download failed, blacklist the album
        if cover is None:
            self.coverBlacklist[(artist, album)] = None

        return cover

    # --== Message handlers ==--

    def onModLoaded(self):
        """ The module has been loaded """
        self.cfgWin = None  # Configuration window
        self.coverMap = {}  # Store covers previously requested
        self.currTrack = None  # The current track being played, if any
        self.cacheRootPath = os.path.join(consts.dirCfg, MOD_NAME)  # Local cache for Internet covers
        self.coverBlacklist = {}  # When a cover cannot be downloaded, avoid requesting it again

        if not os.path.exists(self.cacheRootPath):
            os.mkdir(self.cacheRootPath)

    def onModUnloaded(self):
        """ The module has been unloaded """
        if self.currTrack is not None:
            modules.postMsg(consts.MSG_CMD_SET_COVER, {'track': self.currTrack, 'pathThumbnail': None, 'pathFullSize': None})

        # Delete covers that have been generated by this module
        for covers in self.coverMap.values():
            if os.path.exists(covers[CVR_THUMB]):
                os.remove(covers[CVR_THUMB])
            if os.path.exists(covers[CVR_FULL]):
                os.remove(covers[CVR_FULL])
        self.coverMap = None

        # Delete blacklist
        self.coverBlacklist = None

    def onNewTrack(self, track):
        """ A new track is being played, try to retrieve the corresponding cover """
        # Make sure we have enough information
        if track.getArtist() == consts.UNKNOWN_ARTIST or track.getAlbum() == consts.UNKNOWN_ALBUM:
            modules.postMsg(consts.MSG_CMD_SET_COVER, {'track': track, 'pathThumbnail': None, 'pathFullSize': None})
            return

        album = track.getAlbum().lower()
        artist = track.getArtist().lower()
        rawCover = None
        self.currTrack = track

        # Let's see whether we already have the cover
        if (artist, album) in self.coverMap:
            covers = self.coverMap[(artist, album)]
            pathFullSize = covers[CVR_FULL]
            pathThumbnail = covers[CVR_THUMB]

            # Make sure the files are still there
            if os.path.exists(pathThumbnail) and os.path.exists(pathFullSize):
                modules.postMsg(
                    consts.MSG_CMD_SET_COVER,
                    {'track': track, 'pathThumbnail': pathThumbnail, 'pathFullSize': pathFullSize})
                return

        # Should we check for a user cover?
        if (not prefs.get(__name__, 'download-covers', PREFS_DFT_DOWNLOAD_COVERS) or
                prefs.get(__name__, 'prefer-user-covers', PREFS_DFT_PREFER_USER_COVERS)):
            rawCover = self.getUserCover(os.path.dirname(track.getFilePath()))

        # Is it in our cache?
        if rawCover is None:
            rawCover = self.getFromCache(artist, album)

        # If we still don't have a cover, maybe we can try to download it
        if rawCover is None:
            modules.postMsg(
                consts.MSG_CMD_SET_COVER,
                {'track': track, 'pathThumbnail': None, 'pathFullSize': None})

            if prefs.get(__name__, 'download-covers', PREFS_DFT_DOWNLOAD_COVERS):
                rawCover = self.getFromInternet(artist, album)

        # If we still don't have a cover, too bad
        # Otherwise, generate a thumbnail and a full size cover, and add it to our cover map
        if rawCover is not None:
            import tempfile

            thumbnail = tempfile.mktemp() + '.png'
            fullSizeCover = tempfile.mktemp() + '.png'
            self.generateThumbnail(rawCover, thumbnail, 'PNG')
            self.generateFullSizeCover(rawCover, fullSizeCover, 'PNG')
            if os.path.exists(thumbnail) and os.path.exists(fullSizeCover):
                self.coverMap[(artist, album)] = (thumbnail, fullSizeCover)
                modules.postMsg(
                    consts.MSG_CMD_SET_COVER,
                    {'track': track, 'pathThumbnail': thumbnail, 'pathFullSize': fullSizeCover})
            else:
                modules.postMsg(
                    consts.MSG_CMD_SET_COVER,
                    {'track': track, 'pathThumbnail': None, 'pathFullSize': None})

    # --== Configuration ==--

    def configure(self, parent):
        """ Show the configuration window """
        if self.cfgWin is None:
            from sirena.gui.window import Window

            self.cfgWin = Window('Covers.ui', 'vbox1', __name__, MOD_INFO[modules.MODINFO_L10N], 320, 265)
            self.cfgWin.getWidget('btn-ok').connect('clicked', self.onBtnOk)
            self.cfgWin.getWidget('img-lastfm').set_from_file(os.path.join(consts.dirPix, 'audioscrobbler.png'))
            self.cfgWin.getWidget('btn-help').connect('clicked', self.onBtnHelp)
            self.cfgWin.getWidget('chk-downloadCovers').connect('toggled', self.onDownloadCoversToggled)
            self.cfgWin.getWidget('btn-cancel').connect('clicked', lambda btn: self.cfgWin.hide())

        if not self.cfgWin.isVisible():
            downloadCovers = prefs.get(__name__, 'download-covers', PREFS_DFT_DOWNLOAD_COVERS)
            preferUserCovers = prefs.get(__name__, 'prefer-user-covers', PREFS_DFT_PREFER_USER_COVERS)
            userCoverFilenames = prefs.get(__name__, 'user-cover-filenames', PREFS_DFT_USER_COVER_FILENAMES)

            self.cfgWin.getWidget('btn-ok').grab_focus()
            self.cfgWin.getWidget('txt-filenames').set_text(', '.join(userCoverFilenames))
            self.cfgWin.getWidget('chk-downloadCovers').set_active(downloadCovers)
            self.cfgWin.getWidget('chk-preferUserCovers').set_active(preferUserCovers)
            self.cfgWin.getWidget('chk-preferUserCovers').set_sensitive(downloadCovers)

        self.cfgWin.show()

    def onBtnOk(self, btn):
        """ Save configuration """
        downloadCovers = self.cfgWin.getWidget('chk-downloadCovers').get_active()
        preferUserCovers = self.cfgWin.getWidget('chk-preferUserCovers').get_active()
        userCoverFilenames = [word.strip() for word in self.cfgWin.getWidget('txt-filenames').get_text().split(',')]

        prefs.set(__name__, 'download-covers', downloadCovers)
        prefs.set(__name__, 'prefer-user-covers', preferUserCovers)
        prefs.set(__name__, 'user-cover-filenames', userCoverFilenames)

        self.cfgWin.hide()

    def onDownloadCoversToggled(self, downloadCovers):
        """ Toggle the "prefer user covers" checkbox according to the state of the "download covers" one """
        self.cfgWin.getWidget('chk-preferUserCovers').set_sensitive(downloadCovers.get_active())

    def onBtnHelp(self, btn):
        """ Display a small help message box """
        from sirena.gui import help

        helpDlg = help.HelpDlg(MOD_INFO[modules.MODINFO_L10N])
        helpDlg.addSection(_('Description'),
                           _('This module displays the cover of the album the current track comes from. Covers '
                             'may be loaded from local pictures, located in the same directory as the current '
                             'track, or may be downloaded from the Internet.'))
        helpDlg.addSection(_('User Covers'),
                           _('A user cover is a picture located in the same directory as the current track. '
                             'When specifying filenames, you do not need to provide file extensions, supported '
                             'file formats (%s) are automatically used.' % ', '.join(ACCEPTED_FILE_FORMATS.keys())))
        helpDlg.addSection(_('Internet Covers'),
                           _('Covers may be downloaded from the Internet, based on the tags of the current track. '
                             'You can ask to always prefer user covers to Internet ones. In this case, if a user '
                             'cover exists for the current track, it is used. If there is none, the cover is downloaded.'))
        helpDlg.show(self.cfgWin)
