#!/usr/bin/env python3
"""
RTL-SDR Direct Recording for GPS L1
Matches the interface of sdrplay_direct.py for unified backend
"""

import subprocess
import argparse
import os
import signal
import sys
import time
from datetime import datetime

def record_rtlsdr(output_file, duration=300, sample_rate=2048000, frequency=1575420000, gain=40):
    """
    Record GPS L1 signals using RTL-SDR

    Args:
        output_file: Output file path (.dat)
        duration: Recording duration in seconds
        sample_rate: Sample rate in Hz (default: 2.048 MSPS)
        frequency: Center frequency in Hz (default: 1575.42 MHz GPS L1)
        gain: Gain in dB (default: 40)

    Returns:
        True if successful, False otherwise
    """
    print(f"=" * 70)
    print(f"RTL-SDR GPS L1 Recording")
    print(f"=" * 70)
    print(f"Frequency:    {frequency / 1e6:.3f} MHz")
    print(f"Sample Rate:  {sample_rate / 1e6:.3f} MSPS")
    print(f"Gain:         {gain} dB")
    print(f"Duration:     {duration} seconds")
    print(f"Output:       {output_file}")
    print()

    # Calculate number of samples
    # RTL-SDR outputs 2 bytes per sample (I and Q as uint8)
    num_samples = int(sample_rate * duration)
    expected_size = num_samples * 2  # 2 bytes per sample (IQ uint8)

    print(f"Expected size: {expected_size / (1024 * 1024):.1f} MB")
    print()

    # Create temporary file for uint8 format
    temp_file = output_file + ".tmp_uint8"

    try:
        # Record using rtl_sdr
        # Output format: interleaved I/Q uint8
        cmd = [
            'rtl_sdr',
            '-f', str(frequency),
            '-s', str(sample_rate),
            '-g', str(gain),
            '-n', str(num_samples),
            temp_file
        ]

        print(f"Starting recording...")
        print(f"Command: {' '.join(cmd)}")
        print()

        start_time = time.time()
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            bufsize=1
        )

        # Print output in real-time
        samples_written = 0
        for line in iter(process.stdout.readline, ''):
            if line:
                print(line.rstrip())
                # Try to extract progress if available
                if 'samples' in line.lower():
                    sys.stdout.flush()

        # Wait for completion
        return_code = process.wait()
        elapsed = time.time() - start_time

        if return_code != 0:
            print(f"\n❌ RTL-SDR recording failed with exit code {return_code}")
            if os.path.exists(temp_file):
                os.remove(temp_file)
            return False

        # Check if file was created and has data
        if not os.path.exists(temp_file):
            print(f"\n❌ Output file not created")
            return False

        file_size = os.path.getsize(temp_file)
        if file_size == 0:
            print(f"\n❌ Recording failed - file is empty (0 bytes)")
            print(f"   Possible causes:")
            print(f"   - Device is in use by another application")
            print(f"   - USB connection issue")
            print(f"   - Insufficient permissions")
            os.remove(temp_file)
            return False

        print(f"\n✓ RTL-SDR recording complete!")
        print(f"  Recorded: {file_size / (1024 * 1024):.1f} MB")
        print(f"  Duration: {elapsed:.1f} seconds")
        print(f"  Rate: {file_size / elapsed / (1024 * 1024):.2f} MB/s")
        print()

        # Convert uint8 to complex64 (gr_complex) for GNSS-SDR
        print(f"Converting uint8 to complex64 (gr_complex format)...")

        import numpy as np

        # Read uint8 IQ data
        iq_uint8 = np.fromfile(temp_file, dtype=np.uint8)

        # Separate I and Q
        i_uint8 = iq_uint8[0::2]
        q_uint8 = iq_uint8[1::2]

        # Convert to float32 and normalize to [-1, 1]
        # uint8 range: 0-255, center: 127.5
        i_float = (i_uint8.astype(np.float32) - 127.5) / 127.5
        q_float = (q_uint8.astype(np.float32) - 127.5) / 127.5

        # Combine into complex64
        complex_samples = i_float + 1j * q_float

        # Write to final output file
        complex_samples.astype(np.complex64).tofile(output_file)

        final_size = os.path.getsize(output_file)
        print(f"✓ Conversion complete!")
        print(f"  Format: complex64 (gr_complex)")
        print(f"  Size: {final_size / (1024 * 1024):.1f} MB")
        print(f"  Samples: {len(complex_samples) / 1e6:.1f} MSamples")
        print()

        # Remove temporary file
        os.remove(temp_file)

        return True

    except KeyboardInterrupt:
        print(f"\n\n🛑 Recording interrupted by user")
        if os.path.exists(temp_file):
            os.remove(temp_file)
        return False

    except Exception as e:
        print(f"\n❌ Error during recording: {e}")
        import traceback
        traceback.print_exc()
        if os.path.exists(temp_file):
            os.remove(temp_file)
        return False


def main():
    """Command-line interface matching sdrplay_direct.py"""
    parser = argparse.ArgumentParser(description='RTL-SDR GPS L1 Recording')
    parser.add_argument('--output', type=str, required=True, help='Output file path (.dat)')
    parser.add_argument('--duration', type=int, default=300, help='Recording duration in seconds (default: 300)')
    parser.add_argument('--sample-rate', type=float, default=2.048e6, help='Sample rate in Hz (default: 2.048 MSPS)')
    parser.add_argument('--frequency', type=float, default=1575.42e6, help='Center frequency in Hz (default: 1575.42 MHz)')
    parser.add_argument('--gain', type=float, default=40, help='Gain in dB (default: 40)')
    parser.add_argument('--tuner', type=int, default=1, help='Tuner selection (ignored for RTL-SDR, for API compatibility)')
    parser.add_argument('--gain-reduction', type=int, default=None, help='Gain reduction (converts to positive gain for RTL-SDR)')

    args = parser.parse_args()

    # Convert gain-reduction to gain if provided (for SDRplay API compatibility)
    # SDRplay uses gain reduction (lower = more gain), RTL-SDR uses gain (higher = more gain)
    # Max gain is typically ~60dB, so gain = 60 - gain_reduction
    gain = args.gain
    if args.gain_reduction is not None:
        gain = 60 - args.gain_reduction
        print(f"Converting gain reduction {args.gain_reduction} dB to gain {gain} dB")

    # Run recording
    success = record_rtlsdr(
        output_file=args.output,
        duration=args.duration,
        sample_rate=int(args.sample_rate),
        frequency=int(args.frequency),
        gain=gain
    )

    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
