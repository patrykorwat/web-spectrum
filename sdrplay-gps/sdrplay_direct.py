#!/usr/bin/env python3
"""
Direct SDRplay API Interface for Python
========================================

This module provides direct access to the SDRplay API without going through
SoapySDR or gr-osmosdr, giving full control over the device and data stream.

Features:
- Direct ctypes bindings to SDRplay API (libsdrplay_api.so/dylib)
- Full control over all device parameters
- High-performance streaming callback architecture
- Support for all SDRplay devices (RSP1, RSP1A, RSP2, RSPduo, RSPdx)
- Bias-T control, tuner selection, gain modes
- Zero-copy data access for maximum throughput

Requirements:
- SDRplay API 3.x installed (get from sdrplay.com)
- Location: macOS: /Library/Frameworks/sdrplay_api.framework
           Linux: /usr/local/lib/libsdrplay_api.so

Usage Example:
    from sdrplay_direct import SDRplayDevice

    def data_callback(samples):
        # samples is numpy array of complex64
        print(f"Received {len(samples)} samples")

    sdr = SDRplayDevice()
    sdr.set_frequency(1575.42e6)  # GPS L1
    sdr.set_sample_rate(2.048e6)
    sdr.set_gain(40)
    sdr.set_bias_tee(True)
    sdr.start_streaming(data_callback)

    # Stream runs in background thread
    time.sleep(60)
    sdr.stop_streaming()
"""

import ctypes
import numpy as np
from ctypes import *
import sys
import platform
import threading
import time
from typing import Callable, Optional
from enum import IntEnum

# Platform-specific library loading
if platform.system() == 'Darwin':  # macOS
    LIB_PATH = '/usr/local/lib/libsdrplay_api.dylib'
    # Try framework path if dylib not found
    import os
    if not os.path.exists(LIB_PATH):
        LIB_PATH = '/Library/Frameworks/sdrplay_api.framework/sdrplay_api'
elif platform.system() == 'Linux':
    LIB_PATH = 'libsdrplay_api.so'
elif platform.system() == 'Windows':
    LIB_PATH = 'sdrplay_api.dll'
else:
    raise RuntimeError(f"Unsupported platform: {platform.system()}")


# SDRplay API Constants
class sdrplay_api_ErrT(IntEnum):
    """Error codes from SDRplay API"""
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
    NotEnabled = 11
    HwVerError = 12
    OutOfMemError = 13
    ServiceNotResponding = 14
    StartPending = 15
    StopPending = 16
    InvalidMode = 17
    FailedVerification1 = 18
    FailedVerification2 = 19
    FailedVerification3 = 20
    FailedVerification4 = 21
    FailedVerification5 = 22
    FailedVerification6 = 23
    InvalidServiceVersion = 24


class sdrplay_api_TunerSelectT(IntEnum):
    """Tuner selection for dual-tuner devices"""
    Neither = 0
    Tuner_A = 1
    Tuner_B = 2
    Both = 3


class sdrplay_api_If_kHzT(IntEnum):
    """IF frequency selection"""
    IF_Zero = 0
    IF_450 = 450
    IF_1620 = 1620
    IF_2048 = 2048


class sdrplay_api_Bw_MHzT(IntEnum):
    """Bandwidth selection"""
    BW_Undefined = 0
    BW_0_200 = 200
    BW_0_300 = 300
    BW_0_600 = 600
    BW_1_536 = 1536
    BW_5_000 = 5000
    BW_6_000 = 6000
    BW_7_000 = 7000
    BW_8_000 = 8000


class sdrplay_api_TransferModeT(IntEnum):
    """Transfer mode enumeration"""
    ISOCH = 0
    BULK = 1


class sdrplay_api_RspDuoModeT(IntEnum):
    """RSPduo mode enumeration"""
    Unknown = 0
    Single_Tuner = 1
    Dual_Tuner = 2
    Master = 4
    Slave = 8


class sdrplay_api_AgcControlT(IntEnum):
    """AGC control enumeration"""
    DISABLE = 0
    AGC_100HZ = 1
    AGC_50HZ = 2
    AGC_5HZ = 3
    AGC_CTRL_EN = 4


class sdrplay_api_AdsbModeT(IntEnum):
    """ADS-B mode enumeration"""
    DECIMATION = 0
    NO_DECIMATION_LOWPASS = 1
    NO_DECIMATION_BANDPASS_2MHZ = 2
    NO_DECIMATION_BANDPASS_3MHZ = 3


class sdrplay_api_LoModeT(IntEnum):
    """LO mode enumeration"""
    Undefined = 0
    Auto = 1
    LO_120MHz = 2
    LO_144MHz = 3
    LO_168MHz = 4


class sdrplay_api_MinGainReductionT(IntEnum):
    """Minimum gain reduction enumeration"""
    EXTENDED_MIN_GR = 0
    NORMAL_MIN_GR = 20


class sdrplay_api_EventT(IntEnum):
    """Event types for event callback"""
    GainChange = 0
    PowerOverloadChange = 1
    DeviceRemoved = 2
    RspDuoModeChange = 3


class sdrplay_api_PowerOverloadCbEventIdT(IntEnum):
    """Power overload change types"""
    Overload_Detected = 0
    Overload_Corrected = 1


