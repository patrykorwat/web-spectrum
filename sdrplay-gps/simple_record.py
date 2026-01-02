#!/usr/bin/env python3
"""
Simple direct recording using SDRplay - 10 MSPS for sweep detection
"""
import numpy as np
from sdrplay_direct import SDRplayDevice
from datetime import datetime
import os
import sys

# Configuration
SAMPLE_RATE = 8e6  # 8 MSPS (full bandwidth)
FREQUENCY = 1575.42e6  # GPS L1
DURATION = float(sys.argv[1]) if len(sys.argv) > 1 else 5.0  # seconds (default 5)

print(f"Recording {DURATION}s at {SAMPLE_RATE/1e6} MSPS...")
print(f"Expected size: ~{DURATION * 80:.0f} MB")

# Output file
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
output_file = f"recordings/gps_recording_{timestamp}_10msps.dat"

# Initialize device
device = SDRplayDevice()
device.set_frequency(FREQUENCY)
device.set_sample_rate(SAMPLE_RATE)

print(f"Recording to: {output_file}")
print("Starting...")

# Collect samples
WARMUP_TIME = 0.5  # Skip first 0.5 seconds to avoid startup artifacts
samples_to_skip = int(WARMUP_TIME * SAMPLE_RATE)
samples_to_collect = int(DURATION * SAMPLE_RATE)
samples_collected = []
sample_count = 0
total_samples = 0

def callback(data):
    global sample_count, samples_collected, total_samples
    total_samples += len(data)

    # Skip warmup period
    if total_samples <= samples_to_skip:
        return

    # Collect samples after warmup
    samples_collected.append(data)
    sample_count += len(data)
    if sample_count % (10e6 * 10) == 0:  # Every 10 seconds
        print(f"  {sample_count / SAMPLE_RATE:.0f}s...")

try:
    device.start_streaming(callback)

    # Wait until we have enough samples
    import time
    start_time = time.time()
    while sample_count < samples_to_collect:
        time.sleep(0.1)
        if time.time() - start_time > DURATION + 5:
            print("Timeout!")
            break

    device.stop_streaming()

    # Combine and save
    print(f"\\nCombining {len(samples_collected)} chunks...")
    all_samples = np.concatenate(samples_collected)

    print(f"Saving {len(all_samples):,} samples...")
    all_samples.tofile(output_file)

    file_size = os.path.getsize(output_file)
    print(f"\\n✓ Complete!")
    print(f"  File: {output_file}")
    print(f"  Size: {file_size / 1e6:.0f} MB")
    print(f"  Samples: {len(all_samples):,}")
    print(f"  Duration: {len(all_samples) / SAMPLE_RATE:.1f}s")

except KeyboardInterrupt:
    print("\\nInterrupted!")
    device.stop_streaming()
finally:
    device.close()
