cmake_minimum_required(VERSION 3.0)

project(DRS4EB)

set(CMAKE_INSTALL_PREFIX ${CMAKE_SOURCE_DIR})
message(STATUS "CMAKE_INSTALL_PREFIX: ${CMAKE_INSTALL_PREFIX}")

add_subdirectory(drscl)
add_subdirectory(drsosc)
