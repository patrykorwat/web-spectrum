#!/usr/bin/env python3
"""
SDRplay Streamer using SoapySDR Python Bindings
================================================

This is a simpler, more reliable alternative to direct API access.
Uses SoapySDR Python bindings which are stable and well-tested.

Advantages over direct API:
- Stable, well-tested implementation
- No segfaults from incorrect struct handling
- Still gives full control over device parameters
- Works with all SDRplay devices

Compared to gr-osmosdr:
- No IQ balance issues (we control the code)
- Direct Python access (no C++ layer)
- Full control over parameters

Usage:
    python3 sdrplay_soapy_streamer.py --output /tmp/gps_iq_samples.dat
"""

import SoapySDR
import numpy as np
import sys
import time
import argparse
import signal
import os

class SDRplayStreamer:
    """Stream from SDRplay to file using SoapySDR"""

    def __init__(self, output_file, frequency=1575.42e6, sample_rate=2.048e6,
                 gain=40, bandwidth=1536000, tuner=2, bias_tee=True):
        """
        Initialize SDRplay streamer

        Args:
            output_file: Output file path
            frequency: Center frequency in Hz
            sample_rate: Sample rate in Hz
            gain: Gain in dB (will be converted to appropriate reduction)
            bandwidth: Bandwidth in Hz
            tuner: Tuner selection (1=A, 2=B for dual-tuner devices)
            bias_tee: Enable bias-T for active antenna
        """
        self.output_file = output_file
        self.frequency = frequency
        self.sample_rate = sample_rate
        self.gain = gain
        self.bandwidth = bandwidth
        self.tuner = tuner
        self.bias_tee_enabled = bias_tee

        self.sdr = None
        self.stream = None
        self.file_handle = None
        self.sample_count = 0
        self.start_time = None
        self.bytes_written = 0
        self.last_stats_time = 0
        self.running = False

    def open_device(self):
        """Open and configure SDRplay device"""
        print("=" * 70)
        print("SDRplay Streamer (SoapySDR)")
        print("=" * 70)
        print()

        # Find SDRplay devices
        results = SoapySDR.Device.enumerate("driver=sdrplay")
        if not results:
            raise RuntimeError("No SDRplay devices found")

        print(f"✓ Found {len(results)} SDRplay device(s)")

        # Open first device
        self.sdr = SoapySDR.Device(results[0])
        print(f"✓ Opened device")

        # Configure device
        print(f"\nConfiguring device:")
        print(f"  Frequency: {self.frequency / 1e6:.3f} MHz")
        print(f"  Sample rate: {self.sample_rate / 1e6:.3f} MSPS")
        print(f"  Bandwidth: {self.bandwidth / 1e3:.0f} kHz")
        print(f"  Gain: {self.gain} dB")

        # Set antenna (Tuner selection)
        if self.tuner == 2:
            try:
                self.sdr.setAntenna(SoapySDR.SOAPY_SDR_RX, 0, "Tuner 2 50 ohm")
                print(f"  Tuner: 2 (50 ohm)")
            except:
                print(f"  ⚠️  Could not set Tuner 2, using default")

        # Set sample rate
        self.sdr.setSampleRate(SoapySDR.SOAPY_SDR_RX, 0, self.sample_rate)
        actual_rate = self.sdr.getSampleRate(SoapySDR.SOAPY_SDR_RX, 0)
        print(f"  Actual sample rate: {actual_rate / 1e6:.3f} MSPS")

        # Set frequency
        self.sdr.setFrequency(SoapySDR.SOAPY_SDR_RX, 0, self.frequency)
        actual_freq = self.sdr.getFrequency(SoapySDR.SOAPY_SDR_RX, 0)
        print(f"  Actual frequency: {actual_freq / 1e6:.6f} MHz")

        # Set bandwidth
        try:
            self.sdr.setBandwidth(SoapySDR.SOAPY_SDR_RX, 0, self.bandwidth)
            actual_bw = self.sdr.getBandwidth(SoapySDR.SOAPY_SDR_RX, 0)
            print(f"  Actual bandwidth: {actual_bw / 1e3:.0f} kHz")
        except:
            print(f"  ⚠️  Could not set bandwidth")

        # Disable AGC (manual gain mode)
        try:
            self.sdr.setGainMode(SoapySDR.SOAPY_SDR_RX, 0, False)
            print(f"  AGC: Disabled (manual gain)")
        except:
            pass

        # Set gain
        try:
            self.sdr.setGain(SoapySDR.SOAPY_SDR_RX, 0, self.gain)
            actual_gain = self.sdr.getGain(SoapySDR.SOAPY_SDR_RX, 0)
            print(f"  Actual gain: {actual_gain} dB")
        except Exception as e:
            print(f"  ⚠️  Could not set gain: {e}")

        # Enable bias-T if requested
        if self.bias_tee_enabled:
            try:
                self.sdr.writeSetting("biasT_ctrl", "true")
                print(f"  Bias-T: Enabled")
            except Exception as e:
                print(f"  ⚠️  Could not enable bias-T: {e}")

        # Try to increase buffer size
        try:
            self.sdr.writeSetting("buffer_length", "32768")
        except:
            pass

        print()

    def start_streaming(self):
        """Start streaming to file"""
        print(f"Output file: {self.output_file}")
        print(f"Format: complex64 (gr_complex)")
        print()

        # Open output file
        self.file_handle = open(self.output_file, 'wb', buffering=65536)
        print("✓ Opened output file")

        # Setup stream
        self.stream = self.sdr.setupStream(SoapySDR.SOAPY_SDR_RX, SoapySDR.SOAPY_SDR_CF32)
        self.sdr.activateStream(self.stream)
        print("✓ Stream activated")
        print()

        self.sample_count = 0
        self.start_time = time.time()
        self.last_stats_time = self.start_time
        self.running = True

        print("🎙️  Streaming... (Ctrl+C to stop)")
        print()

        buffer_size = 16384
        buff = np.zeros(buffer_size, dtype=np.complex64)

        try:
            while self.running:
                # Read samples
                sr = self.sdr.readStream(self.stream, [buff], len(buff), timeoutUs=2000000)

                if sr.ret > 0:
                    # Write to file
                    self.file_handle.write(buff[:sr.ret].tobytes())
                    self.file_handle.flush()
                    self.sample_count += sr.ret
                    self.bytes_written += sr.ret * 8  # complex64 = 8 bytes

                    # Print stats every second
                    now = time.time()
                    if now - self.last_stats_time >= 1.0:
                        elapsed = now - self.start_time
                        rate = self.sample_count / elapsed / 1e6
                        size_mb = self.bytes_written / 1e6

                        print(f"\r[{elapsed:.0f}s] {self.sample_count / 1e6:.1f} MSamples | "
                              f"{rate:.2f} MSPS | {size_mb:.1f} MB",
                              end='', flush=True)

                        self.last_stats_time = now

                elif sr.ret == SoapySDR.SOAPY_SDR_TIMEOUT:
                    print("\n⚠️  Timeout reading samples")
                elif sr.ret == SoapySDR.SOAPY_SDR_OVERFLOW:
                    print("\n⚠️  Overflow (samples dropped)")
                else:
                    print(f"\n⚠️  Read error: {sr.ret}")

        except KeyboardInterrupt:
            print("\n\n⏹️  Stopped by user")

        self.running = False

    def cleanup(self):
        """Cleanup resources"""
        print("\n\nCleaning up...")

        if self.stream:
            try:
                self.sdr.deactivateStream(self.stream)
                self.sdr.closeStream(self.stream)
                print("✓ Stream closed")
            except:
                pass

        if self.file_handle:
            self.file_handle.close()
            print("✓ File closed")

        if self.sdr and self.bias_tee_enabled:
            try:
                self.sdr.writeSetting("biasT_ctrl", "false")
                print("✓ Bias-T disabled")
            except:
                pass

        elapsed = time.time() - self.start_time if self.start_time else 0
        if elapsed > 0:
            rate = self.sample_count / elapsed / 1e6
            print()
            print(f"Statistics:")
            print(f"  Duration: {elapsed:.1f} seconds")
            print(f"  Samples: {self.sample_count / 1e6:.1f} MSamples")
            print(f"  Average rate: {rate:.2f} MSPS")
            print(f"  File size: {self.bytes_written / 1e6:.1f} MB")


