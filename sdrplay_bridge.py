#!/usr/bin/env python3
"""
SDRPlay to Web-Spectrum Bridge

This script interfaces with SDRPlay devices (RSPdx, RSPduo, etc.) and streams IQ samples
to the web-spectrum application via WebSocket, allowing GPS/GNSS signal analysis with
a higher-quality SDR.

Requirements:
    pip install soapy_sdr websockets numpy

Hardware Requirements:
    - SDRPlay device (RSPdx, RSPduo, RSP1A, etc.)
    - SDRPlay API installed (https://www.sdrplay.com/downloads/)
    - SoapySDR with SDRPlay support

Usage:
    python sdrplay_bridge.py [--freq FREQ] [--rate RATE] [--gain GAIN] [--port PORT]
                             [--tuner {1,2}] [--bias-tee]

Examples:
    # GPS L1 on RSPdx
    python sdrplay_bridge.py --freq 1575.42e6 --rate 2.048e6 --gain 40

    # GPS L1 on RSPduo with Tuner 2 and active antenna (T-bias enabled)
    python sdrplay_bridge.py --freq 1575.42e6 --rate 2.048e6 --gain 40 --tuner 2 --bias-tee

    # GPS L2 on RSPduo Tuner 1
    python sdrplay_bridge.py --freq 1227.60e6 --rate 2.048e6 --gain 40 --tuner 1

    # Galileo E1 with active antenna
    python sdrplay_bridge.py --freq 1575.42e6 --rate 2.048e6 --gain 40 --tuner 2 --bias-tee
"""

import asyncio
import websockets
import numpy as np
import argparse
import sys
import signal
from datetime import datetime

try:
    import SoapySDR
    from SoapySDR import SOAPY_SDR_RX, SOAPY_SDR_CF32
except ImportError:
    print("ERROR: SoapySDR not installed!")
    print("Make sure SoapySDR is installed via Homebrew:")
    print("  brew install soapysdr")
    print("")
    print("And run this script using the wrapper:")
    print("  ./run_sdrplay_bridge.sh")
    sys.exit(1)