class sdrplay_api_ReasonForUpdateT(IntEnum):
    """Reason for update enumeration"""
    Update_None = 0x00000000
    Update_Dev_Fs = 0x00000001
    Update_Dev_Ppm = 0x00000002
    Update_Dev_SyncUpdate = 0x00000004
    Update_Dev_ResetFlags = 0x00000008
    Update_Rsp1a_BiasTControl = 0x00000010
    Update_Rsp1a_RfNotchControl = 0x00000020
    Update_Rsp1a_RfDabNotchControl = 0x00000040
    Update_Rsp2_BiasTControl = 0x00000080
    Update_Rsp2_AmPortSelect = 0x00000100
    Update_Rsp2_AntennaControl = 0x00000200
    Update_Rsp2_RfNotchControl = 0x00000400
    Update_Rsp2_ExtRefControl = 0x00000800
    Update_RspDuo_BiasTControl = 0x00001000
    Update_RspDuo_AmPortSelect = 0x00002000
    Update_RspDuo_Tuner1AmNotchControl = 0x00004000
    Update_RspDuo_RfNotchControl = 0x00008000
    Update_RspDuo_RfDabNotchControl = 0x00010000
    Update_Tuner_Gr = 0x00020000
    Update_Tuner_GrLimits = 0x00040000
    Update_Tuner_Frf = 0x00080000
    Update_Tuner_BwType = 0x00100000
    Update_Tuner_IfType = 0x00200000
    Update_Tuner_DcOffset = 0x00400000
    Update_Tuner_LoMode = 0x00800000
    Update_Ctrl_DCoffsetIQimbalance = 0x01000000
    Update_Ctrl_Decimation = 0x02000000
    Update_Ctrl_Agc = 0x04000000
    Update_Ctrl_AdsbMode = 0x08000000
    Update_Ctrl_OverloadMsgAck = 0x10000000


class sdrplay_api_ReasonForUpdateExtension1T(IntEnum):
    """Extension 1 reason for update enumeration"""
    Update_Ext1_None = 0x00000000


# Error info structure
class sdrplay_api_ErrorInfoT(Structure):
    """Extended error message structure"""
    _fields_ = [
        ("file", c_char * 256),
        ("function", c_char * 256),
        ("line", c_int),
        ("message", c_char * 1024)
    ]


# Structure definitions (matching sdrplay_api.h)
class sdrplay_api_DeviceT(Structure):
    """Device descriptor - matches sdrplay_api.h exactly"""
    _fields_ = [
        ("SerNo", c_char * 64),  # char SerNo[SDRPLAY_MAX_SER_NO_LEN]
        ("hwVer", c_ubyte),       # unsigned char hwVer
        ("tuner", c_int),         # sdrplay_api_TunerSelectT tuner
        ("rspDuoMode", c_int),    # sdrplay_api_RspDuoModeT rspDuoMode
        ("valid", c_ubyte),       # unsigned char valid
        ("rspDuoSampleFreq", c_double),  # double rspDuoSampleFreq
        ("dev", c_void_p)         # HANDLE dev - device handle
    ]


# Forward declarations for complex structures
class sdrplay_api_RxChannelParamsT(Structure):
    """RX channel parameters - forward declaration"""
    pass


class sdrplay_api_DevParamsT(Structure):
    """Device parameters - forward declaration"""
    pass


# ADC sampling frequency parameters structure
class sdrplay_api_FsFreqT(Structure):
    """ADC sampling frequency parameters"""
    _fields_ = [
        ("fsHz", c_double),        # default: 2000000.0
        ("syncUpdate", c_ubyte),   # default: 0
        ("reCal", c_ubyte)         # default: 0
    ]


# Synchronous update parameters structure
class sdrplay_api_SyncUpdateT(Structure):
    """Synchronous update parameters"""
    _fields_ = [
        ("sampleNum", c_uint),     # default: 0
        ("period", c_uint)         # default: 0
    ]


# Reset update operations structure
class sdrplay_api_ResetFlagsT(Structure):
    """Reset update operations"""
    _fields_ = [
        ("resetGainUpdate", c_ubyte),  # default: 0
        ("resetRfUpdate", c_ubyte),    # default: 0
        ("resetFsUpdate", c_ubyte)     # default: 0
    ]


# Device-specific parameters (simplified for now)
class sdrplay_api_Rsp1aParamsT(Structure):
    """RSP1A specific parameters"""
    _fields_ = [
        ("rfNotchEnable", c_ubyte),    # default: 0
        ("rfDabNotchEnable", c_ubyte)  # default: 0
    ]


class sdrplay_api_Rsp2ParamsT(Structure):
    """RSP2 specific parameters"""
    _fields_ = [
        ("extRefOutputEn", c_ubyte)    # default: 0
    ]


class sdrplay_api_RspDuoParamsT(Structure):
    """RSPduo specific parameters"""
    _fields_ = [
        ("extRefOutputEn", c_int)      # default: 0
    ]


class sdrplay_api_RspDxParamsT(Structure):
    """RSPdx specific parameters"""
    _fields_ = [
        ("hdrEnable", c_ubyte),        # default: 0
        ("biasTEnable", c_ubyte),      # default: 0
        ("antennaSel", c_int),         # sdrplay_api_RspDx_AntennaSelectT
        ("rfNotchEnable", c_ubyte),    # default: 0
        ("rfDabNotchEnable", c_ubyte)  # default: 0
    ]


# Complete device parameters structure
sdrplay_api_DevParamsT._fields_ = [
    ("ppm", c_double),                           # default: 0.0
    ("fsFreq", sdrplay_api_FsFreqT),            # ADC sampling frequency
    ("syncUpdate", sdrplay_api_SyncUpdateT),     # Synchronous update
    ("resetFlags", sdrplay_api_ResetFlagsT),     # Reset flags
    ("mode", c_int),                             # sdrplay_api_TransferModeT, default: ISOCH
    ("samplesPerPkt", c_uint),                   # default: 0 (output param)
    ("rsp1aParams", sdrplay_api_Rsp1aParamsT),
    ("rsp2Params", sdrplay_api_Rsp2ParamsT),
    ("rspDuoParams", sdrplay_api_RspDuoParamsT),
    ("rspDxParams", sdrplay_api_RspDxParamsT)
]


