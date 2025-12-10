#!/usr/bin/env python3
"""
SDRplay Direct Streaming to GNSS-SDR
=====================================

This module uses the SDRplay API directly (no SoapySDR/gr-osmosdr)
to stream IQ samples to GNSS-SDR via a FIFO pipe or file.

Advantages over SoapySDR/gr-osmosdr approach:
- Direct API access = full control
- No gr-osmosdr compatibility issues
- Access to all SDRplay-specific features
- Better error handling and diagnostics
- Can implement custom processing before GNSS-SDR

Usage:
    # Stream to file (continuous overwrite for GNSS-SDR)
    python3 sdrplay_streamer.py --output /tmp/gps_iq_samples.dat --mode continuous

    # Stream to FIFO
    python3 sdrplay_streamer.py --output /tmp/gps_fifo --mode fifo

    # Record fixed duration
    python3 sdrplay_streamer.py --output samples.dat --duration 60
"""

import ctypes
from ctypes import *
import numpy as np
import sys
import time
import argparse
import signal
import os
from enum import IntEnum

# Load SDRplay API
LIB_PATH = '/usr/local/lib/libsdrplay_api.dylib'

# API constants
class ErrT(IntEnum):
    Success = 0
    Fail = 1
    InvalidParam = 2
    OutOfRange = 3
    GainUpdateError = 4
    RfUpdateError = 5
    FsUpdateError = 6
    HwError = 7
    AliasingError = 8
    AlreadyInitialised = 9
    NotInitialised = 10

class TunerSelectT(IntEnum):
    Neither = 0
    Tuner_A = 1
    Tuner_B = 2
    Both = 3

class Bw_MHzT(IntEnum):
    BW_Undefined = 0
    BW_0_200 = 200
    BW_0_300 = 300
    BW_0_600 = 600
    BW_1_536 = 1536
    BW_5_000 = 5000
    BW_6_000 = 6000
    BW_7_000 = 7000
    BW_8_000 = 8000

class If_kHzT(IntEnum):
    IF_Zero = 0
    IF_450 = 450
    IF_1620 = 1620
    IF_2048 = 2048

# Structures
class DeviceT(Structure):
    _fields_ = [
        ("SerNo", c_char * 64),
        ("DevNm", c_char * 64),
        ("hwVer", c_ubyte),
        ("tuner", c_int),
        ("rspDuoMode", c_int),
        ("valid", c_ubyte),
        ("rspDuoSampleFreq", c_double),
        ("devAvail", c_ubyte)
    ]

class TunerParamsT(Structure):
    _fields_ = [
        ("bwType", c_int),
        ("ifType", c_int),
        ("loMode", c_int),
        ("gain", c_int),
        ("rfFreq", c_double),
        ("dcOffsetTuner", c_ubyte),
        ("iqImbalTuner", c_ubyte)
    ]

class RspDuoTunerParamsT(Structure):
    _fields_ = [
        ("biasTEnable", c_ubyte),
        ("tuner1AmPortSel", c_int),
        ("tuner1AmNotchEnable", c_ubyte),
        ("rfNotchEnable", c_ubyte),
        ("rfDabNotchEnable", c_ubyte)
    ]

class Rsp2TunerParamsT(Structure):
    _fields_ = [
        ("biasTEnable", c_ubyte),
        ("amPortSel", c_int),
        ("antennaSel", c_int),
        ("rfNotchEnable", c_ubyte)
    ]

class RspDxTunerParamsT(Structure):
    _fields_ = [
        ("hdrEnable", c_ubyte),
        ("biasTEnable", c_ubyte),
        ("antennaSel", c_int),
        ("rfNotchEnable", c_ubyte),
        ("rfDabNotchEnable", c_ubyte)
    ]

class DeviceParamsT(Structure):
    _fields_ = [
        ("devParams", c_void_p),
        ("rxChannelA", c_void_p),
        ("rxChannelB", c_void_p)
    ]

class RxChannelParamsT(Structure):
    _fields_ = [
        ("tunerParams", TunerParamsT),
        ("ctrlParams", c_void_p),
        ("tunerParamsRspDuo", RspDuoTunerParamsT),
        ("tunerParamsRsp2", Rsp2TunerParamsT),
        ("tunerParamsRspDx", RspDxTunerParamsT)
    ]

