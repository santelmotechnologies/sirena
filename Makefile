INSTALL ?= install
MAKE ?= make
RM ?= rm
RMDIR ?= rmdir
prefix ?= /usr


PREFIX = $(DESTDIR)$(prefix)

BINDIR = $(PREFIX)/bin
MANDIR = $(PREFIX)/share/man/man1
DATADIR = $(PREFIX)/share/sirena
SRCDIR = $(DATADIR)/sirena
PIXDIR = $(DATADIR)/pix
RESDIR = $(DATADIR)/res

APPDIR = $(PREFIX)/share/applications
ICONDIR = $(PREFIX)/share/pixmaps
LOCALEDIR = $(PREFIX)/share/locale

CONFIGURE_IN = sed -e "s!prefix = '/usr'!prefix = '$(prefix)'!g"

LANGUAGES = `find locale/ -maxdepth 1 -mindepth 1 -type d -printf "%f "`

help:
	@echo Usage:
	@echo "make           - not used"
	@echo "make clean     - removes temporary data"
	@echo "make install   - installs data"
	@echo "make uninstall - uninstalls data"
	@echo "make test      - runs tests"
	@echo "make help      - prints this help"
	@echo

install:
	cat sirena.py | $(CONFIGURE_IN) > script;
	echo $(PREFIX)
	$(INSTALL) -m 755 -d $(BINDIR) $(MANDIR) $(DATADIR) $(SRCDIR) $(RESDIR) $(APPDIR) $(PIXDIR) $(ICONDIR)
	$(INSTALL) -m 755 -d $(SRCDIR)/gui
	$(INSTALL) -m 755 -d $(SRCDIR)/media
	$(INSTALL) -m 755 -d $(SRCDIR)/media/format
	$(INSTALL) -m 755 -d $(SRCDIR)/media/track
	$(INSTALL) -m 755 -d $(SRCDIR)/tools
	$(INSTALL) -m 755 -d $(SRCDIR)/modules
	$(INSTALL) -m 644 sirena/*.py $(SRCDIR)
	$(INSTALL) -m 644 sirena/gui/*.py $(SRCDIR)/gui
	$(INSTALL) -m 644 sirena/tools/*.py $(SRCDIR)/tools
	$(INSTALL) -m 644 sirena/media/*.py $(SRCDIR)/media
	$(INSTALL) -m 644 sirena/media/track/*.py $(SRCDIR)/media/track
	$(INSTALL) -m 644 sirena/media/format/*.py $(SRCDIR)/media/format
	$(INSTALL) -m 644 sirena/modules/*.py $(SRCDIR)/modules
	$(INSTALL) -m 644 res/*.ui $(RESDIR)
	$(INSTALL) -m 644 res/sirena.1 $(MANDIR)
	$(INSTALL) -m 644 pix/*.png $(PIXDIR)
	$(INSTALL) -m 644 pix/sirena.png $(ICONDIR)
	$(INSTALL) -m 644 res/sirena.desktop $(APPDIR)
	if test -L $(BINDIR)/sirena; then ${RM} $(BINDIR)/sirena; fi
	$(INSTALL) -m 755 script $(BINDIR)/sirena
	$(MAKE) -C po dist
	for lang in $(LANGUAGES); do \
		${INSTALL} -m 755 -d $(LOCALEDIR)/$$lang/LC_MESSAGES;\
		$(INSTALL) -m 644 locale/$$lang/LC_MESSAGES/sirena.mo $(LOCALEDIR)/$$lang/LC_MESSAGES/; \
	done

uninstall:
	${RM} $(BINDIR)/sirena
	${RM} $(APPDIR)/sirena.desktop
	${RM} $(MANDIR)/sirena.1
	${RM} $(ICONDIR)/sirena.png
	${RM} -rf $(DATADIR)
	$(RMDIR) --ignore-fail-on-non-empty $(BINDIR) $(MANDIR) $(APPDIR)
	for lang in $(LANGUAGES); do \
		${RM} $(LOCALEDIR)/$$lang/LC_MESSAGES/sirena.mo; \
	done

clean:
	$(MAKE) -C po clean
	${RM} sirena/*.py[co] res/*~ res/*.bak
	${RM} script

test:
	pyflakes sirena sirena.py
	# Ignore middle-of-file imports, bare excepts and line breaks after binary operators.
	pycodestyle --ignore E402,E722,W504 --max-line-length=130 benchmarks sirena sirena.py
	dev/find-dead-code

.PHONY: help clean install test
