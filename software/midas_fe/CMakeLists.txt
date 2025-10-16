cmake_minimum_required(VERSION 3.0)

include_directories(${CMAKE_SOURCE_DIR}/include ${CMAKE_SOURCE_DIR}/mxml)
list(APPEND CMAKE_MODULE_PATH ${CMAKE_SOURCE_DIR}/cmake)
find_package(libusb-1.0 REQUIRED)

set(SRC
   ../src/DRS.cpp
   ../src/averager.cpp
   ../src/musbstd.c
   ../src/strlcpy.cxx
   ../mxml/mxml.cxx)

add_executable(drs4_fe ${SRC} drs4_fe.cpp)

target_compile_options(drs4_fe PRIVATE -DOS_LINUX -DHAVE_USB -DHAVE_LIBUSB10)
target_include_directories(drs4_fe PRIVATE ${LIBUSB_1_INCLUDE_DIRS})
target_link_libraries(drs4_fe ${LIBUSB_1_LIBRARIES} midas::mfed)

install(TARGETS drs4_fe DESTINATION bin)
