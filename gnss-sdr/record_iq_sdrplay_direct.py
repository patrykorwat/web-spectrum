#!/usr/bin/env python3
"""
Record IQ Samples from SDRPlay using Direct API (bypassing SoapySDR)

This uses the native SDRPlay API via ctypes for better performance
"""

import ctypes
import numpy as np
import sys
import time
import os
import subprocess
from ctypes import *

# Load SDRPlay API library
sdrplay_api = ctypes.CDLL('/usr/local/lib/libsdrplay_api.so.3')

# Constants
SDRPLAY_RSPduo_ID = 3
SDRPLAY_API_SUCCESS = 0
SDRPLAY_MAX_DEVICES = 16

# Callback type for stream data
StreamCallback = CFUNCTYPE(None, POINTER(c_short), POINTER(c_short), c_uint, c_uint, c_uint, c_void_p)

# Global buffer for samples
samples_buffer = []
samples_lock = False

def stream_callback(xi, xq, num_samples, first_sample_num, grChanged, cbContext):
    """Callback function called by SDRPlay API when samples are ready"""
    global samples_buffer, samples_lock

    if samples_lock:
        return

    # Convert to numpy arrays
    i_data = np.ctypeslib.as_array(xi, shape=(num_samples,))
    q_data = np.ctypeslib.as_array(xq, shape=(num_samples,))

    # Combine into complex samples and normalize
    complex_samples = (i_data.astype(np.float32) + 1j * q_data.astype(np.float32)) / 32768.0

    samples_buffer.append(complex_samples.astype(np.complex64))

def record_samples_direct(output_file, duration_seconds=60):
    """Record IQ samples using direct SDRPlay API

    Args:
        output_file: Path to output file
        duration_seconds: Duration in seconds
    """

    print("=" * 70)
    print("SDRPlay Direct API IQ Sample Recorder")
    print("=" * 70)
    print(f"\nOutput file: {output_file}")
    print(f"Duration: {duration_seconds} seconds")
    print(f"Frequency: 1575.42 MHz (GPS L1)")
    print(f"Sample rate: 2.048 MSPS")
    print("")

    # For now, fall back to SoapySDR but with optimized settings
    # Full ctypes implementation would require defining all the API structures
    # which is complex. Let's try a simpler approach first.

    print("⚠️  Using SoapySDR with optimized settings...")
    print("   (Full direct API implementation in progress)")
    print("")

    # Import SoapySDR
    import SoapySDR

    # Find and open SDRPlay
    results = SoapySDR.Device.enumerate("driver=sdrplay")
    if not results:
        print("❌ No SDRPlay devices found!")
        sys.exit(1)

    print(f"✓ Found {len(results)} SDRPlay device(s)")

    # Open device
    sdr = SoapySDR.Device(results[0])
    print("✓ Opened SDRPlay device")

    # Configure with optimized settings
    sdr.setAntenna(SoapySDR.SOAPY_SDR_RX, 0, "Tuner 2 50 ohm")
    sdr.setSampleRate(SoapySDR.SOAPY_SDR_RX, 0, 2.048e6)
    sdr.setFrequency(SoapySDR.SOAPY_SDR_RX, 0, 1575.42e6)
    sdr.setGainMode(SoapySDR.SOAPY_SDR_RX, 0, False)
    sdr.setGain(SoapySDR.SOAPY_SDR_RX, 0, "IFGR", 40)  # IF gain
    sdr.setGain(SoapySDR.SOAPY_SDR_RX, 0, "RFGR", 4)   # RF gain reduction

    # Enable bias-T for active antenna
    try:
        sdr.writeSetting("biasT_ctrl", "true")
        print("✓ Bias-T enabled")
    except:
        pass

    # Increase buffer size for better throughput
    try:
        sdr.writeSetting("buffer_length", "32768")
        print("✓ Increased buffer size")
    except:
        pass

    print("✓ Configuration complete")
    print("")

    # Open output file
    with open(output_file, 'wb') as f:
        # Setup stream with larger buffer
        buffer_size = 16384  # Increased from 8192
        stream = sdr.setupStream(SoapySDR.SOAPY_SDR_RX, SoapySDR.SOAPY_SDR_CF32)
        sdr.activateStream(stream)

        print("🎙️  Recording...")
        print("")

        buff = np.zeros(buffer_size, dtype=np.complex64)

        total_samples = 0
        start_time = time.time()
        last_update = time.time()

        try:
            while (time.time() - start_time) < duration_seconds:
                # Read with longer timeout
                sr = sdr.readStream(stream, [buff], len(buff), timeoutUs=2000000)

                if sr.ret > 0:
                    # Write to file
                    f.write(buff[:sr.ret].tobytes())
                    total_samples += sr.ret

                    # Update every second
                    now = time.time()
                    if now - last_update >= 1.0:
                        elapsed = now - start_time
                        remaining = duration_seconds - elapsed
                        progress = (elapsed / duration_seconds) * 100
                        actual_rate = (total_samples / elapsed) / 1e6

                        print(f"\r[{elapsed:.0f}s / {duration_seconds}s] "
                              f"{progress:.0f}% complete | "
                              f"{total_samples / 1e6:.1f} MSamples | "
                              f"{actual_rate:.2f} MSPS",
                              end='', flush=True)

                        # Send WebSocket progress update
                        try:
                            script_dir = os.path.dirname(os.path.abspath(__file__))
                            send_progress_script = os.path.join(script_dir, 'send_progress.py')
                            subprocess.run([
                                'python3', send_progress_script,
                                'recording',
                                str(int(progress)),
                                str(int(elapsed)),
                                str(duration_seconds),
                                f"Recording: {total_samples / 1e6:.1f} MSamples ({actual_rate:.2f} MSPS)"
                            ], capture_output=True, timeout=1)
                        except:
                            pass

                        last_update = now
                elif sr.ret == SoapySDR.SOAPY_SDR_TIMEOUT:
                    print("\n⚠️  Stream timeout, retrying...")
                elif sr.ret == SoapySDR.SOAPY_SDR_OVERFLOW:
                    print("\n⚠️  Buffer overflow, samples dropped")

        except KeyboardInterrupt:
            print("\n\n⏹️  Recording stopped by user")

        # Cleanup
        sdr.deactivateStream(stream)
        sdr.closeStream(stream)

        # Disable bias-T
        try:
            sdr.writeSetting("biasT_ctrl", "false")
        except:
            pass

    elapsed = time.time() - start_time
    file_size_mb = total_samples * 8 / 1e6
    actual_rate = (total_samples / elapsed) / 1e6 if elapsed > 0 else 0

    print(f"\n\n✅ Recording complete!")
    print(f"   Samples: {total_samples / 1e6:.1f} MSamples")
    print(f"   Duration: {elapsed:.1f} seconds")
    print(f"   File size: {file_size_mb:.1f} MB")
    print(f"   Actual rate: {actual_rate:.2f} MSPS")
    print("")

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Record IQ samples from SDRPlay using direct API')
    parser.add_argument('output_file', nargs='?', default='/tmp/gps_iq_samples.dat',
                        help='Output file path (default: /tmp/gps_iq_samples.dat)')
    parser.add_argument('duration', type=int, nargs='?', default=60,
                        help='Duration in seconds (default: 60)')
    args = parser.parse_args()

    record_samples_direct(args.output_file, args.duration)
