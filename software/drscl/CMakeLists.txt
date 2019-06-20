cmake_minimum_required(VERSION 3.0)

include_directories(${CMAKE_SOURCE_DIR}/include ${CMAKE_SOURCE_DIR}/mxml)
list(APPEND CMAKE_MODULE_PATH ${CMAKE_SOURCE_DIR}/cmake)
find_package(libusb-1.0 REQUIRED)

set(SRC
   ../src/DRS.cpp
   ../src/averager.cpp
   ../src/musbstd.c
   ../mxml/mxml.cxx
   ../mxml/strlcpy.cxx)
   
add_executable(drscl ${SRC} drscl.cpp)
add_executable(drs_exam ${SRC} drs_exam.cpp)
add_executable(drs_exam_multi ${SRC} drs_exam_multi.cpp)

target_compile_options(drscl PRIVATE -DOS_LINUX -DHAVE_USB -DHAVE_LIBUSB10)
target_include_directories(drscl PRIVATE ${LIBUSB_1_INCLUDE_DIRS})
target_link_libraries(drscl ${LIBUSB_1_LIBRARIES})

target_compile_options(drs_exam PRIVATE -DOS_LINUX -DHAVE_USB -DHAVE_LIBUSB10)
target_include_directories(drs_exam PRIVATE ${LIBUSB_1_INCLUDE_DIRS})
target_link_libraries(drs_exam ${LIBUSB_1_LIBRARIES})

target_compile_options(drs_exam_multi PRIVATE -DOS_LINUX -DHAVE_USB -DHAVE_LIBUSB10)
target_include_directories(drs_exam_multi PRIVATE ${LIBUSB_1_INCLUDE_DIRS})
target_link_libraries(drs_exam_multi ${LIBUSB_1_LIBRARIES})

install(TARGETS drscl drs_exam drs_exam_multi DESTINATION bin)