class SDRPlayBridge:
    def __init__(self, frequency=1575.42e6, sample_rate=2.048e6, gain=40, port=8765,
                 tuner=1, bias_tee=False):
        """
        Initialize SDRPlay bridge

        Args:
            frequency: Center frequency in Hz (default: 1575.42 MHz for GPS L1)
            sample_rate: Sample rate in Hz (default: 2.048 MSPS to match RTL-SDR)
            gain: RF gain in dB (default: 40 dB)
            port: WebSocket server port (default: 8765)
            tuner: Tuner selection for RSPduo (1 or 2, default: 1)
            bias_tee: Enable T-bias for active antenna (RSPduo Tuner 2 only, default: False)
        """
        self.frequency = frequency
        self.sample_rate = sample_rate
        self.gain = gain
        self.port = port
        self.tuner = tuner
        self.bias_tee = bias_tee
        self.sdr = None
        self.stream = None
        self.running = False
        self.clients = set()
        self.device_model = None
        self.is_rspduo = False

        # Buffer size for reading samples (1024 samples = ~0.5ms at 2.048 MSPS)
        self.buffer_size = 16384  # 8ms of data

    def setup_sdr(self):
        """Initialize and configure SDRPlay device"""
        try:
            # Find SDRPlay device
            print("Searching for SDRPlay devices...")
            results = SoapySDR.Device.enumerate()

            if not results:
                print("ERROR: No SDRPlay devices found!")
                print("Make sure:")
                print("  1. SDRPlay API is installed (https://www.sdrplay.com/downloads/)")
                print("  2. Device is connected")
                print("  3. SoapySDR has SDRPlay support (run: SoapySDRUtil --find)")
                return False

            print(f"Found {len(results)} device(s):")
            for i, result in enumerate(results):
                print(f"  [{i}] {result}")

            # Detect RSPduo from enumeration results
            device_info = results[0]
            # Check if 'label' field contains 'RSPduo'
            if 'label' in device_info:
                self.device_model = device_info['label']
                self.is_rspduo = 'RSPduo' in self.device_model
            else:
                self.device_model = 'Unknown'
                self.is_rspduo = False

            # For RSPduo, select the Single Tuner mode (Dev0) and specify which tuner
            if self.is_rspduo:
                # Find the Single Tuner device (mode=ST)
                rspduo_device = None
                for result in results:
                    if 'mode' in result and result['mode'] == 'ST':
                        rspduo_device = result
                        break

                if rspduo_device is None:
                    rspduo_device = results[0]  # Fallback to first device

                # Build device arguments string for RSPduo with tuner selection
                # Format: "driver=sdrplay,serial=XXXXX,rfnotch_ctrl=false,dabnotch_ctrl=false"
                try:
                    serial = rspduo_device['serial']
                except KeyError:
                    serial = ''

                # For RSPduo Single Tuner mode, the selected tuner is controlled by the 'antenna' setting
                # after opening, not at device construction time. Open the device in ST mode.
                print(f"\nOpening RSPduo in Single Tuner mode...")
                print(f"  Will configure for Tuner {self.tuner}")
                self.sdr = SoapySDR.Device(rspduo_device)
            else:
                # Non-RSPduo devices
                self.sdr = SoapySDR.Device(results[0])

            hw_info = self.sdr.getHardwareInfo()
            print(f"\nOpened: {hw_info}")

            if self.is_rspduo:
                print(f"  RSPduo detected!")
                print(f"  Selected Tuner: {self.tuner}")
                print(f"  T-bias: {'ENABLED' if self.bias_tee else 'DISABLED'}")

                # Set RSPduo tuner selection BEFORE other configuration
                # This is done via the 'rfnotch_ctrl' setting or 'tuner_sel' setting
                try:
                    # Try setting tuner selection
                    tuner_value = "Tuner 1" if self.tuner == 1 else "Tuner 2"

                    # Try different setting names for tuner selection
                    tuner_set = False
                    for setting_name in ['tuner_sel', 'rfnotch_ctrl', 'antenna']:
                        try:
                            self.sdr.writeSetting(setting_name, tuner_value)
                            print(f"  Tuner selected via '{setting_name}': {tuner_value}")
                            tuner_set = True
                            break
                        except:
                            continue

                    if not tuner_set:
                        print(f"  Note: Tuner selection via settings not available, will use antenna selection")
                except Exception as e:
                    print(f"  Note: Could not set tuner via settings: {e}")

            # Configure device
            print(f"\nConfiguring device:")
            print(f"  Frequency: {self.frequency / 1e6:.2f} MHz")
            print(f"  Sample Rate: {self.sample_rate / 1e6:.3f} MSPS")
            print(f"  Gain: {self.gain} dB")

            # Channel selection
            channel = 0  # Default channel

            # Set sample rate
            self.sdr.setSampleRate(SOAPY_SDR_RX, channel, self.sample_rate)
            actual_rate = self.sdr.getSampleRate(SOAPY_SDR_RX, channel)
            print(f"  Actual Sample Rate: {actual_rate / 1e6:.3f} MSPS")

            # Set center frequency
            self.sdr.setFrequency(SOAPY_SDR_RX, channel, self.frequency)
            actual_freq = self.sdr.getFrequency(SOAPY_SDR_RX, channel)
            print(f"  Actual Frequency: {actual_freq / 1e6:.6f} MHz")

            # Disable AGC for manual gain control (important for GPS!)
            self.sdr.setGainMode(SOAPY_SDR_RX, channel, False)
            print(f"  AGC: Disabled (manual gain control)")

            # Set gain
            # RSPduo has multiple gain stages: IFGR (IF Gain Reduction) and RFGR (RF Gain Reduction)
            self.sdr.setGain(SOAPY_SDR_RX, channel, self.gain)
            actual_gain = self.sdr.getGain(SOAPY_SDR_RX, channel)
            print(f"  Actual Gain: {actual_gain} dB")

            # Set antenna (RSPdx has multiple antenna ports, RSPduo has Tuner 1/2)
            antennas = self.sdr.listAntennas(SOAPY_SDR_RX, channel)
            print(f"  Available antennas: {antennas}")

            if self.is_rspduo:
                # RSPduo tuner selection in Single Tuner mode
                # In ST mode, the available antennas should be like "Tuner 1 50 ohm" or similar
                # Try various antenna naming schemes that SoapySDR might use
                possible_names = [
                    f"Tuner {self.tuner} 50 ohm",
                    f"Tuner {self.tuner} Hi-Z",
                    f"Tuner {self.tuner}",
                    f"TUNER_{self.tuner}",
                ]

                antenna_set = False
                for tuner_name in possible_names:
                    if tuner_name in antennas:
                        self.sdr.setAntenna(SOAPY_SDR_RX, channel, tuner_name)
                        print(f"  Selected: {tuner_name}")
                        antenna_set = True
                        break

                if not antenna_set:
                    # Try to find any antenna that contains the tuner number
                    for antenna in antennas:
                        if f"tuner {self.tuner}" in antenna.lower() or f"tuner{self.tuner}" in antenna.lower():
                            self.sdr.setAntenna(SOAPY_SDR_RX, channel, antenna)
                            print(f"  Selected: {antenna}")
                            antenna_set = True
                            break

                if not antenna_set:
                    # Fallback: use first available antenna
                    if antennas:
                        self.sdr.setAntenna(SOAPY_SDR_RX, channel, antennas[0])
                        print(f"  Selected: {antennas[0]} (fallback)")
                        if self.tuner != 1:
                            print(f"  ⚠️  WARNING: Could not find antenna for Tuner {self.tuner}")
                            print(f"  ⚠️  The default tuner will be used instead")
            else:
                # Non-RSPduo devices (e.g., RSPdx)
                if 'Antenna A' in antennas:
                    self.sdr.setAntenna(SOAPY_SDR_RX, channel, 'Antenna A')
                    print(f"  Using: Antenna A")
                elif antennas:
                    self.sdr.setAntenna(SOAPY_SDR_RX, channel, antennas[0])
                    print(f"  Using: {antennas[0]}")

            # RSPduo-specific: Enable T-bias for Tuner 2 if requested
            if self.is_rspduo and self.bias_tee:
                if self.tuner == 2:
                    try:
                        # T-bias is controlled via different possible setting names
                        # Try multiple variants as different driver versions may use different names
                        bias_settings = ["biasT_ctrl", "bias_tx", "biastee_ctrl"]
                        bias_enabled = False

                        for setting_name in bias_settings:
                            try:
                                self.sdr.writeSetting(setting_name, "true")
                                print(f"  T-bias: ENABLED on Tuner 2 (via {setting_name})")
                                bias_enabled = True
                                break
                            except:
                                continue

                        if not bias_enabled:
                            print(f"  WARNING: Failed to enable T-bias")
                            print(f"  T-bias may not be supported by this driver version")
                            print(f"  Try updating SDRPlay API and SoapySDR")
                    except Exception as e:
                        print(f"  WARNING: Failed to enable T-bias: {e}")
                else:
                    print(f"  WARNING: T-bias is only available on Tuner 2, but Tuner {self.tuner} is selected")
                    print(f"  T-bias: DISABLED")

            # Setup stream
            self.stream = self.sdr.setupStream(SOAPY_SDR_RX, SOAPY_SDR_CF32, [channel])
            print("\nSDRPlay configured successfully!")
            return True

        except Exception as e:
            print(f"ERROR setting up SDRPlay: {e}")
            return False

    def start_streaming(self):
        """Start SDR streaming"""
        if self.stream:
            self.sdr.activateStream(self.stream)
            self.running = True
            print("Streaming started!")

    def stop_streaming(self):
        """Stop SDR streaming"""
        if self.stream and self.running:
            self.sdr.deactivateStream(self.stream)
            self.running = False
            print("Streaming stopped!")

    def read_samples(self):
        """Read IQ samples from SDR and convert to uint8 format (RTL-SDR compatible)"""
        if not self.stream or not self.running:
            return None

        # Read complex float samples
        buffer = np.zeros(self.buffer_size, dtype=np.complex64)
        sr = self.sdr.readStream(self.stream, [buffer], self.buffer_size, timeoutUs=1000000)

        if sr.ret > 0:
            # Convert complex float to interleaved I/Q uint8 (RTL-SDR format)
            # SoapySDR gives [-1, +1], convert to [0, 255]
            samples = buffer[:sr.ret]

            # Separate I and Q
            i_samples = np.real(samples)
            q_samples = np.imag(samples)

            # Convert to uint8 [0, 255] with 127.5 as center
            i_uint8 = np.clip((i_samples * 127.5 + 127.5), 0, 255).astype(np.uint8)
            q_uint8 = np.clip((q_samples * 127.5 + 127.5), 0, 255).astype(np.uint8)

            # Interleave I and Q
            iq_interleaved = np.empty(sr.ret * 2, dtype=np.uint8)
            iq_interleaved[0::2] = i_uint8
            iq_interleaved[1::2] = q_uint8

            return iq_interleaved.tobytes()

        return None

    async def handle_client(self, websocket):
        """Handle WebSocket client connection"""
        client_addr = websocket.remote_address
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Client connected: {client_addr}")
        self.clients.add(websocket)

        try:
            # Keep connection alive and receive any messages (though we don't expect any)
            async for message in websocket:
                pass  # Ignore any messages from client
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            self.clients.remove(websocket)
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Client disconnected: {client_addr}")

    async def stream_samples(self):
        """Continuously read samples and broadcast to all connected clients"""
        print("Starting sample streaming loop...")
        sample_count = 0
        last_report = datetime.now()

        while self.running:
            # Read samples from SDR
            data = self.read_samples()

            if data and self.clients:
                # Broadcast to all connected clients
                disconnected = set()
                for client in self.clients:
                    try:
                        await client.send(data)
                        sample_count += len(data)
                    except websockets.exceptions.ConnectionClosed:
                        disconnected.add(client)

                # Remove disconnected clients
                self.clients -= disconnected

                # Report throughput every second
                now = datetime.now()
                if (now - last_report).total_seconds() >= 1.0:
                    mbps = (sample_count * 8) / 1e6
                    print(f"[{now.strftime('%H:%M:%S')}] Streaming: {mbps:.2f} Mbps, {len(self.clients)} client(s)")
                    sample_count = 0
                    last_report = now

            # Small delay to prevent CPU spinning
            await asyncio.sleep(0.001)

    async def run_server(self):
        """Run WebSocket server"""
        print(f"\nStarting WebSocket server on port {self.port}...")
        print(f"Connect web-spectrum to: ws://localhost:{self.port}")
        print("\nPress Ctrl+C to stop\n")

        async with websockets.serve(self.handle_client, "0.0.0.0", self.port):
            # Start streaming task
            stream_task = asyncio.create_task(self.stream_samples())

            try:
                await asyncio.Future()  # Run forever
            except asyncio.CancelledError:
                stream_task.cancel()
                raise

    def cleanup(self):
        """Clean up resources"""
        print("\nCleaning up...")
        self.stop_streaming()

        if self.stream:
            self.sdr.closeStream(self.stream)

        if self.sdr:
            self.sdr = None

        print("Cleanup complete!")


