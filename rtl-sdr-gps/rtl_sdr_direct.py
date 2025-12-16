#!/usr/bin/env python3
"""
RTL-SDR GPS L1 C/A Direct Recording Script
==========================================

Records GPS L1 C/A signals (1575.42 MHz) using RTL-SDR hardware.
Compatible with RTL-SDR Blog V3/V4, RTL2832U-based dongles with bias-T support.

Hardware Requirements:
- RTL-SDR Blog V3/V4 or equivalent (R820T2/R828D tuner)
- GPS active antenna (requires bias-T power)
- USB 2.0/3.0 port

GPS L1 C/A Signal:
- Center frequency: 1575.42 MHz
- Main lobe bandwidth: ±1.023 MHz (2.046 MHz total)
- Sample rate: 2.048 MSPS (Nyquist compliant for main lobe)
- RTL-SDR max stable sample rate: 2.56 MSPS (will use 2.048 MSPS)

Recording Configuration:
- Sample rate: 2.048 MSPS
- Format: 8-bit IQ (uint8, GNSS-SDR compatible)
- Bandwidth: ~2 MHz (captures GPS L1 main lobe)
- Gain: Auto (RTL-SDR AGC enabled)
- Bias-T: ENABLED (for active GPS antenna power)

File Size Estimates:
- 2.048 MSPS × 2 bytes/sample (I+Q uint8) = 4.096 MB/s
- 1 minute = 245.76 MB
- 5 minutes = 1.23 GB
- 10 minutes = 2.46 GB

Usage:
    python3 rtl_sdr_direct.py --duration 300 --output gps_recording.dat

Author: Based on SDRplay GPS recording system
Date: December 2025
"""

import argparse
import subprocess
import os
import sys
import time
from datetime import datetime
import signal