class sdrplay_api_DeviceParamsT(Structure):
    """Device parameters container"""
    _fields_ = [
        ("devParams", POINTER(sdrplay_api_DevParamsT)),
        ("rxChannelA", POINTER(sdrplay_api_RxChannelParamsT)),
        ("rxChannelB", POINTER(sdrplay_api_RxChannelParamsT))
    ]


# Gain value structure
class sdrplay_api_GainValuesT(Structure):
    """Current gain values"""
    _fields_ = [
        ("curr", c_float),
        ("max", c_float),
        ("min", c_float)
    ]


# Gain setting parameter structure
class sdrplay_api_GainT(Structure):
    """Gain setting parameters"""
    _fields_ = [
        ("gRdB", c_int),                       # default: 50
        ("LNAstate", c_ubyte),                 # default: 0
        ("syncUpdate", c_ubyte),               # default: 0
        ("minGr", c_int),                      # sdrplay_api_MinGainReductionT, default: NORMAL_MIN_GR
        ("gainVals", sdrplay_api_GainValuesT)  # output parameter
    ]


# RF frequency parameter structure
class sdrplay_api_RfFreqT(Structure):
    """RF frequency parameters"""
    _fields_ = [
        ("rfHz", c_double),                    # default: 200000000.0
        ("syncUpdate", c_ubyte)                # default: 0
    ]


# Event callback parameter structures
class sdrplay_api_GainCbParamT(Structure):
    """Gain change event parameters"""
    _fields_ = [
        ("gRdB", c_uint),
        ("lnaGRdB", c_uint),
        ("currGain", c_float)
    ]


class sdrplay_api_PowerOverloadCbParamT(Structure):
    """Power overload event parameters"""
    _fields_ = [
        ("powerOverloadChangeType", c_uint)  # sdrplay_api_PowerOverloadCbEventIdT
    ]


class sdrplay_api_RspDuoModeCbParamT(Structure):
    """RSPduo mode change event parameters"""
    _fields_ = [
        ("modeChangeType", c_uint)
    ]


class sdrplay_api_EventParamsT(Structure):
    """Event callback parameters union-like structure"""
    _fields_ = [
        ("gainParams", sdrplay_api_GainCbParamT),
        ("powerOverloadParams", sdrplay_api_PowerOverloadCbParamT),
        ("rspDuoModeParams", sdrplay_api_RspDuoModeCbParamT)
    ]


# DC calibration parameter structure
class sdrplay_api_DcOffsetTunerT(Structure):
    """DC calibration parameters"""
    _fields_ = [
        ("dcCal", c_ubyte),                    # default: 3 (Periodic mode)
        ("speedUp", c_ubyte),                  # default: 0 (No speedup)
        ("trackTime", c_int),                  # default: 1
        ("refreshRateTime", c_int)             # default: 2048
    ]


# Tuner parameter structure
class sdrplay_api_TunerParamsT(Structure):
    """Tuner parameters"""
    _fields_ = [
        ("bwType", c_int),                                # sdrplay_api_Bw_MHzT, default: BW_0_200
        ("ifType", c_int),                                # sdrplay_api_If_kHzT, default: IF_Zero
        ("loMode", c_int),                                # sdrplay_api_LoModeT, default: LO_Auto
        ("gain", sdrplay_api_GainT),
        ("rfFreq", sdrplay_api_RfFreqT),
        ("dcOffsetTuner", sdrplay_api_DcOffsetTunerT)
    ]


# DC offset control parameters
class sdrplay_api_DcOffsetT(Structure):
    """DC offset control parameters"""
    _fields_ = [
        ("DCenable", c_ubyte),                 # default: 1
        ("IQenable", c_ubyte)                  # default: 1
    ]


# Decimation control parameters
class sdrplay_api_DecimationT(Structure):
    """Decimation control parameters"""
    _fields_ = [
        ("enable", c_ubyte),                   # default: 0
        ("decimationFactor", c_ubyte),         # default: 1
        ("wideBandSignal", c_ubyte)            # default: 0
    ]


# AGC control parameters
class sdrplay_api_AgcT(Structure):
    """AGC control parameters"""
    _fields_ = [
        ("enable", c_int),                     # sdrplay_api_AgcControlT, default: AGC_50HZ
        ("setPoint_dBfs", c_int),             # default: -60
        ("attack_ms", c_ushort),              # default: 0
        ("decay_ms", c_ushort),               # default: 0
        ("decay_delay_ms", c_ushort),         # default: 0
        ("decay_threshold_dB", c_ushort),     # default: 0
        ("syncUpdate", c_int)                 # default: 0
    ]


# Control parameters structure
class sdrplay_api_ControlParamsT(Structure):
    """Control parameters"""
    _fields_ = [
        ("dcOffset", sdrplay_api_DcOffsetT),
        ("decimation", sdrplay_api_DecimationT),
        ("agc", sdrplay_api_AgcT),
        ("adsbMode", c_int)                   # sdrplay_api_AdsbModeT, default: DECIMATION
    ]


# Tuner-specific parameters for RSP1A
class sdrplay_api_Rsp1aTunerParamsT(Structure):
    """RSP1A tuner-specific parameters"""
    _fields_ = [
        ("biasTEnable", c_ubyte)              # default: 0
    ]


# Tuner-specific parameters for RSP2
class sdrplay_api_Rsp2TunerParamsT(Structure):
    """RSP2 tuner-specific parameters"""
    _fields_ = [
        ("biasTEnable", c_ubyte),             # default: 0
        ("amPortSel", c_int),                 # sdrplay_api_Rsp2_AmPortSelectT
        ("antennaSel", c_int),                # sdrplay_api_Rsp2_AntennaSelectT
        ("rfNotchEnable", c_ubyte)            # default: 0
    ]


