INSTALL ?= install

PYFILES = $(shell find ../sirena -type f -name "*.py")
UIFILES = $(wildcard ../res/*.ui)
POFILES = $(wildcard *.po)

UIHFILES := $(UIFILES:.ui=.ui.h)

help:
	@echo USAGE:
	@echo "make update - updates sirena.pot and .po files"
	@echo "make dist   - creates .mo files in ../locale dir"
	@echo "make pl.po  - updates pl.po file OR creates new one"
	@echo "              (replace 'pl' with your language code)"

%.h: %
	intltool-extract --type="gettext/glade" $*
	sed -i '/^char \*s = N_("gtk-.*");$$/d' $@


sirena.pot: $(UIHFILES) $(PYFILES)
	xgettext -k_ -kN_ -o sirena.pot $(PYFILES) $(UIHFILES) --from-code=utf-8

%.po: sirena.pot
	@if test -f $@; then \
		echo -n "Updating '$*' language ";\
		msgmerge --update --backup=none $@ sirena.pot; \
	else \
		msginit -l $*.UTF8 -o $@; \
	fi

%.mo:
	for pofile in $(patsubst ../locale/%/LC_MESSAGES/sirena.mo,%.po,$@); do \
		${INSTALL} -m 755 -d $(subst sirena.mo,,$@);\
		msgconv -t UTF-8 $${pofile} -o $${pofile}_utf8;\
		msgfmt $${pofile}_utf8 -o $@;\
		rm $${pofile}_utf8;\
	done

update: $(POFILES)
dist: $(POFILES:%.po=../locale/%/LC_MESSAGES/sirena.mo)

clean:
	$(RM) $(UIHFILES)
	$(RM) $(POFILES:%.po=../locale/%/LC_MESSAGES/sirena.mo)
	#$(RM) sirena.pot

.PHONY:  update
