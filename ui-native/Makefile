CC ?= cc
PKGS := gtk+-3.0 json-glib-1.0 libcurl
CFLAGS ?= -O2 -Wall
CFLAGS += $(shell pkg-config --cflags $(PKGS))
LIBS := $(shell pkg-config --libs $(PKGS)) -lm

silisten-ui: main.c
	$(CC) $(CFLAGS) -o $@ main.c $(LIBS)

clean:
	rm -f silisten-ui

.PHONY: clean
