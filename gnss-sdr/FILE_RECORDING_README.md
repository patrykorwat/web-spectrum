# GPS File-Based Recording & Position Fix

This directory contains a complete solution for recording GPS data from SDRplay and processing it with GNSS-SDR to get position fixes.

## Why File-Based?

The file-based approach solves the FIFO blocking issue that occurs with real-time GNSS-SDR processing. By recording IQ samples to a file first, then processing offline, we:
- Avoid the FIFO deadlock after 30-80 seconds
- Allow multiple processing attempts on the same data
- Enable post-processing with different GNSS-SDR settings
- Get reliable position fixes without streaming issues

## Components

### 1. Recording API Server (`recording_api_simple.py`)
Python HTTP server that provides REST API endpoints for the UI to control recording and processing.

**Endpoints:**
- `POST /gnss/start-recording` - Start GPS data recording
- `POST /gnss/stop-recording` - Stop current recording
- `POST /gnss/process-recording` - Process recorded file with GNSS-SDR
- `GET /gnss/status` - Get current status
- `GET /gnss/recordings` - List all recordings

### 2. SDRplay Direct API (`sdrplay_direct.py`)
Direct interface to SDRplay API with command-line recording support.

**Command-line usage:**
```bash
python3 sdrplay_direct.py \
  --output recordings/test.dat \
  --duration 300 \
  --frequency 1575420000 \
  --sample-rate 2048000 \
  --gain-reduction 30
```

### 3. UI Controls (`src/pages/SdrPlayDecoder.tsx`)
React UI with buttons to:
- Start 5-minute GPS recording
- Stop recording early
- Process recorded file to get position fix

## Quick Start

### Option 1: Use the UI (Recommended)

1. **Start the API server:**
   ```bash
   cd gnss-sdr
   ./start_recording_api.sh
   ```

2. **Start the React UI:**
   ```bash
   cd ..
   npm start
   ```

3. **In the UI:**
   - Select "GNSS-SDR Direct" bridge mode
   - Click "⏺ Start Recording (5 min)"
   - Wait for recording to complete (or stop early)
   - Click "🔄 Process & Get Position"
   - Check `recordings/` directory for NMEA/KML/GPX output

### Option 2: Command Line

1. **Record GPS data (5 minutes):**
   ```bash
   cd gnss-sdr
   python3 sdrplay_direct.py \
     --output recordings/gps_$(date +%Y%m%d_%H%M%S).dat \
     --duration 300 \
     --frequency 1575420000 \
     --sample-rate 2048000 \
     --gain-reduction 30
   ```

2. **Process with GNSS-SDR:**
   ```bash
   # Create config file (see example below)
   gnss-sdr --config_file=recordings/your_file.conf
   ```

## File Sizes

GPS L1 C/A at 2.048 MSPS, complex64 format:
- **1 minute:** ~980 MB
- **5 minutes:** ~4.9 GB
- **10 minutes:** ~9.8 GB

## GNSS-SDR Configuration

The API server automatically generates configs, but you can create custom ones:

```ini
[GNSS-SDR]
GNSS-SDR.internal_fs_sps=2048000

; Input file
SignalSource.implementation=File_Signal_Source
SignalSource.filename=/path/to/recording.dat
SignalSource.item_type=gr_complex
SignalSource.sampling_frequency=2048000
SignalSource.samples=0
SignalSource.repeat=false
SignalSource.enable_throttle_control=true

; Signal conditioning
SignalConditioner.implementation=Pass_Through

; GPS L1 channels
Channels_1C.count=12
Channel.signal=1C

; Acquisition - sensitive settings for weak signals
Acquisition_1C.implementation=GPS_L1_CA_PCPS_Acquisition
Acquisition_1C.pfa=0.0001
Acquisition_1C.doppler_max=10000
Acquisition_1C.doppler_step=500
Acquisition_1C.threshold=0.002

; Tracking
Tracking_1C.implementation=GPS_L1_CA_DLL_PLL_Tracking
Tracking_1C.pll_bw_hz=50.0
Tracking_1C.dll_bw_hz=4.0

; Output
PVT.implementation=RTKLIB_PVT
PVT.positioning_mode=Single
PVT.nmea_dump_filename=/path/to/output.nmea
PVT.kml_output_enabled=true
PVT.gpx_output_enabled=true
```

## Output Files

After processing, you'll get:
- `*.nmea` - NMEA sentences with position/time data
- `*.kml` - Google Earth track
- `*.gpx` - GPS Exchange format
- `*_pvt.dat` - Raw PVT (Position/Velocity/Time) data

## Troubleshooting

### No position fix after processing
- **Cause:** Weak signal, indoor location, or insufficient satellites
- **Solution:**
  - Record for longer (10+ minutes)
  - Move antenna outdoors with clear sky view
  - Check antenna connection and L1 band filter
  - Increase gain (lower `--gain-reduction` value)

### Recording stops early
- **Cause:** Disk space, SDRplay driver issue
- **Solution:**
  - Check disk space (need ~1GB per minute)
  - Verify SDRplay API: `DYLD_LIBRARY_PATH=/usr/local/lib SoapySDRUtil --find`
  - Check for USB errors in system logs

### API server won't start
- **Cause:** Port 3001 already in use
- **Solution:**
  - `lsof -i :3001` to find process
  - Kill existing process or change port in `recording_api_simple.py`

### Processing takes too long
- **Cause:** Large file, weak signals
- **Solution:**
  - GNSS-SDR processes slower than real-time for file sources
  - 5-minute file may take 10-15 minutes to process
  - Use `enable_throttle_control=true` for faster processing

## SDRplay Settings

Current optimal settings for GPS L1:
- **Frequency:** 1575.42 MHz (GPS L1 C/A)
- **Sample Rate:** 2.048 MSPS
- **Gain Reduction:** 30 dB (29 dB actual gain)
- **Bandwidth:** 2 MHz
- **LNA State:** 4 (high sensitivity)

## Architecture

```
UI (React)
   ↓ HTTP POST
Recording API Server (Python)
   ↓ subprocess
SDRplay Direct API
   ↓ IQ samples
Recording File (.dat)
   ↓ config file
GNSS-SDR Processor
   ↓ parse_gnss_logs.py
WebSocket → UI
   ↓ final outputs
NMEA/KML/GPX files
```

## Next Steps

1. Test recording with 1-minute duration first
2. Verify file is created in `recordings/` directory
3. Process file and check for satellite acquisition
4. If successful, try 5-minute recording for position fix
5. Adjust gain if needed based on C/N0 values

## Resources

- SDRplay API: https://www.sdrplay.com/api/
- GNSS-SDR: https://gnss-sdr.org/
- GPS L1 C/A signals: 1575.42 MHz
- Expected C/N0: 35-50 dB-Hz (outdoor with good antenna)
