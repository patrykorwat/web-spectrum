# GPS Recording API - Multi-Device Support

The recording API now supports **both SDRplay and RTL-SDR** devices with explicit device selection.

## API Changes

### 1. Device Detection - `/gnss/device-info` (GET)

Returns information about **all** available devices:

**Response:**
```json
{
  "success": true,
  "sdrplay": {
    "success": true,
    "count": 1,
    "devices": [...],
    "type": "SDRplay"
  },
  "rtlsdr": {
    "success": true,
    "count": 1,
    "devices": [...],
    "type": "RTL-SDR"
  }
}
```

- `sdrplay`: SDRplay device info (null if not found)
- `rtlsdr`: RTL-SDR device info (null if not found)

### 2. Start Recording - `/gnss/start-recording` (POST)

Now accepts a `device_type` parameter to explicitly select which device to use.

**Request Body:**
```json
{
  "duration": 300,
  "device_type": "rtlsdr",  // NEW: "sdrplay" or "rtlsdr"
  "tuner": 1
}
```

**Parameters:**
- `device_type` (string, optional): Device to use for recording
  - `"sdrplay"`: Use SDRplay device (via sdrplay_direct.py)
  - `"rtlsdr"`: Use RTL-SDR device (via rtlsdr_direct.py)
  - Default: `"sdrplay"` (for backward compatibility)
- `duration` (int, optional): Recording duration in seconds (default: 300)
- `tuner` (int, optional): Tuner selection (1 or 2 for RSPduo, ignored for RTL-SDR)

**Response:**
```json
{
  "success": true,
  "filename": "gps_recording_20251221_172729.dat",
  "filepath": "/path/to/recordings/gps_recording_20251221_172729.dat",
  "duration": 300,
  "device_type": "rtlsdr",
  "started_at": "20251221_172729"
}
```

## Frontend Integration

### For Separate UIs

If you have separate UI pages for RTL-SDR and SDRplay:

**RTL-SDR UI:**
```javascript
// Always send device_type: "rtlsdr"
fetch('/gnss/start-recording', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    duration: 300,
    device_type: 'rtlsdr'  // Explicitly use RTL-SDR
  })
})
```

**SDRplay UI:**
```javascript
// Always send device_type: "sdrplay"
fetch('/gnss/start-recording', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    duration: 300,
    device_type: 'sdrplay',  // Explicitly use SDRplay
    tuner: 2  // RSPduo tuner selection
  })
})
```

### Checking Available Devices

```javascript
// Fetch device info
const response = await fetch('/gnss/device-info');
const devices = await response.json();

// Check which devices are available
const hasSDRplay = devices.sdrplay !== null;
const hasRTLSDR = devices.rtlsdr !== null;

if (hasRTLSDR) {
  console.log('RTL-SDR found:', devices.rtlsdr.devices[0].name);
}

if (hasSDRplay) {
  console.log('SDRplay found:', devices.sdrplay.devices[0]);
}
```

## Backend Implementation

The backend automatically routes to the correct recording script:

- **RTL-SDR**: Uses `rtlsdr_direct.py`
  - Records with `rtl_sdr` command-line tool
  - Converts uint8 IQ to complex64 (gr_complex) format
  - Compatible with GNSS-SDR processing

- **SDRplay**: Uses `sdrplay_direct.py`
  - Uses SDRplay API directly via Python ctypes
  - Native complex64 output
  - Supports bias-T, tuner selection, etc.

## File Format

Both recording scripts output the same format:
- **Format**: complex64 (gr_complex)
- **Byte order**: Native (little-endian on x86/ARM)
- **Interleaving**: Complex samples (I+jQ)
- **Compatible with**: GNSS-SDR, GNU Radio, SigMF

## Example: Test RTL-SDR Recording

```bash
# Test via API
curl -X POST http://localhost:3001/gnss/start-recording \
  -H "Content-Type: application/json" \
  -d '{"duration": 10, "device_type": "rtlsdr"}'

# Test directly via script
python3 sdrplay-gps/rtlsdr_direct.py \
  --output test.dat \
  --duration 10 \
  --sample-rate 2048000 \
  --frequency 1575420000 \
  --gain 40
```

## Migration Guide

If you had existing UI code that didn't specify `device_type`:

**Before** (auto-detected device):
```javascript
fetch('/gnss/start-recording', {
  method: 'POST',
  body: JSON.stringify({ duration: 300 })
})
// Would auto-detect and use whichever device was found
```

**After** (explicit device selection):
```javascript
fetch('/gnss/start-recording', {
  method: 'POST',
  body: JSON.stringify({
    duration: 300,
    device_type: 'rtlsdr'  // Explicitly specify device
  })
})
// Uses RTL-SDR specifically
```

**Backward compatibility**: If you don't specify `device_type`, it defaults to `"sdrplay"` for backward compatibility with existing SDRplay UIs.

## Troubleshooting

### Empty Recording File (0 bytes)

This usually means:
1. **Wrong device selected**: Check `device_type` matches your hardware
2. **Device in use**: Close other SDR applications (SDRuno, GQRX, etc.)
3. **No device found**: Check device is plugged in and detected (`rtl_test -t` or `SoapySDRUtil --find`)

### Check Device Detection

```bash
# Check RTL-SDR
rtl_test -t

# Check SDRplay (requires SDRplay API service running)
python3 sdrplay-gps/detect_sdrplay.py

# Check via API
curl http://localhost:3001/gnss/device-info
```
