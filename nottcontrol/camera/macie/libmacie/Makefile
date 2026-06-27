# Makefile for libmacie.a 

# gcc
CC = LD_LIBRARY_PATH=/usr/local/lib/macie_lib CPATH=/usr/local/lib/macie_lib g++
CFLAGS = -O2 -Wall -g -fPIC

all: libmacie.a

SRCS = \
        macie_lib.c \

OBJS = $(SRCS:.c=.o)

libmacie.a: $(OBJS)
	ar r $@ $(OBJS)
	ranlib $@

clean: clobber

clobber:
	rm -rf $(OBJS) libmacie.a

