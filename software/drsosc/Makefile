########################################################
#
#  Makefile for drsosc executable under linux
#
#  Requires wxWidgets 2.8.9 or newer
#
#  S. Ritt, Nov. 2016
########################################################

# determine OS
OSTYPE = $(shell uname)

# check if wxWidgets is installed
HAVE_WX       = $(shell which wx-config)
ifeq ($(HAVE_WX),)
$(error Error: wxWidgets required to compile "drsosc")
endif

CFLAGS        = -g -O2 -Wall -Wuninitialized -Wno-unused-result -fno-strict-aliasing -DHAVE_USB -DHAVE_LIBUSB10 -DUSE_DRS_MUTEX
CFLAGS        += -I../include -I../ -I/usr/local/include
WXFLAGS       = $(shell wx-config --cxxflags)
LIBS          = -L/usr/local/lib -lpthread -lutil
LIBS          += $(shell wx-config --libs)

WX_OBJ        = ConfigDialog.o DOFrame.o DOScreen.o DRSOsc.o MeasureDialog.o Measurement.o Osci.o EPThread.o DisplayDialog.o InfoDialog.o AboutDialog.o TriggerDialog.o
OBJECTS       = main.o musbstd.o DRS.o rb.o averager.o mxml.o strlcpy.o $(WX_OBJ)

OUTNAME       = drsosc

# OS specific flags
ifeq ($(OSTYPE),Darwin)
CFLAGS        += -DOS_DARWIN -stdlib=libstdc++
LIBS          += -lusb-1.0
endif

ifeq ($(OSTYPE),Linux)
CFLAGS        += -DOS_LINUX
LIBS          += -lusb-1.0
endif

all: $(OUTNAME) read_binary
app: DRSOsc.app

$(OUTNAME): $(OBJECTS)
	$(CXX) $(CFLAGS) $(OBJECTS) -o $(OUTNAME) $(LIBS)

DRSOsc.app: drsosc
	-mkdir DRSOsc.app
	-mkdir DRSOsc.app/Contents
	-mkdir DRSOsc.app/Contents/MacOS
	-mkdir DRSOsc.app/Contents/Resources
	-mkdir DRSOsc.app/Contents/Resources/English.lproj
	echo 'APPL????' > DRSOsc.app/Contents/PkgInfo
	cp drsosc.xcodeproj/Info-processed.plist DRSOsc.app/Contents/Info.plist
	cp drsosc DRSOsc.app/Contents/MacOS/DRSOsc
	cp DRSOsc.icns DRSOsc.app/Contents/Resources

read_binary: read_binary.cpp
	$(CXX) $(CFLAGS)  -o $@ $<

main.o: %.o: %.cpp ../include/mxml.h ../include/DRS.h
	$(CXX) $(CFLAGS) $(WXFLAGS) -c $<

musbstd.o: ../src/musbstd.c ../include/musbstd.h
	$(CC) $(CFLAGS) -c $<

DRS.o: ../src/DRS.cpp ../include/DRS.h
	$(CXX) $(CFLAGS) $(WXFLAGS) -c $<

rb.o: rb.cpp rb.h
	$(CXX) $(CFLAGS) -c $<

averager.o: ../src/averager.cpp ../include/averager.h
	$(CXX) $(CFLAGS) -c $<

mxml.o: ../src/mxml.c ../include/mxml.h
	$(CC) $(CFLAGS) -c $<

strlcpy.o: ../src/strlcpy.c ../include/strlcpy.h
	$(CC) $(CFLAGS) -c $<

$(WX_OBJ): %.o: %.cpp %.h ../include/mxml.h ../include/DRS.h
	$(CXX) $(CFLAGS) $(WXFLAGS) -c $<

clean:
	rm -f *.o $(OUTNAME) read_binary

