cmake_minimum_required(VERSION 3.0)

execute_process(COMMAND wx-config --cxxflags OUTPUT_VARIABLE WX_CXXFLAGS)
separate_arguments(WX_CXXFLAGS UNIX_COMMAND ${WX_CXXFLAGS})
execute_process(COMMAND wx-config --libs OUTPUT_VARIABLE WX_LIBS)
string(STRIP ${WX_LIBS} WX_LIBS)

list(APPEND CMAKE_MODULE_PATH ${CMAKE_SOURCE_DIR}/cmake)
find_package(libusb-1.0 REQUIRED)

set(LIBSRC
   ../src/DRS.cpp
   ../src/averager.cpp
   ../src/musbstd.c
   ../mxml/mxml.cxx
   ../mxml/strlcpy.cxx)

set(SRC
   ConfigDialog.cpp
   DOFrame.cpp
   DOScreen.cpp
   DRSOsc.cpp
   MeasureDialog.cpp
   Measurement.cpp
   Osci.cpp
   EPThread.cpp
   DisplayDialog.cpp
   InfoDialog.cpp
   AboutDialog.cpp
   TriggerDialog.cpp
   rb.cpp
   main.cpp)

add_executable(drsosc ${SRC} ${LIBSRC})

target_compile_options(drsosc PRIVATE 
   -Wno-deprecated-declarations
   -DOS_LINUX -DHAVE_USB -DHAVE_LIBUSB10 -DUSE_DRS_MUTEX)
target_compile_options(drsosc PRIVATE ${WX_CXXFLAGS})

target_include_directories(drsosc PRIVATE 
   ${CMAKE_SOURCE_DIR}/include 
   ${CMAKE_SOURCE_DIR}/mxml
   ${LIBUSB_1_INCLUDE_DIRS})
target_link_libraries(drsosc ${LIBUSB_1_LIBRARIES} ${WX_LIBS})

target_link_options(drsosc PRIVATE -L/opt/local/lib)

set_target_properties(drsosc PROPERTIES
   MACOSX_BUNDLE ON
   MACOSX_BUNDLE_BUNDLE_NAME "DRSOsc"
   MACOSC_BUNDLE_BUNDLE_IDENTIFIER "PSI.DRSOsc")

install(TARGETS drsosc DESTINATION bin)