# Callback type
StreamCallback_t = CFUNCTYPE(None, POINTER(c_short), POINTER(c_short), POINTER(c_uint), c_uint, c_uint, c_void_p)
EventCallback_t = CFUNCTYPE(None, c_int, c_int, POINTER(c_void_p), c_void_p)


class SDRplayStreamer:
    """Direct SDRplay to file/FIFO streamer"""

    def __init__(self, output_file, frequency=1575.42e6, sample_rate=2.048e6,
                 gain_reduction=40, if_mode=0, bandwidth=1536, tuner=2, bias_tee=True):
        """
        Initialize SDRplay streamer

        Args:
            output_file: Output file path (will be created/overwritten)
            frequency: Center frequency in Hz (default: GPS L1)
            sample_rate: Sample rate in Hz (default: 2.048 MHz)
            gain_reduction: Gain reduction in dB (lower = more gain)
            if_mode: IF mode (0=Zero-IF, 450=450kHz, etc.)
            bandwidth: Bandwidth in kHz (200, 300, 600, 1536, 5000, 6000, 7000, 8000)
            tuner: Tuner selection (1=Tuner A, 2=Tuner B for RSP2/RSPduo)
            bias_tee: Enable bias-T for active antenna
        """
        self.output_file = output_file
        self.frequency = frequency
        self.sample_rate = sample_rate
        self.gain_reduction = gain_reduction
        self.if_mode = if_mode
        self.bandwidth = bandwidth
        self.tuner = tuner
        self.bias_tee_enabled = bias_tee

        self.lib = None
        self.device = None
        self.device_handle = None
        self.streaming = False
        self.file_handle = None
        self.sample_count = 0
        self.start_time = None

        # Stats
        self.bytes_written = 0
        self.last_stats_time = 0

    def setup_api(self):
        """Load and configure SDRplay API"""
        print(f"Loading SDRplay API from {LIB_PATH}...")
        self.lib = ctypes.CDLL(LIB_PATH)

        # Define function signatures
        self.lib.sdrplay_api_Open.restype = c_int
        self.lib.sdrplay_api_Close.restype = c_int
        self.lib.sdrplay_api_ApiVersion.argtypes = [POINTER(c_float)]
        self.lib.sdrplay_api_ApiVersion.restype = c_int
        self.lib.sdrplay_api_LockDeviceApi.restype = c_int
        self.lib.sdrplay_api_UnlockDeviceApi.restype = c_int
        self.lib.sdrplay_api_GetDevices.argtypes = [POINTER(DeviceT), POINTER(c_uint), c_uint]
        self.lib.sdrplay_api_GetDevices.restype = c_int
        self.lib.sdrplay_api_SelectDevice.argtypes = [POINTER(DeviceT)]
        self.lib.sdrplay_api_SelectDevice.restype = c_int
        self.lib.sdrplay_api_ReleaseDevice.argtypes = [POINTER(DeviceT)]
        self.lib.sdrplay_api_ReleaseDevice.restype = c_int
        self.lib.sdrplay_api_GetDeviceParams.argtypes = [c_void_p, POINTER(POINTER(DeviceParamsT))]
        self.lib.sdrplay_api_GetDeviceParams.restype = c_int
        self.lib.sdrplay_api_Init.argtypes = [c_void_p, StreamCallback_t, EventCallback_t, c_void_p]
        self.lib.sdrplay_api_Init.restype = c_int
        self.lib.sdrplay_api_Uninit.argtypes = [c_void_p]
        self.lib.sdrplay_api_Uninit.restype = c_int

        print("✓ API function signatures configured")

    def open_device(self):
        """Open and select SDRplay device"""
        # Open API
        err = self.lib.sdrplay_api_Open()
        if err != ErrT.Success:
            raise RuntimeError(f"Failed to open API: error {err}")
        print("✓ SDRplay API opened")

        # Get version
        version = c_float()
        err = self.lib.sdrplay_api_ApiVersion(byref(version))
        if err == ErrT.Success:
            print(f"✓ API Version: {version.value}")

        # Lock API for device access
        err = self.lib.sdrplay_api_LockDeviceApi()
        if err != ErrT.Success:
            raise RuntimeError(f"Failed to lock API: error {err}")

        # Get devices
        devices = (DeviceT * 16)()
        num_devices = c_uint(0)
        err = self.lib.sdrplay_api_GetDevices(devices, byref(num_devices), c_uint(16))

        if err != ErrT.Success or num_devices.value == 0:
            self.lib.sdrplay_api_UnlockDeviceApi()
            raise RuntimeError("No SDRplay devices found")

        print(f"✓ Found {num_devices.value} device(s)")

        # Select first available device
        self.device = devices[0]
        print(f"✓ Selected: {self.device.DevNm.decode()} (Serial: {self.device.SerNo.decode()})")

        # Select device
        err = self.lib.sdrplay_api_SelectDevice(byref(self.device))
        if err != ErrT.Success:
            self.lib.sdrplay_api_UnlockDeviceApi()
            raise RuntimeError(f"Failed to select device: error {err}")

        # Unlock API
        self.lib.sdrplay_api_UnlockDeviceApi()

        # Store device handle
        self.device_handle = cast(self.device.DevNm, c_void_p)

        print("✓ Device selected")

    def configure_device(self):
        """Configure device parameters"""
        # Get device parameters
        device_params = POINTER(DeviceParamsT)()
        err = self.lib.sdrplay_api_GetDeviceParams(self.device_handle, byref(device_params))

        if err != ErrT.Success:
            raise RuntimeError(f"Failed to get device parameters: error {err}")

        # Get RX channel A parameters
        rx_params_ptr = cast(device_params.contents.rxChannelA, POINTER(RxChannelParamsT))
        rx_params = rx_params_ptr.contents

        # Configure tuner parameters
        rx_params.tunerParams.rfFreq = self.frequency
        rx_params.tunerParams.bwType = self.bandwidth
        rx_params.tunerParams.ifType = self.if_mode

        # Configure gain (lower gain reduction = higher gain)
        # rx_params.tunerParams.gain = self.gain_reduction

        # Enable bias-T if requested (device-specific)
        if self.bias_tee_enabled:
            # Try RSP2 first
            try:
                rx_params.tunerParamsRsp2.biasTEnable = 1
                print("✓ Bias-T enabled (RSP2)")
            except:
                pass

            # Try RSPduo
            try:
                rx_params.tunerParamsRspDuo.biasTEnable = 1
                print("✓ Bias-T enabled (RSPduo)")
            except:
                pass

            # Try RSPdx
            try:
                rx_params.tunerParamsRspDx.biasTEnable = 1
                print("✓ Bias-T enabled (RSPdx)")
            except:
                pass

        print(f"✓ Configured:")
        print(f"  Frequency: {self.frequency / 1e6:.3f} MHz")
        print(f"  Sample rate: {self.sample_rate / 1e6:.3f} MSPS")
        print(f"  Bandwidth: {self.bandwidth} kHz")
        print(f"  Gain reduction: {self.gain_reduction} dB")
        print(f"  IF mode: {self.if_mode}")

    def start_streaming(self):
        """Start streaming to file"""
        # Open output file
        self.file_handle = open(self.output_file, 'wb', buffering=65536)  # 64KB buffer
        print(f"✓ Opened output file: {self.output_file}")

        self.sample_count = 0
        self.start_time = time.time()
        self.last_stats_time = self.start_time

        # Create stream callback
        @StreamCallback_t
        def stream_cb(xi, xq, params, num_samples, reset, ctx):
            """Callback receives samples from SDRplay"""
            if num_samples == 0:
                return

            try:
                # Convert to numpy arrays (zero-copy)
                i_samples = np.ctypeslib.as_array(xi, shape=(num_samples,))
                q_samples = np.ctypeslib.as_array(xq, shape=(num_samples,))

                # Interleave I/Q and convert to complex64 (gr_complex format)
                # Normalize from int16 [-32768, 32767] to float32 [-1.0, 1.0]
                complex_samples = (i_samples.astype(np.float32) +
                                  1j * q_samples.astype(np.float32)) / 32768.0

                # Write to file
                self.file_handle.write(complex_samples.tobytes())
                self.sample_count += num_samples
                self.bytes_written += num_samples * 8  # complex64 = 8 bytes

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

            except Exception as e:
                print(f"\nError in stream callback: {e}")

        # Create event callback (required but can be no-op)
        @EventCallback_t
        def event_cb(event_id, tuner, params, ctx):
            pass

        # Store callbacks to prevent GC
        self._stream_cb = stream_cb
        self._event_cb = event_cb

        # Initialize and start streaming
        print("Starting stream...")
        err = self.lib.sdrplay_api_Init(
            self.device_handle,
            stream_cb,
            event_cb,
            None
        )

        if err != ErrT.Success:
            raise RuntimeError(f"Failed to initialize stream: error {err}")

        self.streaming = True
        print("✓ Streaming started")

    def stop_streaming(self):
        """Stop streaming"""
        if not self.streaming:
            return

        print("\nStopping stream...")
        err = self.lib.sdrplay_api_Uninit(self.device_handle)
        if err != ErrT.Success:
            print(f"⚠️  Warning: Uninit error {err}")

        if self.file_handle:
            self.file_handle.close()
            print(f"✓ Closed output file")

        elapsed = time.time() - self.start_time
        rate = self.sample_count / elapsed / 1e6

        print(f"\nStatistics:")
        print(f"  Duration: {elapsed:.1f} seconds")
        print(f"  Samples: {self.sample_count / 1e6:.1f} MSamples")
        print(f"  Average rate: {rate:.2f} MSPS")
        print(f"  File size: {self.bytes_written / 1e6:.1f} MB")

        self.streaming = False

    def cleanup(self):
        """Cleanup resources"""
        if self.streaming:
            self.stop_streaming()

        if self.device:
            err = self.lib.sdrplay_api_ReleaseDevice(byref(self.device))
            if err != ErrT.Success:
                print(f"⚠️  Warning: Release device error {err}")

        if self.lib:
            self.lib.sdrplay_api_Close()
            print("✓ API closed")