def main():
    parser = argparse.ArgumentParser(
        description='Stream IQ samples from SDRplay to file (using SoapySDR)',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument('--output', '-o', default='/tmp/gps_iq_samples.dat',
                       help='Output file path (default: /tmp/gps_iq_samples.dat)')
    parser.add_argument('--frequency', '-f', type=float, default=1575.42e6,
                       help='Center frequency in Hz (default: 1575.42e6 for GPS L1)')
    parser.add_argument('--sample-rate', '-s', type=float, default=2.048e6,
                       help='Sample rate in Hz (default: 2.048e6)')
    parser.add_argument('--gain', '-g', type=float, default=40,
                       help='Gain in dB (default: 40)')
    parser.add_argument('--bandwidth', '-b', type=float, default=1536000,
                       help='Bandwidth in Hz (default: 1536000)')
    parser.add_argument('--tuner', type=int, default=2, choices=[1, 2],
                       help='Tuner selection (default: 2)')
    parser.add_argument('--no-bias-tee', action='store_true',
                       help='Disable bias-T (default: enabled)')

    args = parser.parse_args()

    streamer = SDRplayStreamer(
        output_file=args.output,
        frequency=args.frequency,
        sample_rate=args.sample_rate,
        gain=args.gain,
        bandwidth=args.bandwidth,
        tuner=args.tuner,
        bias_tee=not args.no_bias_tee
    )

    # Signal handler for clean shutdown
    def signal_handler(sig, frame):
        print("\n\nShutdown requested...")
        streamer.running = False

    signal.signal(signal.SIGINT, signal_handler)

    try:
        streamer.open_device()
        streamer.start_streaming()
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
    finally:
        streamer.cleanup()


if __name__ == '__main__':
    main()
