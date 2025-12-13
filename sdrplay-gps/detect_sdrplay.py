#!/usr/bin/env python3
"""
Detect SDRplay devices and return info as JSON
"""

import sys
import json

# Try to import sdrplay_direct module
try:
    from sdrplay_direct import SDRplayDevice, sdrplay_api_DeviceT, c_uint, byref, POINTER
except ImportError:
    print(json.dumps({'error': 'sdrplay_direct module not available'}))
    sys.exit(1)

def detect_devices():
    """Detect connected SDRplay devices"""
    try:
        # Import library loading code
        import ctypes
        import platform
        from ctypes import cdll, c_int, c_uint, c_char, c_ubyte, c_double, c_void_p, byref, POINTER, Structure

        # Load SDRplay API library
        if platform.system() == 'Darwin':  # macOS
            lib_path = '/usr/local/lib/libsdrplay_api.dylib'
        elif platform.system() == 'Linux':
            lib_path = 'libsdrplay_api.so'
        else:
            return {'error': 'Unsupported platform', 'devices': []}

        lib = cdll.LoadLibrary(lib_path)

        # Setup function signatures
        lib.sdrplay_api_Open.argtypes = []
        lib.sdrplay_api_Open.restype = c_int
        lib.sdrplay_api_Close.argtypes = []
        lib.sdrplay_api_Close.restype = c_int
        lib.sdrplay_api_LockDeviceApi.argtypes = []
        lib.sdrplay_api_LockDeviceApi.restype = c_int
        lib.sdrplay_api_UnlockDeviceApi.argtypes = []
        lib.sdrplay_api_UnlockDeviceApi.restype = c_int
        lib.sdrplay_api_GetDevices.argtypes = [POINTER(sdrplay_api_DeviceT), POINTER(c_uint), c_uint]
        lib.sdrplay_api_GetDevices.restype = c_int

        # Open API
        err = lib.sdrplay_api_Open()
        if err != 0:
            return {'error': f'Failed to open SDRplay API: error {err}', 'devices': []}

        # Lock API for device enumeration
        err = lib.sdrplay_api_LockDeviceApi()
        if err != 0:
            lib.sdrplay_api_Close()
            return {'error': f'Failed to lock API: error {err}', 'devices': []}

        # Get device list
        devices = (sdrplay_api_DeviceT * 16)()  # Max 16 devices
        num_devices = c_uint(0)

        err = lib.sdrplay_api_GetDevices(devices, byref(num_devices), 16)

        # Unlock API
        lib.sdrplay_api_UnlockDeviceApi()
        lib.sdrplay_api_Close()

        if err != 0:
            return {'error': f'Failed to get devices: error {err}', 'devices': []}

        # Build device list
        device_list = []
        for i in range(num_devices.value):
            dev = devices[i]

            # Map hardware version to model name
            hw_ver = dev.hwVer
            model_map = {
                1: 'RSP1',
                2: 'RSP1A',
                3: 'RSP2',
                4: 'RSPduo',
                5: 'RSPdx'
            }
            model = model_map.get(hw_ver, f'Unknown (hw={hw_ver})')

            # Map tuner selection
            tuner_map = {
                0: 'Neither',
                1: 'Tuner 1 (A)',
                2: 'Tuner 2 (B)',
                3: 'Both'
            }
            tuner = tuner_map.get(dev.tuner, f'Unknown ({dev.tuner})')

            # Map RSPduo mode
            mode_map = {
                0: 'Unknown',
                1: 'Single Tuner',
                2: 'Dual Tuner',
                4: 'Master',
                8: 'Slave'
            }
            rsp_duo_mode = mode_map.get(dev.rspDuoMode, f'Mode {dev.rspDuoMode}')

            device_info = {
                'index': i,
                'serial': dev.SerNo.decode('utf-8'),
                'model': model,
                'hw_version': hw_ver,
                'tuner': tuner,
                'tuner_id': dev.tuner,
                'valid': bool(dev.valid),
                'is_rspduo': hw_ver == 4
            }

            # Add RSPduo-specific info
            if hw_ver == 4:
                device_info['rspduo_mode'] = rsp_duo_mode
                device_info['rspduo_sample_freq'] = dev.rspDuoSampleFreq

            device_list.append(device_info)

        return {
            'success': True,
            'count': num_devices.value,
            'devices': device_list
        }

    except Exception as e:
        return {
            'error': str(e),
            'devices': []
        }

if __name__ == '__main__':
    result = detect_devices()
    print(json.dumps(result, indent=2))
