#!/usr/bin/env python3
"""
Minimal test to isolate the streaming initialization issue
"""
import sys
import os
import time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sdrplay_direct import SDRplayDevice

print("=" * 60)
print("Minimal Streaming Test")
print("=" * 60)

def simple_callback(samples):
    """Simplest possible callback - just count samples"""
    print(f"Got {len(samples)} samples")

try:
    # Create device
    print("\n1. Creating device...")
    sdr = SDRplayDevice()
    print("   ✓ Device created")

    # Don't change any settings, just try to stream with defaults
    print("\n2. Starting streaming with default settings...")
    sdr.start_streaming(simple_callback)
    print("   ✓ Streaming started!")

    print("\n3. Streaming for 2 seconds...")
    time.sleep(2)

    print("\n4. Stopping streaming...")
    sdr.stop_streaming()
    print("   ✓ Streaming stopped")

    print("\n" + "=" * 60)
    print("SUCCESS: Streaming test passed!")
    print("=" * 60)

except Exception as e:
    print(f"\nERROR: {e}")
    import traceback
    traceback.print_exc()

    print("\n" + "=" * 60)
    print("DEBUGGING INFO")
    print("=" * 60)
    print("\nThe sdrplay_api_Init function is failing.")
    print("This suggests the issue is with:")
    print("1. The callback structure format")
    print("2. Missing or incorrect device parameters")
    print("3. Hardware/driver communication issue")
    print("\nCheck the SDRplay service is running:")
    print("  - On Linux: systemctl status sdrplay")
    print("  - On macOS: Check if sdrplay_apiService is running")