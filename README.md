Sirena - A fast and minimalist audio player for Linux
===================================================

It groups tracks by album, which uses less space and simplifies
rearranging your playlist. Sirena does not organize your tracks in a music
library and does not stream or download tracks. Therefore, it is best
suited for people who store their tracks by album and want a simple way
of playing them. Sirena allows you to quickly search for music on local
drives and in the playlist. It also features an equalizer and displays
covers and desktop notifications.

Sirena is a fork of Pogo a fork Decibel Audio Player and supports most common audio
formats. It is written in Python and uses GTK+ and GStreamer.
Requirements
------------

See `debian/control` for Ubuntu package names.

  * Python (>= 3.2):        https://www.python.org
  * GTK+ (>= 3.0):          https://www.gtk.org
  * GStreamer (>= 1.0):     https://gstreamer.freedesktop.org
  * Mutagen:                https://github.com/quodlibet/mutagen
  * Python DBus:            https://dbus.freedesktop.org
  * Pillow:                 https://github.com/python-pillow/Pillow

Recommended libraries:

  * libnotify               (Desktop notifications)
  * GNOME settings daemon   (GNOME media keys)
  * GStreamer plugins       (Support for various audio formats)


Run Sirena (without installing)
-----------------------------

    ./sirena.py


Install and run Pogo
--------------------

    sudo make install
    sirena

