#!/usr/bin/env python3
"""
SDRPlay to GNSS-SDR UDP Streamer

This script captures IQ samples from SDRPlay RSPduo and streams them
via UDP to GNSS-SDR's Custom_UDP_Signal_Source.

Architecture:
    SDRPlay → SoapySDR → This Script → UDP (port 5555) → GNSS-SDR

Usage:
    python3 sdrplay_to_gnss_sdr.py --freq 1575.42e6 --rate 2.048e6 --gain 40 --tuner 2 --bias-tee

Requirements:
    - SoapySDR
    - SDRPlay API installed
    - numpy
"""

import SoapySDR
import numpy as np
import socket
import struct
import time
import argparse
import sys


class SDRPlayToGNSS:
    """Stream SDRPlay IQ samples to GNSS-SDR via UDP"""

    def __init__(self,
                 frequency: float,
                 sample_rate: float,
                 gain: float,
                 tuner: int = 2,
                 bias_tee: bool = False,
                 gnss_sdr_host: str = '127.0.0.1',
                 gnss_sdr_port: int = 5555):
        """
        Initialize SDRPlay streamer

        Args:
            frequency: Center frequency in Hz (e.g., 1575.42e6 for GPS L1)
            sample_rate: Sample rate in Hz (e.g., 2.048e6)
            gain: RF gain in dB
            tuner: Tuner selection (1 or 2)
            bias_tee: Enable bias-T for active antenna (Tuner 2 only)
            gnss_sdr_host: GNSS-SDR host IP
            gnss_sdr_port: GNSS-SDR UDP port
        """
        self.frequency = frequency
        self.sample_rate = sample_rate
        self.gain = gain
        self.tuner = tuner
        self.bias_tee = bias_tee
        self.gnss_sdr_host = gnss_sdr_host
        self.gnss_sdr_port = gnss_sdr_port

        self.sdr = None
        self.stream = None
        self.udp_socket = None
        self.running = False

    def setup_sdr(self):
        """Initialize SDRPlay device"""
        print("=" * 70)
        print("SDRPlay to GNSS-SDR UDP Streamer")
        print("=" * 70)
        print("")

        # Find SDRPlay devices
        print("🔍 Searching for SDRPlay devices...")
        results = SoapySDR.Device.enumerate("driver=sdrplay")

        if not results:
            print("❌ No SDRPlay devices found!")
            print("   Make sure:")
            print("   • SDRPlay is connected via USB")
            print("   • SDRPlay API is installed")
            print("   • Drivers are loaded")
            sys.exit(1)

        print(f"✓ Found {len(results)} SDRPlay device(s)")

        # For RSPduo, use the first enumeration result (Single Tuner mode)
        # This mode allows selecting either Tuner 1 or Tuner 2 via antenna setting
        # Other modes: DT=Dual Tuner, MA=Master, MA8=Master 8MHz
        device_args = results[0]  # Single Tuner mode

        # Antenna (tuner) selection map for RSPduo
        antenna_map = {
            1: "Tuner 1 50 ohm",
            2: "Tuner 2 50 ohm"
        }

        self.sdr = SoapySDR.Device(device_args)
        print(f"✓ Opened SDRPlay device")

        # Get device info
        try:
            hw_info = self.sdr.getHardwareInfo()
            # hw_info is a SoapySDRKwargs object, access like a dict but differently
            hw_key = self.sdr.getHardwareKey()
            print(f"  Hardware: {hw_key}")
        except:
            print(f"  Hardware: RSPduo")

        # Configure tuner selection via antenna setting
        antenna_name = antenna_map.get(self.tuner, "Tuner 1 50 ohm")
        self.sdr.setAntenna(SoapySDR.SOAPY_SDR_RX, 0, antenna_name)
        print(f"  Using {antenna_name}")

        # Disable filters
        try:
            self.sdr.writeSetting("rfnotch_ctrl", "false")
            self.sdr.writeSetting("dabnotch_ctrl", "false")
        except:
            pass  # Not all settings available on all models

        # Set sample rate
        self.sdr.setSampleRate(SoapySDR.SOAPY_SDR_RX, 0, self.sample_rate)
        actual_rate = self.sdr.getSampleRate(SoapySDR.SOAPY_SDR_RX, 0)
        print(f"✓ Sample rate: {actual_rate / 1e6:.3f} MSPS")

        # Set frequency
        self.sdr.setFrequency(SoapySDR.SOAPY_SDR_RX, 0, self.frequency)
        actual_freq = self.sdr.getFrequency(SoapySDR.SOAPY_SDR_RX, 0)
        print(f"✓ Frequency: {actual_freq / 1e6:.2f} MHz")

        # Disable AGC to allow manual gain control
        try:
            self.sdr.setGainMode(SoapySDR.SOAPY_SDR_RX, 0, False)
            print(f"✓ AGC disabled (manual gain control)")
        except Exception as e:
            print(f"⚠️  Could not disable AGC: {e}")

        # Set gain
        self.sdr.setGain(SoapySDR.SOAPY_SDR_RX, 0, self.gain)
        actual_gain = self.sdr.getGain(SoapySDR.SOAPY_SDR_RX, 0)
        print(f"✓ Gain: {actual_gain:.1f} dB")

        # Enable bias-T if requested (Tuner 2 only)
        if self.bias_tee:
            if self.tuner == 2:
                try:
                    self.sdr.writeSetting("biastee_ctrl", "true")
                    print(f"✓ Bias-T enabled (powering active antenna)")
                except Exception as e:
                    print(f"⚠️  Could not enable bias-T: {e}")
            else:
                print(f"⚠️  Bias-T only available on Tuner 2 (current: Tuner {self.tuner})")

        print("")

    def setup_udp(self):
        """Setup UDP socket for GNSS-SDR"""
        self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        print(f"✓ UDP socket created")
        print(f"  Target: {self.gnss_sdr_host}:{self.gnss_sdr_port}")
        print(f"  Format: gr_complex (32-bit float I + 32-bit float Q)")
        print("")

    def start_streaming(self):
        """Start streaming IQ samples to GNSS-SDR"""
        print("=" * 70)
        print("🚀 Starting IQ sample streaming")
        print("=" * 70)
        print("")

        # Setup RX stream
        self.stream = self.sdr.setupStream(SoapySDR.SOAPY_SDR_RX, SoapySDR.SOAPY_SDR_CF32)
        self.sdr.activateStream(self.stream)

        print("✓ SDR stream active")
        print(f"✓ Streaming to GNSS-SDR at {self.gnss_sdr_host}:{self.gnss_sdr_port}")
        print("")
        print("Status updates every 5 seconds...")
        print("Press Ctrl+C to stop")
        print("")

        self.running = True

        # Buffer for receiving samples
        buffer_size = 8192  # samples per read
        buff = np.zeros(buffer_size, dtype=np.complex64)

        # Stats
        total_samples = 0
        total_bytes = 0
        start_time = time.time()
        last_report = time.time()

        try:
            while self.running:
                # Read samples from SDR
                sr = self.sdr.readStream(self.stream, [buff], len(buff), timeoutUs=1000000)

                if sr.ret > 0:
                    num_samples = sr.ret

                    # Convert to bytes (gr_complex format: float32 I, float32 Q)
                    # GNSS-SDR expects little-endian floats
                    iq_bytes = buff[:num_samples].tobytes()

                    # Split into UDP-sized chunks (max 1472 bytes per packet)
                    # Each complex sample is 8 bytes (2 floats), so 184 samples per packet
                    max_udp_payload = 1472
                    for i in range(0, len(iq_bytes), max_udp_payload):
                        chunk = iq_bytes[i:i + max_udp_payload]
                        self.udp_socket.sendto(chunk, (self.gnss_sdr_host, self.gnss_sdr_port))

                    # Update stats
                    total_samples += num_samples
                    total_bytes += len(iq_bytes)

                    # Report every 5 seconds
                    now = time.time()
                    if now - last_report >= 5.0:
                        elapsed = now - start_time
                        sample_rate_actual = total_samples / elapsed / 1e6
                        data_rate_mbps = (total_bytes * 8) / elapsed / 1e6

                        print(f"[{time.strftime('%H:%M:%S')}] "
                              f"📡 {total_samples / 1e6:.1f} MSamples | "
                              f"Rate: {sample_rate_actual:.3f} MSPS | "
                              f"UDP: {data_rate_mbps:.1f} Mbps")

                        last_report = now

        except KeyboardInterrupt:
            print("\n\n⏹️  Stopping stream...")
            self.running = False

    def cleanup(self):
        """Cleanup resources"""
        print("\n🧹 Cleaning up...")

        if self.stream:
            try:
                self.sdr.deactivateStream(self.stream)
                self.sdr.closeStream(self.stream)
                print("✓ SDR stream closed")
            except:
                pass

        if self.bias_tee and self.tuner == 2:
            try:
                self.sdr.writeSetting("biastee_ctrl", "false")
                print("✓ Bias-T disabled")
            except:
                pass

        if self.sdr:
            self.sdr = None
            print("✓ SDR device closed")

        if self.udp_socket:
            self.udp_socket.close()
            print("✓ UDP socket closed")

        print("\n✅ Cleanup complete!")