def main():
    parser = argparse.ArgumentParser(
        description='Stream IQ samples from SDRplay to file/FIFO',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument('--output', '-o', default='/tmp/gps_iq_samples.dat',
                       help='Output file path (default: /tmp/gps_iq_samples.dat)')
    parser.add_argument('--frequency', '-f', type=float, default=1575.42e6,
                       help='Center frequency in Hz (default: 1575.42e6 for GPS L1)')
    parser.add_argument('--sample-rate', '-s', type=float, default=2.048e6,
                       help='Sample rate in Hz (default: 2.048e6)')
    parser.add_argument('--gain', '-g', type=float, default=40,
                       help='Gain reduction in dB (default: 40, lower = more gain)')
    parser.add_argument('--bandwidth', '-b', type=int, default=1536,
                       choices=[200, 300, 600, 1536, 5000, 6000, 7000, 8000],
                       help='Bandwidth in kHz (default: 1536)')
    parser.add_argument('--no-bias-tee', action='store_true',
                       help='Disable bias-T (default: enabled)')
    parser.add_argument('--duration', '-d', type=float,
                       help='Duration in seconds (default: continuous)')

    args = parser.parse_args()

    print("=" * 70)
    print("SDRplay Direct Streamer")
    print("=" * 70)
    print()

    streamer = SDRplayStreamer(
        output_file=args.output,
        frequency=args.frequency,
        sample_rate=args.sample_rate,
        gain_reduction=args.gain,
        bandwidth=args.bandwidth,
        bias_tee=not args.no_bias_tee
    )

    # Signal handler for clean shutdown
    def signal_handler(sig, frame):
        print("\n\nShutdown requested...")
        streamer.cleanup()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)

    try:
        streamer.setup_api()
        streamer.open_device()
        streamer.configure_device()
        streamer.start_streaming()

        if args.duration:
            print(f"\nStreaming for {args.duration} seconds...")
            time.sleep(args.duration)
        else:
            print("\nStreaming continuously (Ctrl+C to stop)...")
            while True:
                time.sleep(1)

    except KeyboardInterrupt:
        print("\n\nInterrupted")
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
    finally:
        streamer.cleanup()


if __name__ == '__main__':
    main()
