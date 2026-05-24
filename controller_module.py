import ctypes
import os
import sys
from pathlib import Path


class ControllerConfig(ctypes.Structure):
    _fields_ = [
        ("kp", ctypes.c_double),
        ("ki", ctypes.c_double),
        ("kd", ctypes.c_double),
        ("target_height", ctypes.c_double),
        ("tick_rate_hz", ctypes.c_double),
        ("paddle_min", ctypes.c_double),
        ("paddle_max", ctypes.c_double),
    ]


def _find_library() -> Path:
    """
    Locate the controller shared library next to this file.
    Searches for the platform-appropriate extension in order:
      Windows : controller.dll
      macOS   : controller.dylib  (then .so as fallback)
      Linux   : controller.so
    Raises FileNotFoundError with a helpful message if none is found.
    """
    here = Path(__file__).resolve().parent

    if sys.platform == "win32":
        candidates = ["controller.dll"]
    elif sys.platform == "darwin":
        candidates = ["controller.dylib", "controller.so"]
    else:  # Linux and other POSIX
        candidates = ["controller.so"]

        for name in candidates:
            lib_path = here / name
            if lib_path.exists():
                if sys.platform == "win32":
                    os.add_dll_directory(str(here))  # tells Windows where to look
                return lib_path

    searched = ", ".join(str(here / n) for n in candidates)
    raise FileNotFoundError(
        f"Controller shared library not found. Searched:\n  {searched}\n"
        f"Build the library for your platform ({sys.platform}) first."
    )


class ControllerModule:
    def __init__(self, kp, ki, kd, target_height, tick_rate_hz, paddle_min, paddle_max):
        """Connect to the shared library and create the controller instance."""
        self._tick_rate_hz = tick_rate_hz

        # ── Load library ──────────────────────────────────────────────────────
        lib_path = _find_library()
        self._lib = ctypes.CDLL(str(lib_path))
        self._bind_functions()

        # ── Create controller instance ────────────────────────────────────────
        cfg = ControllerConfig(
            kp=kp,
            ki=ki,
            kd=kd,
            target_height=target_height,
            tick_rate_hz=tick_rate_hz,
            paddle_min=paddle_min,
            paddle_max=paddle_max,
        )
        self._state = self._lib.controller_create(ctypes.byref(cfg))
        if not self._state:
            raise RuntimeError("controller_create() returned NULL — check your config values")

    def _bind_functions(self):
        """Bind all C function signatures."""
        self._lib.controller_create.argtypes = [ctypes.POINTER(ControllerConfig)]
        self._lib.controller_create.restype = ctypes.c_void_p

        self._lib.controller_destroy.argtypes = [ctypes.c_void_p]
        self._lib.controller_destroy.restype = None

        self._lib.controller_reset.argtypes = [ctypes.c_void_p]
        self._lib.controller_reset.restype = None

        self._lib.controller_tick.argtypes = [
            ctypes.c_void_p,
            ctypes.c_double,
            ctypes.c_double,
        ]
        self._lib.controller_tick.restype = ctypes.c_double

        self._lib.controller_last_peak.argtypes = [ctypes.c_void_p]
        self._lib.controller_last_peak.restype = ctypes.c_double

    def step(self, ball_position: float, ball_velocity: float) -> float:
        """Called from main every 1/tick_rate_hz seconds. Returns paddle position."""
        return self._lib.controller_tick(self._state, ball_position, ball_velocity)

    def last_peak(self) -> float:
        """Returns the last observed peak height, or NaN if none yet."""
        return self._lib.controller_last_peak(self._state)

    def reset(self):
        """Reset internal state, preserving configuration."""
        self._lib.controller_reset(self._state)

    def destroy(self):
        """Free the controller instance."""
        if self._state:
            self._lib.controller_destroy(self._state)
            self._state = None