class RTLSDRGPSRecorder:
    """RTL-SDR GPS L1 C/A signal recorder"""

    def __init__(self):
        self.frequency = 1575420000  # GPS L1 C/A center frequency (Hz)
        self.sample_rate = 2048000   # 2.048 MSPS
        self.gain = 0                # 0 = Auto gain (AGC)
        self.bias_tee = True         # Enable bias-T for active antenna
        self.process = None
        self.recording = False

    def check_rtlsdr_installed(self):
        """Check if rtl_sdr command is available"""
        try:
            result = subprocess.run(['which', 'rtl_sdr'],
                                  capture_output=True, text=True)
            if result.returncode != 0:
                print("ERROR: rtl_sdr command not found!")
                print("Install rtl-sdr tools:")
                print("  macOS: brew install librtlsdr")
                print("  Linux: sudo apt-get install rtl-sdr")
                return False
            return True
        except Exception as e:
            print(f"ERROR checking rtl_sdr: {e}")
            return False

    def check_device_present(self):
        """Check if RTL-SDR device is connected"""
        try:
            result = subprocess.run(['rtl_test', '-t'],
                                  capture_output=True, text=True, timeout=2)
            if 'Found' in result.stdout:
                print("✓ RTL-SDR device detected")
                # Extract device info
                for line in result.stdout.split('\n'):
                    if 'Found' in line or 'Tuner' in line:
                        print(f"  {line.strip()}")
                return True
            else:
                print("ERROR: No RTL-SDR device found!")
                print("Check USB connection and device permissions.")
                return False
        except subprocess.TimeoutExpired:
            print("✓ RTL-SDR device detected (timeout during test is normal)")
            return True
        except Exception as e:
            print(f"ERROR detecting RTL-SDR device: {e}")
            return False

    def enable_bias_tee(self):
        """Enable bias-T for active GPS antenna power"""
        if not self.bias_tee:
            return True

        try:
            # RTL-SDR Blog V3/V4 bias-T control
            result = subprocess.run(['rtl_biast', '-b', '1'],
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                print("✓ Bias-T enabled (GPS antenna powered)")
                return True
            else:
                print("WARNING: Could not enable bias-T")
                print("  Your RTL-SDR may not support bias-T")
                print("  Use external power for GPS antenna if needed")
                return True  # Continue anyway
        except FileNotFoundError:
            print("WARNING: rtl_biast command not found")
            print("  Bias-T control not available")
            print("  Ensure your RTL-SDR supports bias-T and use manual control if needed")
            return True  # Continue anyway
        except Exception as e:
            print(f"WARNING: Error enabling bias-T: {e}")
            return True  # Continue anyway

    def disable_bias_tee(self):
        """Disable bias-T (cleanup)"""
        if not self.bias_tee:
            return

        try:
            subprocess.run(['rtl_biast', '-b', '0'],
                         capture_output=True, text=True, timeout=5)
            print("✓ Bias-T disabled")
        except:
            pass  # Ignore errors during cleanup

    def record(self, duration_seconds, output_file):
        """
        Record GPS L1 C/A signals to file

        Args:
            duration_seconds: Recording duration in seconds
            output_file: Output .dat file path
        """
        print("\n" + "="*60)
        print("RTL-SDR GPS L1 C/A RECORDER")
        print("="*60)

        # Pre-flight checks
        if not self.check_rtlsdr_installed():
            return False

        if not self.check_device_present():
            return False

        if not self.enable_bias_tee():
            return False

        # Calculate file size
        bytes_per_sample = 2  # IQ uint8 (1 byte I + 1 byte Q)
        total_bytes = self.sample_rate * bytes_per_sample * duration_seconds
        size_mb = total_bytes / (1024 * 1024)
        size_gb = size_mb / 1024

        print(f"\nRecording Configuration:")
        print(f"  Frequency:     {self.frequency / 1e6:.2f} MHz (GPS L1 C/A)")
        print(f"  Sample Rate:   {self.sample_rate / 1e6:.3f} MSPS")
        print(f"  Gain:          Auto (AGC enabled)")
        print(f"  Bias-T:        {'ENABLED' if self.bias_tee else 'DISABLED'}")
        print(f"  Duration:      {duration_seconds} seconds ({duration_seconds/60:.1f} minutes)")
        print(f"  Output File:   {output_file}")
        print(f"  Expected Size: {size_mb:.1f} MB ({size_gb:.2f} GB)")
        print(f"  Format:        8-bit IQ (uint8, GNSS-SDR compatible)")

        # Build rtl_sdr command
        # rtl_sdr usage: rtl_sdr [options] <filename>
        #   -f <frequency_hz>  : Center frequency
        #   -s <sample_rate>   : Sample rate
        #   -g <gain>          : Gain (0 = auto)
        #   -n <samples>       : Number of samples to read

        num_samples = self.sample_rate * duration_seconds

        cmd = [
            'rtl_sdr',
            '-f', str(self.frequency),
            '-s', str(self.sample_rate),
            '-g', str(self.gain),  # 0 = Auto gain
            '-n', str(num_samples),
            output_file
        ]

        print(f"\nCommand: {' '.join(cmd)}")
        print("\nStarting recording...")
        print("Press Ctrl+C to stop early\n")

        start_time = time.time()
        self.recording = True

        try:
            # Run rtl_sdr and show progress
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )

            # Monitor progress
            bytes_written = 0
            last_update = time.time()

            while self.recording and self.process.poll() is None:
                # Check file size periodically
                if os.path.exists(output_file):
                    current_size = os.path.getsize(output_file)
                    if time.time() - last_update >= 1.0:  # Update every second
                        elapsed = time.time() - start_time
                        progress = (current_size / total_bytes) * 100
                        speed = current_size / elapsed / (1024 * 1024)  # MB/s

                        print(f"\rProgress: {progress:.1f}% | "
                              f"Elapsed: {elapsed:.1f}s | "
                              f"Size: {current_size/(1024*1024):.1f} MB | "
                              f"Speed: {speed:.2f} MB/s", end='', flush=True)

                        last_update = time.time()

                time.sleep(0.1)

            # Wait for process to complete
            if self.process:
                self.process.wait()

            print()  # New line after progress

        except KeyboardInterrupt:
            print("\n\nRecording interrupted by user")
            if self.process:
                self.process.terminate()
                self.process.wait()

        finally:
            self.recording = False
            self.disable_bias_tee()

        # Verify recording
        if os.path.exists(output_file):
            actual_size = os.path.getsize(output_file)
            actual_duration = actual_size / (self.sample_rate * bytes_per_sample)

            print(f"\n{'='*60}")
            print("Recording Complete!")
            print(f"{'='*60}")
            print(f"  File:     {output_file}")
            print(f"  Size:     {actual_size/(1024*1024):.1f} MB ({actual_size/(1024*1024*1024):.2f} GB)")
            print(f"  Duration: {actual_duration:.2f} seconds ({actual_duration/60:.2f} minutes)")
            print(f"  Samples:  {actual_size // bytes_per_sample:,}")
            print(f"\nNext Steps:")
            print(f"  1. Process with GNSS-SDR:")
            print(f"     gnss-sdr --config_file=gnss-sdr-config.conf --signal_source.filename={output_file}")
            print(f"  2. Analyze spectrum:")
            print(f"     python3 gps_spectrum_analyzer.py {output_file}")

            return True
        else:
            print("\nERROR: Recording file not created!")
            return False


def main():
    parser = argparse.ArgumentParser(
        description='RTL-SDR GPS L1 C/A Signal Recorder',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Record 5 minutes of GPS L1 signals
  python3 rtl_sdr_direct.py --duration 300 --output gps_recording.dat

  # Record 1 minute with auto-generated filename
  python3 rtl_sdr_direct.py --duration 60

  # Disable bias-T (if using externally powered antenna)
  python3 rtl_sdr_direct.py --duration 300 --no-bias-tee

Hardware Requirements:
  - RTL-SDR Blog V3/V4 or compatible dongle
  - GPS active antenna (requires bias-T or external power)
  - Clear view of sky for GPS reception

Note: RTL-SDR uses 8-bit samples (vs SDRplay 16-bit), so SNR will be lower.
      For best results, use RTL-SDR Blog V4 with improved sensitivity.
        """
    )

    parser.add_argument('--duration', type=int, default=300,
                       help='Recording duration in seconds (default: 300 = 5 minutes)')
    parser.add_argument('--output', type=str, default=None,
                       help='Output filename (default: auto-generated with timestamp)')
    parser.add_argument('--no-bias-tee', action='store_true',
                       help='Disable bias-T (use if antenna has external power)')

    args = parser.parse_args()

    # Generate output filename if not provided
    if args.output is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = os.path.join(os.path.dirname(__file__), 'recordings')
        os.makedirs(output_dir, exist_ok=True)
        args.output = os.path.join(output_dir, f'gps_recording_{timestamp}.dat')

    # Create recorder
    recorder = RTLSDRGPSRecorder()
    recorder.bias_tee = not args.no_bias_tee

    # Start recording
    success = recorder.record(args.duration, args.output)

    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