# Tuner-specific parameters for RSPduo
class sdrplay_api_RspDuoTunerParamsT(Structure):
    """RSPduo tuner-specific parameters"""
    _fields_ = [
        ("biasTEnable", c_ubyte),             # default: 0
        ("tuner1AmPortSel", c_int),           # sdrplay_api_RspDuo_AmPortSelectT
        ("tuner1AmNotchEnable", c_ubyte),     # default: 0
        ("rfNotchEnable", c_ubyte),           # default: 0
        ("rfDabNotchEnable", c_ubyte)         # default: 0
    ]


# Tuner-specific parameters for RSPdx
class sdrplay_api_RspDxTunerParamsT(Structure):
    """RSPdx tuner-specific parameters"""
    _fields_ = [
        ("hdrBw", c_int)                      # sdrplay_api_RspDx_HdrModeBwT
    ]


# Complete RxChannelParamsT definition
sdrplay_api_RxChannelParamsT._fields_ = [
    ("tunerParams", sdrplay_api_TunerParamsT),
    ("ctrlParams", sdrplay_api_ControlParamsT),
    ("rsp1aTunerParams", sdrplay_api_Rsp1aTunerParamsT),
    ("rsp2TunerParams", sdrplay_api_Rsp2TunerParamsT),
    ("rspDuoTunerParams", sdrplay_api_RspDuoTunerParamsT),
    ("rspDxTunerParams", sdrplay_api_RspDxTunerParamsT)
]


# Stream callback parameters structure
class sdrplay_api_StreamCbParamsT(Structure):
    """Streaming data parameter callback structure"""
    _fields_ = [
        ("firstSampleNum", c_uint),
        ("grChanged", c_int),
        ("rfChanged", c_int),
        ("fsChanged", c_int),
        ("numSamples", c_uint)
    ]


# Callback types
sdrplay_api_StreamCallback_t = CFUNCTYPE(
    None,
    POINTER(c_short),                           # xi (I samples)
    POINTER(c_short),                           # xq (Q samples)
    POINTER(sdrplay_api_StreamCbParamsT),      # params
    c_uint,                                     # numSamples
    c_uint,                                     # reset
    c_void_p                                    # cbContext
)

sdrplay_api_EventCallback_t = CFUNCTYPE(
    None,
    c_uint,                                       # eventId (sdrplay_api_EventT)
    c_uint,                                       # tuner (sdrplay_api_TunerSelectT)
    POINTER(sdrplay_api_EventParamsT),           # params
    c_void_p                                      # cbContext
)


# Callback function structure
class sdrplay_api_CallbackFnsT(Structure):
    """Callback function definition structure"""
    _fields_ = [
        ("StreamACbFn", sdrplay_api_StreamCallback_t),
        ("StreamBCbFn", sdrplay_api_StreamCallback_t),
        ("EventCbFn", sdrplay_api_EventCallback_t)
    ]


