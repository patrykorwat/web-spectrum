#!/usr/bin/env python3
"""
Record IQ samples from RTL-SDR to file for GNSS-SDR processing
Compatible with RTL-SDR dongles (RTL2832U)
"""

import SoapySDR
from SoapySDR import SOAPY_SDR_RX, SOAPY_SDR_CF32
import numpy as np
import sys
import time
import signal

def signal_handler(sig, frame):
    print('\n\n✋ Recording stopped by user')
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)

def record_samples(output_file, duration_seconds=60, continuous=False):
    """Record IQ samples from RTL-SDR to file

    Args:
        output_file: Path to output file
        duration_seconds: Duration in seconds (ignored if continuous=True)
        continuous: If True, record continuously until interrupted
    """

    print("=" * 70)
    print("RTL-SDR IQ Sample Recorder for GNSS-SDR")
    print("=" * 70)
    print("")
    print(f"Output file: {output_file}")
    print(f"Duration: {'continuous' if continuous else f'{duration_seconds} seconds'}")
    print(f"Frequency: 1575.42 MHz (GPS L1)")
    print(f"Sample rate: 2.048 MSPS")
    print("")

    # Find RTL-SDR device
    results = SoapySDR.Device.enumerate('driver=rtlsdr')
    if not results:
        print("❌ No RTL-SDR devices found!")
        print("   Please check:")
        print("   • RTL-SDR is connected via USB")
        print("   • librtlsdr is installed")
        sys.exit(1)

    print(f"✓ Found RTL-SDR device")

    # Open device
    sdr = SoapySDR.Device(dict(driver='rtlsdr'))

    # GPS L1 frequency
    freq = 1575.42e6

    # Sample rate (RTL-SDR can do up to ~2.8 MSPS typically)
    sample_rate = 2.048e6

    # Configure RTL-SDR
    sdr.setSampleRate(SOAPY_SDR_RX, 0, sample_rate)
    sdr.setFrequency(SOAPY_SDR_RX, 0, freq)

    # RTL-SDR gain settings
    # Use manual gain for consistent performance
    sdr.setGainMode(SOAPY_SDR_RX, 0, False)  # Manual gain
    sdr.setGain(SOAPY_SDR_RX, 0, 40)  # 40 dB gain (adjust as needed)

    # Enable bias tee if your RTL-SDR supports it (for active GPS antennas)
    # Note: Not all RTL-SDR dongles support bias-tee
    try:
        sdr.writeSetting('biastee', 'true')
        print("✓ Bias-T enabled (for active GPS antenna)")
    except:
        print("ℹ️  Bias-T not available on this device")

    print("✓ Configuration complete")
    print("")

    # Setup stream
    stream = sdr.setupStream(SOAPY_SDR_RX, SOAPY_SDR_CF32)
    sdr.activateStream(stream)

    # Buffer for reading samples
    buff = np.array([0]*1024, np.complex64)

    print("🎙️  Recording...")
    print("")

    with open(output_file, 'wb') as f:
        start_time = time.time()
        last_report = start_time
        total_samples = 0

        try:
            while True:
                if not continuous and (time.time() - start_time) >= duration_seconds:
                    break

                # Read samples
                sr = sdr.readStream(stream, [buff], len(buff), timeoutUs=1000000)

                if sr.ret > 0:
                    # Write samples to file as complex64
                    f.write(buff[:sr.ret].tobytes())
                    total_samples += sr.ret

                    # Flush periodically for continuous reading
                    if continuous:
                        f.flush()

                    # Progress report
                    now = time.time()
                    elapsed = int(now - start_time)

                    if now - last_report >= 1.0:  # Report every second
                        if continuous:
                            print(f"\r[{elapsed}s] Recording... | {total_samples / 1e6:.1f} MSamples", end='', flush=True)
                        else:
                            progress = int((elapsed / duration_seconds) * 100)
                            remaining = duration_seconds - elapsed
                            print(f"[{elapsed}s / {duration_seconds}s] {progress}% complete | {total_samples / 1e6:.1f} MSamples", end='')
                            if elapsed > 0 and elapsed % 10 == 0:
                                print()
                        last_report = now

                elif sr.ret == -1:
                    print("\n⚠️  Stream timeout")
                    break

        except KeyboardInterrupt:
            print("\n\n✋ Recording stopped by user")

        finally:
            sdr.deactivateStream(stream)
            sdr.closeStream(stream)

    elapsed = time.time() - start_time
    print("")
    print("")
    print("✅ Recording complete!")
    print(f"   Samples: {total_samples / 1e6:.1f} MSamples")
    print(f"   Duration: {elapsed:.1f} seconds")

    # Calculate file size
    import os
    file_size = os.path.getsize(output_file)
    if file_size > 1e9:
        size_str = f"{file_size / 1e9:.1f} GB"
    else:
        size_str = f"{file_size / 1e6:.1f} MB"
    print(f"   File size: {size_str}")
    print("")

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python3 record_iq_samples_rtlsdr.py <output_file> [duration_seconds]")
        print("Example: python3 record_iq_samples_rtlsdr.py /tmp/gps_iq_samples.dat 300")
        sys.exit(1)

    output_file = sys.argv[1]
    duration = int(sys.argv[2]) if len(sys.argv) > 2 else 60
    continuous = '--continuous' in sys.argv

    record_samples(output_file, duration, continuous)
