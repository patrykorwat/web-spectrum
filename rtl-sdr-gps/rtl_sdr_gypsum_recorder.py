#!/usr/bin/env python3
"""
RTL-SDR GPS Recorder for Gypsum
================================

Records GPS L1 C/A signals in Gypsum-compatible format.

Gypsum Requirements:
- Sample rate: 2.046 MHz (exactly 2x PRN chipping rate)
- Format: Complex float32 (interleaved I/Q)
- File format: GNU Radio recording format

RTL-SDR records in uint8 format, so we convert to float32.

Usage:
    python3 rtl_sdr_gypsum_recorder.py --duration 60 --output gps_samples.dat
"""

import argparse
import subprocess
import os
import sys
import time
import numpy as np
from datetime import datetime


class RTLSDRGypsumRecorder:
    """RTL-SDR GPS recorder for Gypsum decoder"""

    def __init__(self):
        self.frequency = 1575420000  # GPS L1 C/A (Hz)
        # Gypsum expects exactly 2.046 MHz (2x PRN rate)
        # RTL-SDR closest: 2.048 MHz, we'll use that and note it
        self.sample_rate = 2048000   # 2.048 MSPS (close to Gypsum's 2.046)
        self.gain = 0  # Auto gain
        self.bias_tee = True

    def check_rtlsdr(self):
        """Check RTL-SDR availability"""
        try:
            result = subprocess.run(['which', 'rtl_sdr'],
                                  capture_output=True, text=True)
            return result.returncode == 0
        except:
            return False

    def enable_bias_tee(self):
        """Enable bias-T for active antenna"""
        if not self.bias_tee:
            return
        try:
            subprocess.run(['rtl_biast', '-b', '1'],
                         capture_output=True, timeout=5)
            print("✓ Bias-T enabled")
        except:
            print("⚠ Bias-T control not available")

    def disable_bias_tee(self):
        """Disable bias-T"""
        if not self.bias_tee:
            return
        try:
            subprocess.run(['rtl_biast', '-b', '0'],
                         capture_output=True, timeout=5)
            print("✓ Bias-T disabled")
        except:
            pass

    def record(self, duration_seconds, output_file):
        """
        Record GPS signals in Gypsum-compatible format

        Args:
            duration_seconds: Recording duration
            output_file: Output file path (GNU Radio format, float32)
        """
        print("="*60)
        print("RTL-SDR GPS Recorder for Gypsum")
        print("="*60)

        if not self.check_rtlsdr():
            print("ERROR: rtl_sdr not found. Install: brew install librtlsdr")
            return False

        self.enable_bias_tee()

        # Record to temporary file (uint8 format)
        temp_file = output_file + ".tmp"
        num_samples = self.sample_rate * duration_seconds

        # Calculate sizes
        uint8_size_mb = (num_samples * 2) / (1024 * 1024)  # 2 bytes per sample (I+Q)
        float32_size_mb = (num_samples * 8) / (1024 * 1024)  # 8 bytes per sample

        print(f"\nConfiguration:")
        print(f"  Frequency:    {self.frequency / 1e6:.2f} MHz (GPS L1)")
        print(f"  Sample Rate:  {self.sample_rate / 1e6:.3f} MSPS")
        print(f"  Duration:     {duration_seconds}s ({duration_seconds/60:.1f} min)")
        print(f"  Gain:         Auto (AGC)")
        print(f"  Bias-T:       {'Enabled' if self.bias_tee else 'Disabled'}")
        print(f"\n  Temp size:    {uint8_size_mb:.1f} MB (uint8)")
        print(f"  Final size:   {float32_size_mb:.1f} MB (float32)")
        print(f"  Format:       GNU Radio (complex float32)")

        # Step 1: Record with rtl_sdr (uint8)
        print(f"\nStep 1/2: Recording from RTL-SDR...")
        cmd = [
            'rtl_sdr',
            '-f', str(self.frequency),
            '-s', str(self.sample_rate),
            '-g', str(self.gain),
            '-n', str(num_samples),
            temp_file
        ]

        try:
            start_time = time.time()
            result = subprocess.run(cmd, capture_output=True, text=True)

            if result.returncode != 0:
                print(f"ERROR: rtl_sdr failed: {result.stderr}")
                return False

            elapsed = time.time() - start_time
            print(f"✓ Recorded {duration_seconds}s in {elapsed:.1f}s")

        except KeyboardInterrupt:
            print("\n\nRecording interrupted")
            self.disable_bias_tee()
            if os.path.exists(temp_file):
                os.remove(temp_file)
            return False

        # Step 2: Convert uint8 → float32 (Gypsum format)
        print(f"\nStep 2/2: Converting to Gypsum format (float32)...")
        try:
            # Read uint8 IQ samples
            iq_uint8 = np.fromfile(temp_file, dtype=np.uint8)

            # Convert to complex float32
            # uint8 [0-255] → float [-1, +1]
            iq_float = (iq_uint8.astype(np.float32) - 127.5) / 127.5

            # Interleave I/Q as complex64 (GNU Radio format)
            # iq_float is [I0, Q0, I1, Q1, ...]
            # Complex64 expects interleaved float32
            iq_float.tofile(output_file)

            print(f"✓ Converted {len(iq_uint8)//2:,} samples to float32")

            # Cleanup temp file
            os.remove(temp_file)

        except Exception as e:
            print(f"ERROR during conversion: {e}")
            self.disable_bias_tee()
            return False

        finally:
            self.disable_bias_tee()

        # Verify output
        if os.path.exists(output_file):
            size_mb = os.path.getsize(output_file) / (1024 * 1024)
            print(f"\n{'='*60}")
            print("Recording Complete!")
            print(f"{'='*60}")
            print(f"  File:     {output_file}")
            print(f"  Size:     {size_mb:.1f} MB")
            print(f"  Format:   Complex float32 (Gypsum compatible)")
            print(f"  Samples:  {os.path.getsize(output_file) // 8:,}")
            print(f"\nNext: Process with Gypsum")
            return True
        else:
            print("\nERROR: Output file not created!")
            return False


def main():
    parser = argparse.ArgumentParser(
        description='RTL-SDR GPS Recorder for Gypsum',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument('--duration', type=int, default=60,
                       help='Recording duration in seconds (default: 60)')
    parser.add_argument('--output', type=str, default=None,
                       help='Output filename (default: auto-generated)')
    parser.add_argument('--no-bias-tee', action='store_true',
                       help='Disable bias-T')

    args = parser.parse_args()

    # Auto-generate filename
    if args.output is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = os.path.join(os.path.dirname(__file__), 'recordings')
        os.makedirs(output_dir, exist_ok=True)
        args.output = os.path.join(output_dir, f'gps_gypsum_{timestamp}.dat')

    recorder = RTLSDRGypsumRecorder()
    recorder.bias_tee = not args.no_bias_tee

    success = recorder.record(args.duration, args.output)
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