def main():
    parser = argparse.ArgumentParser(
        description='Stream SDRPlay IQ samples to GNSS-SDR via UDP',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # GPS L1 with Tuner 2 and bias-T (active antenna)
  python3 sdrplay_to_gnss_sdr.py --freq 1575.42e6 --rate 2.048e6 --gain 40 --tuner 2 --bias-tee

  # GPS L1 with Tuner 1 (passive antenna)
  python3 sdrplay_to_gnss_sdr.py --freq 1575.42e6 --rate 2.048e6 --gain 40 --tuner 1

  # Galileo E1
  python3 sdrplay_to_gnss_sdr.py --freq 1575.42e6 --rate 2.048e6 --gain 40 --tuner 2 --bias-tee

  # GLONASS L1
  python3 sdrplay_to_gnss_sdr.py --freq 1602e6 --rate 2.048e6 --gain 40 --tuner 2 --bias-tee

Make sure GNSS-SDR is running and configured with Custom_UDP_Signal_Source on port 5555.
        """
    )

    parser.add_argument('--freq', type=float, required=True,
                        help='Center frequency in Hz (e.g., 1575.42e6 for GPS L1)')
    parser.add_argument('--rate', type=float, default=2.048e6,
                        help='Sample rate in Hz (default: 2.048e6)')
    parser.add_argument('--gain', type=float, default=40,
                        help='RF gain in dB (default: 40)')
    parser.add_argument('--tuner', type=int, default=2, choices=[1, 2],
                        help='RSPduo tuner selection (default: 2)')
    parser.add_argument('--bias-tee', action='store_true',
                        help='Enable bias-T for active antenna (Tuner 2 only)')
    parser.add_argument('--host', type=str, default='127.0.0.1',
                        help='GNSS-SDR host IP (default: 127.0.0.1)')
    parser.add_argument('--port', type=int, default=5555,
                        help='GNSS-SDR UDP port (default: 5555)')

    args = parser.parse_args()

    # Create streamer
    streamer = SDRPlayToGNSS(
        frequency=args.freq,
        sample_rate=args.rate,
        gain=args.gain,
        tuner=args.tuner,
        bias_tee=args.bias_tee,
        gnss_sdr_host=args.host,
        gnss_sdr_port=args.port
    )

    try:
        # Setup
        streamer.setup_sdr()
        streamer.setup_udp()

        # Start streaming
        streamer.start_streaming()

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        streamer.cleanup()


if __name__ == '__main__':
    main()
