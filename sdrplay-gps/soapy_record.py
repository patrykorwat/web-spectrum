#!/usr/bin/env python3
"""
RSPduo Master Mode Recording using SoapySDR
Device 2: Master mode for 10 MSPS full bandwidth
"""
import numpy as np
import SoapySDR
from SoapySDR import SOAPY_SDR_RX, SOAPY_SDR_CF32
from datetime import datetime
import os
import sys

# Configuration
SAMPLE_RATE = 10e6  # 10 MSPS
FREQUENCY = 1575.42e6  # GPS L1
DURATION = float(sys.argv[1]) if len(sys.argv) > 1 else 5.0  # seconds
DEVICE_INDEX = 2  # RSPduo Master mode

print(f"Recording {DURATION}s at {SAMPLE_RATE/1e6} MSPS using RSPduo Master mode...")
print(f"Expected size: ~{DURATION * 80:.0f} MB")

# Output file
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
output_file = f"recordings/gps_recording_{timestamp}_rspduo_master.dat"

# Enumerate devices and find RSPduo Master mode (Device 2)
print(f"Enumerating devices...")
devices = SoapySDR.Device.enumerate()

# Find Device 2 (Master mode)
master_device = None
for dev in devices:
    # SoapySDRKwargs acts like a dict but needs different access
    if 'mode' in dev and 'serial' in dev:
        if dev['mode'] == 'MA' and dev['serial'] == '2305039634':
            master_device = dev
            break

if not master_device:
    print("✗ RSPduo Master mode device not found!")
    sys.exit(1)

print(f"Found RSPduo Master mode device:")
print(f"  Mode: {master_device['mode']}")
print(f"  Serial: {master_device['serial']}")
print(f"  Label: {master_device['label']}")

print(f"\nOpening RSPduo Master mode device...")
sdr = SoapySDR.Device(master_device)

try:
    # Configure device
    print(f"Configuring device...")

    # Set sample rate
    sdr.setSampleRate(SOAPY_SDR_RX, 0, SAMPLE_RATE)
    actual_rate = sdr.getSampleRate(SOAPY_SDR_RX, 0)
    print(f"✓ Sample rate: {actual_rate/1e6} MSPS")

    # Set center frequency
    sdr.setFrequency(SOAPY_SDR_RX, 0, FREQUENCY)
    actual_freq = sdr.getFrequency(SOAPY_SDR_RX, 0)
    print(f"✓ Center frequency: {actual_freq/1e6} MHz")

    # Set bandwidth (if supported)
    try:
        sdr.setBandwidth(SOAPY_SDR_RX, 0, 8e6)  # 8 MHz
        actual_bw = sdr.getBandwidth(SOAPY_SDR_RX, 0)
        print(f"✓ Bandwidth: {actual_bw/1e6} MHz")
    except:
        print("⚠ Bandwidth setting not available")

    # Enable bias-T for active antenna (if supported)
    try:
        sdr.writeSetting('biasT_ctrl', 'true')
        print(f"✓ Bias-T enabled")
    except:
        print("⚠ Bias-T control not available via this method")

    # Set gain - AUTO or manual
    try:
        # Try AGC first
        sdr.setGainMode(SOAPY_SDR_RX, 0, True)
        print(f"✓ Gain: AGC enabled")
    except:
        # Manual gain
        sdr.setGain(SOAPY_SDR_RX, 0, 30)
        print(f"✓ Gain: 30 dB (manual)")

    # Setup stream
    print(f"Setting up stream...")
    rx_stream = sdr.setupStream(SOAPY_SDR_RX, SOAPY_SDR_CF32)
    sdr.activateStream(rx_stream)
    print(f"✓ Stream activated")

    # Calculate samples to collect
    samples_to_collect = int(DURATION * actual_rate)
    print(f"Recording to: {output_file}")
    print(f"Collecting {samples_to_collect:,} samples...")

    # Allocate buffer
    buff_size = 16384  # Buffer size per read
    buff = np.zeros(buff_size, dtype=np.complex64)
    all_samples = []
    total_collected = 0

    # Collect samples
    import time
    start_time = time.time()

    while total_collected < samples_to_collect:
        sr = sdr.readStream(rx_stream, [buff], buff_size)

        if sr.ret > 0:
            # Append samples
            all_samples.append(buff[:sr.ret].copy())
            total_collected += sr.ret

            # Progress
            if total_collected % int(actual_rate * 1) == 0:  # Every second
                elapsed = time.time() - start_time
                print(f"  {total_collected:,} samples ({elapsed:.1f}s)")
        elif sr.ret == -1:
            print("Timeout in readStream")
            break
        else:
            print(f"Error in readStream: {sr.ret}")
            break

        # Safety timeout
        if time.time() - start_time > DURATION + 10:
            print("Safety timeout reached")
            break

    # Deactivate stream
    sdr.deactivateStream(rx_stream)
    sdr.closeStream(rx_stream)
    print(f"✓ Stream closed")

    # Combine and save
    print(f"\nCombining {len(all_samples)} chunks...")
    combined = np.concatenate(all_samples)

    print(f"Saving {len(combined):,} samples...")
    combined.tofile(output_file)

    file_size = os.path.getsize(output_file)
    print(f"\n✓ Complete!")
    print(f"  File: {output_file}")
    print(f"  Size: {file_size / 1e6:.0f} MB")
    print(f"  Samples: {len(combined):,}")
    print(f"  Duration: {len(combined) / actual_rate:.3f}s")
    print(f"  Sample rate: {actual_rate/1e6} MSPS")

except Exception as e:
    print(f"\n✗ Error: {e}")
    import traceback
    traceback.print_exc()

finally:
    # Close device
    print("Closing device...")
    del sdr
    print("✓ Device closed")