class SDRplayDevice:
    """
    Direct interface to SDRplay device via API

    This class provides Pythonic access to SDRplay devices with full control
    over all parameters and high-performance streaming.
    """

    def __init__(self, serial_number: Optional[str] = None):
        """
        Initialize SDRplay device

        Args:
            serial_number: Optional serial number to select specific device.
                          If None, uses first available device.
        """
        self.lib = None
        self.device = None
        self.device_params = None
        self.streaming = False
        self.data_callback = None
        self.stream_thread = None
        self.sample_buffer = []
        self.buffer_lock = threading.Lock()

        # Load library
        try:
            self.lib = ctypes.CDLL(LIB_PATH)
            print(f"✓ Loaded SDRplay API library: {LIB_PATH}")
        except OSError as e:
            raise RuntimeError(f"Failed to load SDRplay API library from {LIB_PATH}. "
                             f"Make sure SDRplay API 3.x is installed. Error: {e}")

        # Setup function signatures
        self._setup_api()

        # Open API
        err = self.lib.sdrplay_api_Open()
        if err != sdrplay_api_ErrT.Success:
            raise RuntimeError(f"Failed to open SDRplay API: error {err}")
        print("✓ SDRplay API opened")

        # Get API version
        ver = c_float()
        err = self.lib.sdrplay_api_ApiVersion(byref(ver))
        if err == sdrplay_api_ErrT.Success:
            print(f"✓ SDRplay API version: {ver.value}")

        # Lock API for device selection
        err = self.lib.sdrplay_api_LockDeviceApi()
        if err != sdrplay_api_ErrT.Success:
            raise RuntimeError(f"Failed to lock API: error {err}")

        # Get device list
        devices = (sdrplay_api_DeviceT * 16)()
        num_devices = c_uint(0)
        err = self.lib.sdrplay_api_GetDevices(devices, byref(num_devices), c_uint(16))

        if err != sdrplay_api_ErrT.Success or num_devices.value == 0:
            self.lib.sdrplay_api_UnlockDeviceApi()
            raise RuntimeError("No SDRplay devices found")

        print(f"✓ Found {num_devices.value} SDRplay device(s)")

        # Select device
        selected = None
        for i in range(num_devices.value):
            dev = devices[i]
            print(f"  Device {i}: (Serial: {dev.SerNo.decode()})")
            if serial_number is None or dev.SerNo.decode() == serial_number:
                selected = dev
                break

        if selected is None:
            self.lib.sdrplay_api_UnlockDeviceApi()
            raise RuntimeError(f"Device with serial {serial_number} not found")

        self.device = selected
        print(f"✓ Selected device: {self.device.SerNo.decode()}")

        # Select device
        err = self.lib.sdrplay_api_SelectDevice(byref(self.device))
        if err != sdrplay_api_ErrT.Success:
            self.lib.sdrplay_api_UnlockDeviceApi()
            raise RuntimeError(f"Failed to select device: error {err}")

        # Device handle is now populated in device.dev after SelectDevice

        # Unlock API
        err = self.lib.sdrplay_api_UnlockDeviceApi()
        if err != sdrplay_api_ErrT.Success:
            print(f"⚠️  Warning: Failed to unlock API: error {err}")

        # Get device parameters using the device handle
        device_params_ptr = c_void_p()
        err = self.lib.sdrplay_api_GetDeviceParams(
            self.device.dev,
            byref(device_params_ptr)
        )

        if err != sdrplay_api_ErrT.Success:
            raise RuntimeError(f"Failed to get device parameters: error {err}")

        self.device_params = cast(device_params_ptr, POINTER(sdrplay_api_DeviceParamsT))
        print("✓ Got device parameters")

        # Enable debug logging for troubleshooting
        if hasattr(self.lib, 'sdrplay_api_DebugEnable'):
            self.lib.sdrplay_api_DebugEnable.argtypes = [c_void_p, c_int]
            self.lib.sdrplay_api_DebugEnable.restype = c_int
            # Enable verbose debug output
            err = self.lib.sdrplay_api_DebugEnable(self.device.dev, 1)  # 1 = Verbose
            if err == sdrplay_api_ErrT.Success:
                print("✓ Debug logging enabled")

        # Setup default configuration
        self._configure_defaults()

    def _setup_api(self):
        """Setup ctypes function signatures for SDRplay API"""
        # sdrplay_api_Open
        self.lib.sdrplay_api_Open.argtypes = []
        self.lib.sdrplay_api_Open.restype = c_int

        # sdrplay_api_Close
        self.lib.sdrplay_api_Close.argtypes = []
        self.lib.sdrplay_api_Close.restype = c_int

        # sdrplay_api_ApiVersion
        self.lib.sdrplay_api_ApiVersion.argtypes = [POINTER(c_float)]
        self.lib.sdrplay_api_ApiVersion.restype = c_int

        # sdrplay_api_LockDeviceApi
        self.lib.sdrplay_api_LockDeviceApi.argtypes = []
        self.lib.sdrplay_api_LockDeviceApi.restype = c_int

        # sdrplay_api_UnlockDeviceApi
        self.lib.sdrplay_api_UnlockDeviceApi.argtypes = []
        self.lib.sdrplay_api_UnlockDeviceApi.restype = c_int

        # sdrplay_api_GetDevices
        self.lib.sdrplay_api_GetDevices.argtypes = [
            POINTER(sdrplay_api_DeviceT),
            POINTER(c_uint),
            c_uint
        ]
        self.lib.sdrplay_api_GetDevices.restype = c_int

        # sdrplay_api_SelectDevice
        self.lib.sdrplay_api_SelectDevice.argtypes = [POINTER(sdrplay_api_DeviceT)]
        self.lib.sdrplay_api_SelectDevice.restype = c_int

        # sdrplay_api_ReleaseDevice
        self.lib.sdrplay_api_ReleaseDevice.argtypes = [POINTER(sdrplay_api_DeviceT)]
        self.lib.sdrplay_api_ReleaseDevice.restype = c_int

        # sdrplay_api_GetDeviceParams
        self.lib.sdrplay_api_GetDeviceParams.argtypes = [c_void_p, POINTER(c_void_p)]
        self.lib.sdrplay_api_GetDeviceParams.restype = c_int

        # sdrplay_api_Init
        self.lib.sdrplay_api_Init.argtypes = [
            c_void_p,  # HANDLE dev
            POINTER(sdrplay_api_CallbackFnsT),  # Pointer to callback functions structure
            c_void_p   # cbContext
        ]
        self.lib.sdrplay_api_Init.restype = c_int

        # sdrplay_api_Uninit
        self.lib.sdrplay_api_Uninit.argtypes = [c_void_p]  # HANDLE dev
        self.lib.sdrplay_api_Uninit.restype = c_int

        # sdrplay_api_Update - CRITICAL for event acknowledgment
        self.lib.sdrplay_api_Update.argtypes = [
            c_void_p,  # HANDLE dev
            c_uint,    # sdrplay_api_TunerSelectT tuner
            c_uint,    # sdrplay_api_ReasonForUpdateT reasonForUpdate
            c_uint     # sdrplay_api_ReasonForUpdateExtension1T reasonForUpdateExt1
        ]
        self.lib.sdrplay_api_Update.restype = c_int

        # sdrplay_api_GetLastError (for detailed error info)
        if hasattr(self.lib, 'sdrplay_api_GetLastError'):
            self.lib.sdrplay_api_GetLastError.argtypes = [c_void_p]
            self.lib.sdrplay_api_GetLastError.restype = c_void_p  # Returns ErrorInfoT pointer

    def _configure_defaults(self):
        """Configure default parameters for GPS L1 reception"""
        if not self.device_params:
            return

        # Check if devParams is not NULL (following C example)
        if self.device_params.contents.devParams:
            # Get device parameters - this will be NULL for slave devices
            dev_params = self.device_params.contents.devParams.contents

            # Set sample rate (REQUIRED before Init)
            dev_params.fsFreq.fsHz = 2048000.0  # 2.048 MHz for GPS
            dev_params.fsFreq.syncUpdate = 0
            dev_params.fsFreq.reCal = 0

            # Set transfer mode
            dev_params.mode = sdrplay_api_TransferModeT.ISOCH

            # Set PPM correction (if needed)
            dev_params.ppm = 0.0
        else:
            print("⚠️  devParams is NULL (might be slave device)")

        # Get RX channel A parameters
        if not self.device_params.contents.rxChannelA:
            print("⚠️  rxChannelA is NULL")
            return

        rx_params = self.device_params.contents.rxChannelA.contents

        # Set RF frequency for GPS L1
        rx_params.tunerParams.rfFreq.rfHz = 1575420000.0  # GPS L1 frequency
        rx_params.tunerParams.rfFreq.syncUpdate = 0

        # Set bandwidth and IF mode (matching C example)
        rx_params.tunerParams.bwType = sdrplay_api_Bw_MHzT.BW_1_536
        rx_params.tunerParams.ifType = sdrplay_api_If_kHzT.IF_Zero  # Zero-IF like C example
        rx_params.tunerParams.loMode = sdrplay_api_LoModeT.Auto

        # Set gain parameters - High gain for GPS reception (balanced for sensitivity and stability)
        rx_params.tunerParams.gain.gRdB = 30  # 30 dB gain reduction (29 dB actual gain, balanced)
        rx_params.tunerParams.gain.LNAstate = 4  # Higher LNA state for better sensitivity
        rx_params.tunerParams.gain.syncUpdate = 0
        rx_params.tunerParams.gain.minGr = sdrplay_api_MinGainReductionT.NORMAL_MIN_GR

        # Bias-T configuration - MUST be enabled for active GPS antenna
        # Active antennas have built-in LNA that requires power
        bias_t_enable = 1  # 0=disabled, 1=enabled

        rx_params.rsp1aTunerParams.biasTEnable = bias_t_enable  # RSP1A

        # RSP2: Configure Bias-T AND select Antenna B (Port 2)
        # Antenna A=5 (Port 1: 10kHz-2GHz), Antenna B=6 (Port 2: 60MHz-2GHz)
        # Based on SDRplay API: sdrplay_api_Rsp2_ANTENNA_A = 5, sdrplay_api_Rsp2_ANTENNA_B = 6
        rx_params.rsp2TunerParams.biasTEnable = bias_t_enable   # RSP2 Bias-T
        rx_params.rsp2TunerParams.antennaSel = 6    # RSP2 Antenna B (Port 2)

        rx_params.rspDuoTunerParams.biasTEnable = bias_t_enable  # RSPduo

        if bias_t_enable:
            print("✓ Bias-T ENABLED for active antenna power (all device types)")
        else:
            print("✓ Bias-T DISABLED to reduce power consumption")
        print("✓ RSP2: Antenna B (Port 2) selected")

        # Configure DC offset
        rx_params.tunerParams.dcOffsetTuner.dcCal = 3  # Periodic mode
        rx_params.tunerParams.dcOffsetTuner.speedUp = 0
        rx_params.tunerParams.dcOffsetTuner.trackTime = 1
        rx_params.tunerParams.dcOffsetTuner.refreshRateTime = 2048

        # Configure control parameters
        rx_params.ctrlParams.dcOffset.DCenable = 1
        rx_params.ctrlParams.dcOffset.IQenable = 1

        # Disable decimation (we're already at 2.048 MSPS)
        rx_params.ctrlParams.decimation.enable = 0
        rx_params.ctrlParams.decimation.decimationFactor = 1
        rx_params.ctrlParams.decimation.wideBandSignal = 0

        # Configure AGC (disabled for manual gain control)
        rx_params.ctrlParams.agc.enable = sdrplay_api_AgcControlT.DISABLE
        rx_params.ctrlParams.agc.setPoint_dBfs = -60
        rx_params.ctrlParams.agc.syncUpdate = 0

        # Set ADS-B mode
        rx_params.ctrlParams.adsbMode = sdrplay_api_AdsbModeT.DECIMATION

        print("✓ Configured default parameters (GPS L1, 2.048 MSPS)")

        # Debug: Print current configuration
        if self.device_params.contents.devParams:
            dev_params = self.device_params.contents.devParams.contents
            print(f"DEBUG: Sample rate: {dev_params.fsFreq.fsHz} Hz")
            print(f"DEBUG: Transfer mode: {dev_params.mode}")
        print(f"DEBUG: RF frequency: {rx_params.tunerParams.rfFreq.rfHz} Hz")
        print(f"DEBUG: Bandwidth: {rx_params.tunerParams.bwType}")
        print(f"DEBUG: IF type: {rx_params.tunerParams.ifType}")
        print(f"DEBUG: Gain reduction: {rx_params.tunerParams.gain.gRdB} dB")

    def set_frequency(self, freq_hz: float):
        """Set center frequency in Hz"""
        if not self.device_params:
            raise RuntimeError("Device not initialized")

        rx_params = self.device_params.contents.rxChannelA.contents
        rx_params.tunerParams.rfFreq.rfHz = freq_hz
        rx_params.tunerParams.rfFreq.syncUpdate = 0

        print(f"✓ Set frequency: {freq_hz / 1e6:.3f} MHz")

    def set_sample_rate(self, rate_hz: float):
        """
        Set sample rate in Hz

        Note: SDRplay has fixed native rates, so this may not match exactly.
        Common rates: 2.0MHz, 2.048MHz, 6MHz, 8MHz, 10MHz
        """
        if not self.device_params:
            raise RuntimeError("Device not initialized")

        if not self.device_params.contents.devParams:
            print("⚠️  Cannot set sample rate - devParams is NULL (slave device?)")
            return

        dev_params = self.device_params.contents.devParams.contents
        dev_params.fsFreq.fsHz = rate_hz
        dev_params.fsFreq.syncUpdate = 0

        print(f"✓ Set sample rate: {rate_hz / 1e6:.3f} MSPS")

    def set_gain(self, gain_db: float):
        """
        Set gain in dB

        Args:
            gain_db: Gain in dB (0-60 typical range)
        """
        if not self.device_params:
            raise RuntimeError("Device not initialized")

        # SDRplay uses gain reduction, so we invert
        # Max gain is ~60dB, so 40dB gain = 20dB reduction
        gain_reduction = int(max(0, min(59, 59 - gain_db)))

        rx_params = self.device_params.contents.rxChannelA.contents
        rx_params.tunerParams.gain.gRdB = gain_reduction
        rx_params.tunerParams.gain.syncUpdate = 0

        print(f"✓ Set gain: {gain_db} dB (reduction: {gain_reduction} dB)")

    def set_bias_tee(self, enable: bool):
        """
        Enable/disable bias-T for active antenna power

        Note: This requires device-specific API calls that vary by model.
        RSP2/RSPduo have bias-T on specific ports.
        """
        print(f"⚠️  Bias-T control requires device-specific implementation")
        print(f"   Requested: {'ON' if enable else 'OFF'}")
        print(f"   Use SoapySDR for bias-T control for now")

    def start_streaming(self, callback: Callable[[np.ndarray], None]):
        """
        Start streaming IQ data

        Args:
            callback: Function that will be called with numpy array of complex64 samples
        """
        if self.streaming:
            print("⚠️  Already streaming")
            return

        self.data_callback = callback

        # Create callback wrapper
        @sdrplay_api_StreamCallback_t
        def stream_callback(xi, xq, params, num_samples, reset, ctx):
            """Internal callback that receives samples from SDRplay"""
            if num_samples == 0:
                return

            # Convert to numpy arrays
            i_samples = np.ctypeslib.as_array(xi, shape=(num_samples,))
            q_samples = np.ctypeslib.as_array(xq, shape=(num_samples,))

            # Convert to complex64 (normalize from int16 to float)
            complex_samples = (i_samples.astype(np.float32) +
                              1j * q_samples.astype(np.float32)) / 32768.0

            # Call user callback
            if self.data_callback:
                try:
                    self.data_callback(complex_samples)
                except Exception as e:
                    print(f"Error in data callback: {e}")

        # Create event callback - CRITICAL for handling PowerOverload events
        @sdrplay_api_EventCallback_t
        def event_callback(event_id, tuner, params, ctx):
            """
            Internal callback for device events
            Following SDRplay_API_Specification_v3_15_API_USAGE.c example
            """
            try:
                # Convert event_id to enum for readability
                event_type = sdrplay_api_EventT(event_id)
                tuner_name = "Tuner_A" if tuner == sdrplay_api_TunerSelectT.Tuner_A else "Tuner_B"

                if event_type == sdrplay_api_EventT.GainChange:
                    # Gain change event
                    if params:
                        gain_params = params.contents.gainParams
                        print(f"[Event] GainChange: {tuner_name}, gRdB={gain_params.gRdB}, "
                              f"lnaGRdB={gain_params.lnaGRdB}, currGain={gain_params.currGain:.2f}")

                elif event_type == sdrplay_api_EventT.PowerOverloadChange:
                    # CRITICAL: Power overload event - MUST acknowledge!
                    if params:
                        overload_type = params.contents.powerOverloadParams.powerOverloadChangeType
                        overload_str = ("Detected" if overload_type == sdrplay_api_PowerOverloadCbEventIdT.Overload_Detected
                                       else "Corrected")
                        print(f"[Event] PowerOverload: {tuner_name}, {overload_str}")

                        # CRITICAL: Acknowledge power overload message (from C example line 41-42)
                        # If we don't acknowledge, the stream may stop!
                        err = self.lib.sdrplay_api_Update(
                            self.device.dev,
                            tuner,
                            sdrplay_api_ReasonForUpdateT.Update_Ctrl_OverloadMsgAck,
                            sdrplay_api_ReasonForUpdateExtension1T.Update_Ext1_None
                        )
                        if err != sdrplay_api_ErrT.Success:
                            print(f"[Event] WARNING: Failed to acknowledge PowerOverload: error {err}")
                        else:
                            print(f"[Event] PowerOverload acknowledged successfully")

                elif event_type == sdrplay_api_EventT.DeviceRemoved:
                    print(f"[Event] DeviceRemoved: {tuner_name}")

                elif event_type == sdrplay_api_EventT.RspDuoModeChange:
                    print(f"[Event] RspDuoModeChange: {tuner_name}")

                else:
                    print(f"[Event] Unknown event: {event_id}, {tuner_name}")

            except Exception as e:
                # Don't let exceptions in callback crash the stream
                print(f"[Event] Error in event callback: {e}")
                import traceback
                traceback.print_exc()

        # Store callbacks to prevent garbage collection
        self._stream_callback = stream_callback
        self._event_callback = event_callback

        # Create callback functions structure
        callback_fns = sdrplay_api_CallbackFnsT()
        callback_fns.StreamACbFn = stream_callback
        callback_fns.StreamBCbFn = cast(None, sdrplay_api_StreamCallback_t)  # NULL for single tuner
        callback_fns.EventCbFn = event_callback

        # Initialize device and start streaming
        print(f"DEBUG: Calling sdrplay_api_Init with dev handle: {self.device.dev}")
        err = self.lib.sdrplay_api_Init(
            self.device.dev,
            byref(callback_fns),
            None
        )

        if err != sdrplay_api_ErrT.Success:
            # Try to get more error details
            error_name = sdrplay_api_ErrT(err).name if err in [e.value for e in sdrplay_api_ErrT] else 'Unknown'

            # Try to get error string from API if available
            error_details = "No additional details available"
            if hasattr(self.lib, 'sdrplay_api_GetErrorString'):
                self.lib.sdrplay_api_GetErrorString.argtypes = [c_int]
                self.lib.sdrplay_api_GetErrorString.restype = c_char_p
                error_str = self.lib.sdrplay_api_GetErrorString(err)
                if error_str:
                    error_details = error_str.decode('utf-8')

            # Try to get extended error info (like in C example)
            if hasattr(self.lib, 'sdrplay_api_GetLastError'):
                error_info_ptr = self.lib.sdrplay_api_GetLastError(None)  # NULL to get last error
                if error_info_ptr:
                    error_info = cast(error_info_ptr, POINTER(sdrplay_api_ErrorInfoT)).contents
                    extended_msg = f"Error in {error_info.file.decode()}: {error_info.function.decode()}(): line {error_info.line}: {error_info.message.decode()}"
                    print(f"DEBUG: Extended error: {extended_msg}")
                    error_details = extended_msg

            error_msg = f"Failed to initialize streaming: error {err} ({error_name}). Details: {error_details}"
            print(f"DEBUG: Init failed. Device params configured: {self.device_params is not None}")
            raise RuntimeError(error_msg)

        self.streaming = True
        print("✓ Streaming started")

    def stop_streaming(self):
        """Stop streaming"""
        if not self.streaming:
            return

        err = self.lib.sdrplay_api_Uninit(self.device.dev)
        if err != sdrplay_api_ErrT.Success:
            print(f"⚠️  Warning: Failed to uninit: error {err}")

        self.streaming = False
        self.data_callback = None
        print("✓ Streaming stopped")

    def close(self):
        """Close device and cleanup"""
        if self.streaming:
            self.stop_streaming()

        if self.device:
            err = self.lib.sdrplay_api_ReleaseDevice(byref(self.device))
            if err != sdrplay_api_ErrT.Success:
                print(f"⚠️  Warning: Failed to release device: error {err}")

        if self.lib:
            err = self.lib.sdrplay_api_Close()
            if err != sdrplay_api_ErrT.Success:
                print(f"⚠️  Warning: Failed to close API: error {err}")

        print("✓ SDRplay device closed")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


