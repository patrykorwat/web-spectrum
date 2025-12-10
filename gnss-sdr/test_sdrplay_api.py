#!/usr/bin/env python3
"""Quick test to verify SDRplay API is accessible"""

import ctypes
import sys

LIB_PATH = '/usr/local/lib/libsdrplay_api.dylib'

print(f"Testing SDRplay API library: {LIB_PATH}")
print()

try:
    lib = ctypes.CDLL(LIB_PATH)
    print("✓ Successfully loaded library")

    # Try to call sdrplay_api_Open
    lib.sdrplay_api_Open.restype = ctypes.c_int
    err = lib.sdrplay_api_Open()

    if err == 0:  # Success
        print("✓ Successfully opened SDRplay API")

        # Get version
        lib.sdrplay_api_ApiVersion.argtypes = [ctypes.POINTER(ctypes.c_float)]
        lib.sdrplay_api_ApiVersion.restype = ctypes.c_int
        version = ctypes.c_float()
        err = lib.sdrplay_api_ApiVersion(ctypes.byref(version))

        if err == 0:
            print(f"✓ SDRplay API Version: {version.value}")

        # Close API
        lib.sdrplay_api_Close.restype = ctypes.c_int
        lib.sdrplay_api_Close()
        print("✓ Closed SDRplay API")

        print()
        print("SUCCESS: SDRplay API is working!")
    else:
        print(f"✗ Failed to open SDRplay API: error code {err}")
        print()
        print("Possible issues:")
        print("  - SDRPlay API service not running")
        print("  - Try: sudo /Library/SDRplayAPI/3.15.1/bin/sdrplay_apiService start")

except OSError as e:
    print(f"✗ Failed to load library: {e}")
    print()
    print("Make sure SDRplay API is installed:")
    print("  Download from: https://www.sdrplay.com/downloads/")
    sys.exit(1)
except Exception as e:
    print(f"✗ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