def signal_handler(sig, frame):
    """Handle Ctrl+C gracefully"""
    print("\n\nShutdown requested...")
    sys.exit(0)


def main():
    parser = argparse.ArgumentParser(
        description='SDRPlay to Web-Spectrum Bridge',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  GPS L1 (RSPdx):                python sdrplay_bridge.py --freq 1575.42e6 --rate 2.048e6 --gain 40
  GPS L1 (RSPduo Tuner 2):       python sdrplay_bridge.py --freq 1575.42e6 --rate 2.048e6 --gain 40 --tuner 2
  GPS L1 (RSPduo + T-bias):      python sdrplay_bridge.py --freq 1575.42e6 --rate 2.048e6 --gain 40 --tuner 2 --bias-tee
  GPS L2:                        python sdrplay_bridge.py --freq 1227.60e6 --rate 2.048e6 --gain 40
  Galileo E1:                    python sdrplay_bridge.py --freq 1575.42e6 --rate 2.048e6 --gain 40
  GLONASS L1:                    python sdrplay_bridge.py --freq 1602.0e6 --rate 2.048e6 --gain 40

RSPduo Notes:
  - Use --tuner to select Tuner 1 or Tuner 2
  - T-bias (--bias-tee) is only available on Tuner 2
  - T-bias provides power for active antennas (typically 4.5V)
        """
    )

    parser.add_argument('--freq', type=float, default=1575.42e6,
                        help='Center frequency in Hz (default: 1575.42 MHz for GPS L1)')
    parser.add_argument('--rate', type=float, default=2.048e6,
                        help='Sample rate in Hz (default: 2.048 MSPS)')
    parser.add_argument('--gain', type=float, default=40,
                        help='RF gain in dB (default: 40 dB)')
    parser.add_argument('--port', type=int, default=8765,
                        help='WebSocket server port (default: 8765)')
    parser.add_argument('--tuner', type=int, default=1, choices=[1, 2],
                        help='Tuner selection for RSPduo (1 or 2, default: 1)')
    parser.add_argument('--bias-tee', action='store_true',
                        help='Enable T-bias for active antenna (RSPduo Tuner 2 only)')

    args = parser.parse_args()

    # Setup signal handler
    signal.signal(signal.SIGINT, signal_handler)

    # Create bridge
    print("=" * 60)
    print("SDRPlay to Web-Spectrum Bridge")
    print("=" * 60)

    bridge = SDRPlayBridge(
        frequency=args.freq,
        sample_rate=args.rate,
        gain=args.gain,
        port=args.port,
        tuner=args.tuner,
        bias_tee=args.bias_tee
    )

    # Setup SDR
    if not bridge.setup_sdr():
        print("\nFailed to setup SDRPlay. Exiting.")
        sys.exit(1)

    # Start streaming
    bridge.start_streaming()

    # Run WebSocket server
    try:
        asyncio.run(bridge.run_server())
    except KeyboardInterrupt:
        pass
    finally:
        bridge.cleanup()


if __name__ == '__main__':
    main()
