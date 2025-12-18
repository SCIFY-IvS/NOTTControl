CC = g++

SHELL = /bin/bash

CFLAGS = -O2 -Wall -g -I../libmacie -fPIC
LDFLAGS = -L../libmacie -L/usr/local/lib/macie_lib
LIBS = -lmacie -lMACIE -lcfitsio -lreadline
SRCS = macie_interface.c MacieMain.c
OBJS = macie_interface.o MacieMain.o

DEST = bin
EXE = macie_acq

LINK.c := $(CC) $(CFLAGS) $(LDFLAGS) $(LIBS) -static-libstdc++

all: libmacie_interface.so
libmacie_interface.so: macie_interface.o MacieMain.o
	$(CC) $(CFLAGS) $(LDFLAGS) $^ $(LIBS) -static-libstdc++ -shared -o $@

# Rule showing which targets to build when you simply do "make".
pass5: $(EXE)

install: $(DEST) $(EXE)
	@ if [ -n "$(EXE)" ]; then cp -f $(EXE) $(DEST); fi

$(EXE): MacieMain.o
	$(CC) -o $@ $(CFLAGS) $(LDFLAGS) MacieMain.o $(LIBS)

$(DEST):
	mkdir -p $(DEST)

.c.o:
	$(CC) $(CFLAGS) -c $< -o $@

clean: clobber

clobber:
	rm -rf $(EXE) $(OBJS) libmacie_interface.so