def main():
    """Test/demo of SDRplay direct API with optional file recording"""
    import argparse
    import signal

    parser = argparse.ArgumentParser(description='SDRplay Direct API - GPS Signal Recording')
    parser.add_argument('--output', type=str, help='Output file path for IQ samples (.dat)')
    parser.add_argument('--duration', type=int, default=10, help='Recording duration in seconds (default: 10)')
    parser.add_argument('--frequency', type=float, default=1575.42e6, help='Center frequency in Hz (default: 1575.42 MHz)')
    parser.add_argument('--sample-rate', type=float, default=2.048e6, help='Sample rate in Hz (default: 2.048 MSPS)')
    parser.add_argument('--gain-reduction', type=int, default=30, help='Gain reduction in dB (default: 30, lower = more gain)')
    parser.add_argument('--tuner', type=int, default=1, choices=[1, 2], help='RSPduo tuner selection: 1 (Tuner A/Port 1) or 2 (Tuner B/Port 2) - default: 1')
    args = parser.parse_args()

    print("=" * 70)
    if args.output:
        print("SDRplay GPS Recording")
        print(f"Output: {args.output}")
    else:
        print("SDRplay Direct API Test")
    print("=" * 70)
    print()

    sample_count = [0]
    start_time = [time.time()]
    output_file = None
    stop_requested = [False]

    # Signal handler for graceful shutdown
    def signal_handler(sig, frame):
        print("\n\n🛑 Stopping recording...")
        stop_requested[0] = True

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Open output file if specified
    if args.output:
        try:
            output_file = open(args.output, 'wb')
            print(f"✓ Opened output file: {args.output}")
        except Exception as e:
            print(f"❌ Failed to open output file: {e}")
            return

    def data_callback(samples):
        """Callback that receives IQ samples"""
        sample_count[0] += len(samples)

        # Write to file if recording
        if output_file:
            try:
                # Write as complex64 (gr_complex format for GNSS-SDR)
                samples.astype(np.complex64).tofile(output_file)
            except Exception as e:
                print(f"❌ Error writing to file: {e}")
                stop_requested[0] = True

        # Print stats every second
        now = time.time()
        elapsed = now - start_time[0]
        if elapsed >= 1.0:
            rate = sample_count[0] / elapsed / 1e6
            total_samples = sample_count[0]
            total_mb = (total_samples * 8) / (1024 * 1024)  # complex64 = 8 bytes

            if args.output:
                print(f"Recording: {sample_count[0] / 1e6:.1f} MSamples, {total_mb:.1f} MB, {rate:.2f} MSPS", flush=True)
            else:
                print(f"Received {sample_count[0] / 1e6:.1f} MSamples ({rate:.2f} MSPS)")

            sample_count[0] = 0
            start_time[0] = now

    try:
        # Open device
        with SDRplayDevice() as sdr:
            # Configure
            print(f"Configuring:")
            print(f"  • Frequency: {args.frequency / 1e6:.2f} MHz")
            print(f"  • Sample Rate: {args.sample_rate / 1e6:.3f} MSPS")
            print(f"  • Gain Reduction: {args.gain_reduction} dB")
            print()

            sdr.set_frequency(args.frequency)
            sdr.set_sample_rate(args.sample_rate)
            sdr.set_gain(args.gain_reduction)

            # Start streaming
            sdr.start_streaming(data_callback)

            if args.output:
                print(f"\n📡 Recording GPS data for {args.duration} seconds...")
                print(f"Expected file size: ~{(args.sample_rate * args.duration * 8) / (1024 * 1024):.0f} MB")
                print("Press Ctrl+C to stop early\n")
            else:
                print(f"\nStreaming for {args.duration} seconds...")

            # Stream for specified duration or until interrupted
            start = time.time()
            while time.time() - start < args.duration and not stop_requested[0]:
                time.sleep(0.1)

            print("\n🛑 Stopping...")

    except KeyboardInterrupt:
        print("\n\n👋 Interrupted by user")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Close output file
        if output_file:
            output_file.close()
            import os
            size = os.path.getsize(args.output)
            print(f"✓ Recording saved: {args.output}")
            print(f"  File size: {size / (1024 * 1024):.1f} MB")
            print(f"  Duration: ~{size / (args.sample_rate * 8):.1f} seconds")


if __name__ == '__main__':
    main()
