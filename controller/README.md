# Paddle Controller (Provided Module)

This directory contains the paddle controller you must integrate into your simulator. **Do not modify these files.**

## Contents

* `controller.h` — C ABI for the controller. This is the interface you must use.
* `controller.cpp` — Implementation. Provided for transparency; treat it as a black box.
* `controller\_smoke\_test.cpp` — Standalone driver that exercises the controller with synthetic inputs.
* `CMakeLists.txt` — Build script producing a static library, a shared library, and the smoke test binary.

## Build

You need a C++17 compiler and CMake ≥ 3.14.

```bash
cd controller
mkdir build
cd build
cmake ..
cmake --build .
```

This produces:

* `libpaddle\_controller.a` — static library (link from C++/Rust)
* `libpaddle\_controller.{so,dylib,dll}` — shared library (load from Python via ctypes/cffi, etc.)
* `controller\_smoke\_test` — standalone test executable

## Verify the build

Run the smoke test: (may be in a debug folder depending on OS)

```bash
./controller\_smoke\_test
```

You should see a table of synthetic ball states and paddle commands, ending with a line reporting the detected peak (actual value wont match the expected, this is OK). If the smoke test runs to completion, your build is good.

## Integration notes

* The interface is plain C (`extern "C"` in the header). All language FFI mechanisms that can call C functions can call this controller.
* All types in the interface are primitives (`double`, opaque pointer, a plain-old-data config struct). No exceptions cross the boundary.
* Memory ownership: `controller\_create` returns a pointer that must be released with `controller\_destroy`. Do not free it any other way.
* The controller assumes `controller\_tick` is invoked at exactly the `tick\_rate\_hz` you passed at creation. The integral and derivative terms use that rate as a constant `dt`. Calling at a different rate will produce incorrect behavior.
* The controller is not thread-safe. Use one instance per simulation thread.

