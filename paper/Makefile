# LATEX: pdflatex | xelatex | lualatex
LATEX = lualatex
LATEX_FLAGS = -shell-escape
BIBTEX = bibtex
export TEXMFVAR ?= $(CURDIR)/.texmf-var
export PATH := $(CURDIR)/.python-packages/bin:$(PATH)
export PYTHONPATH := $(CURDIR)/.python-packages:$(PYTHONPATH)

FILES = $(patsubst %.tex, %.pdf, $(wildcard *.tex))

all: $(FILES)


%.pdf: %.tex
	$(LATEX) $(LATEX_FLAGS) $<
	$(LATEX) $(LATEX_FLAGS) $<
	-$(BIBTEX) `basename $< .tex`
	$(LATEX) $(LATEX_FLAGS) $<
	$(LATEX) $(LATEX_FLAGS) $<
	$(LATEX) $(LATEX_FLAGS) $<
	qpdf --warning-exit-0 --linearize --newline-before-endstream $@ /tmp/$@
	mv /tmp/$@ $@

clean:
	-rm -f *.{log,toc,tac,aux,dvi,ps,bbl,blg,tmp,nav,out,snm,vrb,rel,cut,abs,xmpi,xmpdata,*~}
	-rm -rf out _minted* auto
	for i in $(ALLSUBDIRS); do \
	    (cd $$i; make clean) || exit 1; \
	done
	-rm $(FILES)

cleanall: clean
	-rm -rf out auto
