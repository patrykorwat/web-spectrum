# GNSS-SDR Web Interface - Quick Start Guide

## Super Simple: One Command to Rule Them All

```bash
./start_all.sh
```

That's it! This ONE script starts everything:
- ✅ Web UI (port 3005)
- ✅ Control API (port 8767) - enables Start/Stop/Restart buttons
- ✅ GNSS Bridge (port 8766) - relays satellite data to UI

## Usage

1. **Start everything:**
   ```bash
   ./start_all.sh
   ```

2. **Open your browser:**
   - Navigate to: http://localhost:3005

3. **In the UI:**
   - Select **"Professional Mode (GNSS-SDR)"**
   - Click **"Start Collection"** button to begin GPS recording
   - Click **"Listen&Decode"** button to see satellite data streaming in

4. **Control data collection:**
   - **Start Collection** - Begin GPS data recording (15 min samples)
   - **Stop Collection** - Stop data recording
   - **Restart Collection** - Restart the recording process

5. **Stop everything:**
   - Press **Ctrl+C** in the terminal running `start_all.sh`
   - All services shut down cleanly

## What Each Button Does

### Start Collection
- Starts recording GPS L1 signals from SDRPlay
- Records 15 minutes of IQ samples
- Processes with GNSS-SDR professional software
- Repeats continuously for real-time tracking
- First cycle takes ~8-10 minutes (recording + ephemeris decoding)

### Listen&Decode
- Connects to GNSS Bridge (ws://localhost:8766)
- Receives real-time satellite tracking data
- Displays satellites, C/N0, Doppler shift
- Shows jamming detection alerts

### Stop Collection
- Stops GPS recording
- Stops GNSS-SDR processing
- Bridge remains active for future connections

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    start_all.sh                         │
│  (Master script - starts everything in background)      │
└─────────────────────────────────────────────────────────┘
                          │
          ┌───────────────┼───────────────┐
          ▼               ▼               ▼
    ┌─────────┐    ┌──────────┐    ┌──────────┐
    │ Web UI  │    │ Control  │    │  GNSS    │
    │ :3005   │    │   API    │    │ Bridge   │
    │         │    │  :8767   │    │  :8766   │
    └─────────┘    └──────────┘    └──────────┘
          │              │                │
          │              │                │
          └──────────────┴────────────────┘
                         │
                         ▼
              ┌──────────────────┐
              │   GNSS-SDR       │
              │   (started by    │
              │   Control API)   │
              └──────────────────┘
                         │
                         ▼
              ┌──────────────────┐
              │   SDRPlay RSPduo │
              │   (GPS antenna)  │
              └──────────────────┘
```

## Troubleshooting

### Check logs if something doesn't work:
```bash
tail -f /tmp/webui.log        # Web UI logs
tail -f /tmp/control_api.log  # Control API logs
tail -f /tmp/gnss_bridge.log  # GNSS Bridge logs
```

### Verify services are running:
```bash
lsof -i :3005  # Web UI
lsof -i :8767  # Control API
lsof -i :8766  # GNSS Bridge
```

### Kill everything if stuck:
```bash
pkill -9 -f start_all.sh
pkill -9 -f npm
pkill -9 -f control_api
pkill -9 -f gnss_sdr_bridge
pkill -9 -f gnss-sdr
```

## Requirements

- SDRPlay RSPduo with GPS antenna
- GNSS-SDR installed (`/usr/local/bin/gnss-sdr`)
- Node.js and npm (for Web UI)
- Python 3 with websockets and numpy

## First Time Setup

If GNSS-SDR is not installed:
```bash
cd gnss-sdr
./install_gnss_sdr.sh
```

## Tips

- **First acquisition takes 8-10 minutes** - be patient!
- GPS antenna needs **clear sky view** (roof, window, outside)
- **Bias-T enabled on Tuner 2** for active antenna power
- **Professional mode** uses real GNSS-SDR (not browser-based correlation)
- Data collection runs in **15-minute cycles** for continuous tracking

## Analyzing Russian Jamming

This setup was designed to detect GNSS interference from Kaliningrad Oblast:

1. Start collection in Gdańsk area
2. Wait 8-10 minutes for first results
3. Check satellite count (normal: 6-12, jammed: 0-2)
4. Check C/N0 values (normal: 35-45 dB-Hz, jammed: <30 dB-Hz)
5. Look for jamming alerts in UI
6. Save results: "Download spectrum" button

Expected jamming signatures:
- Low satellite count (1-3 instead of 8-12)
- Low C/N0 values (<30 dB-Hz)
- High acquisition failure rate (>80%)
- Jamming type: CW_TONE or BROADBAND_NOISE
