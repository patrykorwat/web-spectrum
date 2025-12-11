#!/usr/bin/env python3
"""
Record IQ samples from SDRplay using Direct API
Writes to file for GNSS-SDR processing
"""
import os
import sys
import time
import numpy as np
import signal
import argparse

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sdrplay_direct import SDRplayDevice

class IQRecorder:
    def __init__(self, output_file, duration):
        self.output_file = output_file
        self.duration = duration
        self.sdr = None
        self.samples_written = 0
        self.start_time = None
        self.file_handle = None
        self.running = True
        self._last_reported_second = -1

    def data_callback(self, samples):
        """Callback from SDRplay - write to file"""
        if self.file_handle is not None and self.running:
            # Convert complex64 to interleaved float32 for GNSS-SDR
            interleaved = np.zeros(len(samples) * 2, dtype=np.float32)
            interleaved[0::2] = samples.real
            interleaved[1::2] = samples.imag

            # Write to file
            self.file_handle.write(interleaved.tobytes())
            self.samples_written += len(samples)

            # Check if we've recorded enough
            elapsed = time.time() - self.start_time
            if elapsed >= self.duration:
                self.running = False

            # Progress report every second
            current_second = int(elapsed)
            if current_second > self._last_reported_second and current_second > 0:
                percent = min(100, int((elapsed / self.duration) * 100))
                print(f"Recording: {percent}% ({current_second}/{self.duration} seconds)")
                sys.stdout.flush()
                self._last_reported_second = current_second

    def run(self):
        """Main recording function"""
        # Initialize SDRplay
        try:
            print("Initializing SDRplay device...")
            self.sdr = SDRplayDevice()

            # Device is already configured with defaults for GPS L1
            print("SDRplay configured: 2.048 MHz @ 1575.42 MHz")

            # Open output file
            self.file_handle = open(self.output_file, 'wb')
            print(f"Recording to: {self.output_file}")

            # Start recording
            self.start_time = time.time()
            self.sdr.start_streaming(self.data_callback)

            print(f"Recording for {self.duration} seconds...")

            # Wait for recording to complete
            while self.running:
                time.sleep(0.1)

            # Stop streaming
            self.sdr.stop_streaming()
            self.file_handle.close()

            # Report results
            file_size = os.path.getsize(self.output_file)
            sample_rate = self.samples_written / self.duration if self.duration > 0 else 0

            print(f"\n✓ Recording complete:")
            print(f"  • Samples: {self.samples_written:,}")
            print(f"  • File size: {file_size:,} bytes")
            print(f"  • Effective rate: {sample_rate/1e6:.2f} MSPS")

            return 0

        except KeyboardInterrupt:
            print("\nRecording interrupted by user")
            if self.file_handle:
                self.file_handle.close()
            if self.sdr:
                self.sdr.close()
            return 1

        except Exception as e:
            print(f"ERROR: {e}")
            import traceback
            traceback.print_exc()
            if self.file_handle:
                self.file_handle.close()
            if self.sdr:
                self.sdr.close()
            return 1

def main():
    # Parse arguments
    parser = argparse.ArgumentParser(description='Record IQ samples from SDRplay')
    parser.add_argument('output_file', nargs='?',
                       default='/tmp/gps_iq_samples.dat',
                       help='Output file path')
    parser.add_argument('duration', nargs='?', type=int,
                       default=60,
                       help='Recording duration in seconds')

    args = parser.parse_args()

    # Create recorder and run
    recorder = IQRecorder(args.output_file, args.duration)
    return recorder.run()

if __name__ == '__main__':
    sys.exit(main())