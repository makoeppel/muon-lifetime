cmake_minimum_required(VERSION 3.0)

set(CMAKE_INSTALL_PREFIX ${CMAKE_SOURCE_DIR})
message(STATUS "CMAKE_INSTALL_PREFIX: ${CMAKE_INSTALL_PREFIX}")

include_directories(${CMAKE_SOURCE_DIR}/include)
list(APPEND CMAKE_MODULE_PATH ${CMAKE_SOURCE_DIR}/cmake)
find_package(libusb-1.0 REQUIRED)

set(LIBSRC
   ../src/DRS.cpp
   ../src/averager.cpp
   ../src/musbstd.c
   ../src/mxml.c
   ../src/strlcpy.c)

set(SRC
   ConfigDialog
   DOFrame
   DOScreen
   DRSOsc
   MeasureDialog
   Measurement
   Osci
   EPThread
   DisplayDialog
   InfoDialog
   AboutDialog
   TriggerDialog)

add_executable(drsosc ${SRC} ${LIBSRC})

target_compile_options(drsosc PRIVATE -DOS_LINUX -DHAVE_USB -DHAVE_LIBUSB10)
target_include_directories(drsosc PRIVATE ${LIBUSB_1_INCLUDE_DIRS})
target_link_libraries(drsosc ${LIBUSB_1_LIBRARIES})

install(TARGETS drsosc DESTINATION bin)
