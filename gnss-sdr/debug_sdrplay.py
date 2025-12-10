#!/usr/bin/env python3
"""
Debug script to find exactly where SDRplay initialization fails
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("=" * 60)
print("SDRplay Debug Test")
print("=" * 60)

try:
    print("\n1. Importing sdrplay_direct...")
    from sdrplay_direct import SDRplayDevice
    print("   ✓ Import successful")

    print("\n2. Creating SDRplayDevice instance...")
    print("   This will initialize the device step by step...")
    print("   Watch for where it stops:\n")

    sdr = SDRplayDevice()

    print("\n3. Device created successfully!")
    print("   ✓ Device object:", sdr)
    print("   ✓ Device params:", sdr.device_params)

    print("\n4. Testing set_frequency...")
    sdr.set_frequency(1575.42e6)
    print("   ✓ Frequency set")

    print("\n5. Testing set_sample_rate...")
    sdr.set_sample_rate(4e6)
    print("   ✓ Sample rate set")

    print("\n6. Testing set_gain...")
    sdr.set_gain(40)
    print("   ✓ Gain set")

    print("\n" + "=" * 60)
    print("SUCCESS: All tests passed!")
    print("=" * 60)
    print("\nThe device is working correctly.")
    print("The issue must be with the streaming callback or FIFO.")

except KeyboardInterrupt:
    print("\n\nInterrupted by user")
    sys.exit(1)

except Exception as e:
    print(f"\n\n✗ FAILED at this step!")
    print(f"   Error: {e}")
    print(f"   Type: {type(e).__name__}")

    import traceback
    print("\nFull traceback:")
    print("-" * 60)
    traceback.print_exc()
    print("-" * 60)

    sys.exit(1)