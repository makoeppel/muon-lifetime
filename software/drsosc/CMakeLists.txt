cmake_minimum_required(VERSION 3.0)

set(CMAKE_INSTALL_PREFIX ${CMAKE_SOURCE_DIR})
message(STATUS "CMAKE_INSTALL_PREFIX: ${CMAKE_INSTALL_PREFIX}")

execute_process(COMMAND wx-config --cxxflags OUTPUT_VARIABLE WX_CXXFLAGS)
separate_arguments(WX_CXXFLAGS UNIX_COMMAND ${WX_CXXFLAGS})
execute_process(COMMAND wx-config --libs OUTPUT_VARIABLE WX_LIBS)
string(STRIP ${WX_LIBS} WX_LIBS)
message(STATUS "--cxxflags: " ${WX_CXXFLAGS})
message(STATUS "--libs: " ${WX_LIBS})

list(APPEND CMAKE_MODULE_PATH ${CMAKE_SOURCE_DIR}/cmake)
find_package(libusb-1.0 REQUIRED)

set(LIBSRC
   ../src/DRS.cpp
   ../src/averager.cpp
   ../src/musbstd.c
   ../mxml/mxml.cxx
   ../mxml/strlcpy.cxx)

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
   TriggerDialog
   rb
   main)

add_executable(drsosc ${SRC} ${LIBSRC})

target_compile_options(drsosc PRIVATE 
   -Wno-deprecated-declarations
   -DOS_LINUX -DHAVE_USB -DHAVE_LIBUSB10)
target_compile_options(drsosc PRIVATE ${WX_CXXFLAGS})

target_include_directories(drsosc PRIVATE 
   ${CMAKE_SOURCE_DIR}/include 
   ${CMAKE_SOURCE_DIR}/mxml
   ${LIBUSB_1_INCLUDE_DIRS})
target_link_libraries(drsosc ${LIBUSB_1_LIBRARIES} ${WX_LIBS})

target_link_options(drsosc PRIVATE -L/opt/local/lib)

install(TARGETS drsosc DESTINATION bin)
