########################################################
#  Makefile for drscl executable under linux
#
#  S. Ritt, Nov. 2016
########################################################

# determine OS
OSTYPE = $(shell uname)

FLAGS         = -g -O3 -Wall -Wuninitialized -Wno-unused-result -DOS_LINUX
FLAGS         += -I../include -I/usr/local/include -I/usr/local/include/libusb-1.0
LIBS          = -lpthread -lutil -lusb-1.0

OBJECTS       = DRS.o averager.o musbstd.o mxml.o strlcpy.o
EXECS         = drscl drs_exam drs_exam_multi

ifeq ($(OSTYPE),Darwin)
FLAGS         += -DHAVE_USB -DHAVE_LIBUSB10
LIBS          += -framework IOKit -framework CoreFoundation -lobjc
else
FLAGS         += -DHAVE_USB -DHAVE_LIBUSB10
endif

all: $(EXECS)

drscl: $(OBJECTS) drscl.o
	$(CXX) $(FLAGS) $(OBJECTS) drscl.o -o drscl $(LIBS)

drs_exam: $(OBJECTS) drs_exam.o
	$(CXX) $(FLAGS) $(OBJECTS) drs_exam.o -o drs_exam $(LIBS)

drs_exam_multi: $(OBJECTS) drs_exam_multi.o
	$(CXX) $(FLAGS) $(OBJECTS) drs_exam_multi.o -o drs_exam_multi $(LIBS)

drscl.o: drscl.cpp ../include/DRS.h
	$(CC) $(FLAGS) -c $<

drs_exam.o: drs_exam.cpp ../include/DRS.h
	$(CC) $(FLAGS) -c $<

drs_exam_multi.o: drs_exam_multi.cpp ../include/DRS.h
	$(CC) $(FLAGS) -c $<

musbstd.o: ../src//musbstd.c ../include/musbstd.h
	$(CC) $(FLAGS) -c $<

DRS.o: ../src/DRS.cpp ../include/DRS.h
	$(CXX) $(FLAGS) -c $<

mxml.o: ../src/mxml.c ../include/mxml.h
	$(CC) $(FLAGS) -c $<

strlcpy.o: ../src/strlcpy.c ../include/strlcpy.h
	$(CC) $(FLAGS) -c $<

averager.o: ../src/averager.cpp ../include/averager.h
	$(CC) $(FLAGS) -c $<

clean:
	rm -f *.o $(EXECS)

