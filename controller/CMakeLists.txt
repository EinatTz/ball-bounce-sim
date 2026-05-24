cmake_minimum_required(VERSION 3.14)
project(paddle_controller LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

# Position-independent code so the static lib can be linked into shared libs
# (e.g. a pybind11 module) as well.
set(CMAKE_POSITION_INDEPENDENT_CODE ON)

if(NOT CMAKE_BUILD_TYPE)
    set(CMAKE_BUILD_TYPE Release)
endif()

if(MSVC)
    add_compile_options(/W4 /permissive-)
else()
    add_compile_options(-Wall -Wextra -Wpedantic)
endif()

# Static library — convenient for embedding in C++/Rust simulators.
add_library(paddle_controller STATIC controller.cpp)
target_include_directories(paddle_controller PUBLIC ${CMAKE_CURRENT_SOURCE_DIR})

# Shared library — convenient for FFI from Python (ctypes/cffi).
add_library(paddle_controller_shared SHARED controller.cpp)
target_include_directories(paddle_controller_shared PUBLIC ${CMAKE_CURRENT_SOURCE_DIR})
set_target_properties(paddle_controller_shared PROPERTIES
    OUTPUT_NAME paddle_controller)

# Smoke test binary.
add_executable(controller_smoke_test controller_smoke_test.cpp)
target_link_libraries(controller_smoke_test PRIVATE paddle_controller)
