# SDRplay GPS Backend Services

Clean, production-ready backend for GPS recording and position fixing using SDRplay RSP2 and RTL-SDR devices.

## 🚀 Quick Start

```bash
cd /Users/patrykorwat/git/web-spectrum
./start_backend.sh
```

This starts:
- **HTTP API Server** (port 5001) - GPS recording/processing API
- **WebSocket Server** (port 8766) - Real-time GNSS data streaming

## 📋 Commands

```bash
./start_backend.sh start    # Start all services (default)
./start_backend.sh stop     # Stop all services
./start_backend.sh restart  # Restart all services
./start_backend.sh status   # Check service status
```

## 📁 Files

### Core Backend Scripts
- `../start_backend.sh` - Main startup script (in root directory)
- `recording_api_simple.py` - HTTP API server (port 5001)
- `gnss_sdr_bridge.py` - WebSocket server (port 8766)
- `sdrplay_direct.py` - SDRplay RSP2 device interface
- `detect_sdrplay.py` - SDRplay device detection utility
- `gnss_sdr_file.conf` - GNSS-SDR configuration

### Configuration
- **Gain**: 30 dB reduction (29 dB actual) - prevents thermal shutdown
- **Sample Rate**: 2.048 MSPS
- **Frequency**: 1575.42 MHz (GPS L1)
- **Duration**: 300 seconds (5 minutes)
- **Bias-T**: ENABLED for active antenna
- **Port**: Antenna B (Port 2)

## 🔧 Architecture

```
┌─────────────────┐
│   React UI      │ (port 3000)
│  (Frontend)     │
└────────┬────────┘
         │
    ┌────┴────┬──────────┐
    │         │          │
┌───▼───┐ ┌──▼────┐ ┌───▼───────┐
│ HTTP  │ │  WS   │ │ GNSS-SDR  │
│ API   │ │Bridge │ │ Processing│
│ 5001  │ │ 8766  │ └───────────┘
└───┬───┘ └───┬───┘
    │         │
    └────┬────┘
         │
    ┌────▼────────┐
    │  SDRplay    │
    │  RSP2       │
    │  (USB)      │
    └─────────────┘
```

## 📊 Directory Structure

```
web-spectrum/
├── start_backend.sh           # Main startup script (moved to root)
└── sdrplay-gps/
    ├── recording_api_simple.py    # HTTP API
    ├── gnss_sdr_bridge.py         # WebSocket server
    ├── sdrplay_direct.py          # SDRplay interface
    ├── detect_sdrplay.py          # Device detection
    ├── gnss_sdr_file.conf         # GNSS config
    ├── recordings/                # GPS recordings stored here
    ├── logs/                      # Service logs
    │   ├── http_api.log
    │   └── websocket.log
    └── .pids/                     # Process IDs (in root)
```

## ✅ Key Features & Fixes Applied

### ✅ Thermal Shutdown Fix
**Problem**: Recordings stopped at ~60 seconds
**Solution**: Reduced gain from 55 dB → 29 dB (30 dB reduction)
**Result**: Stable 5-minute recordings

### ✅ Event Handling Implementation
**Problem**: SDRplay PowerOverload events not acknowledged
**Solution**: Implemented full event callback following C API example
**Result**: Proper device event handling

### ✅ Bias-T Configuration
**Problem**: Active antenna not receiving power
**Solution**: Enabled Bias-T for all device types (RSP1A, RSP2, RSPduo)
**Result**: Antenna LNA powered correctly

## 🎯 Workflow

1. **Start backend**: `./start_backend.sh` (from root directory)
2. **Start frontend**: `npm start`
3. **Open browser**: http://localhost:3000
4. **Record**: Click "Start Recording" (5 minutes)
5. **Process**: Auto-starts after recording
6. **View**: GPS position appears after processing

## 🔍 Troubleshooting

### Backend not starting?
```bash
./start_backend.sh status
tail -f logs/http_api.log
tail -f logs/websocket.log
```

### Ports in use?
```bash
lsof -i :5001
lsof -i :8766
./start_backend.sh restart
```

### No position fix?
- Check recording completed full 5 minutes
- View GNSS-SDR processing logs
- Ensure C/N0 > 30 dB-Hz
- Check antenna connection and Bias-T power

## 📝 API Endpoints

### HTTP API (port 5001)
- `POST /gnss/record` - Start GPS recording
- `POST /gnss/process` - Process recorded data
- `GET /gnss/status` - Get status
- `GET /gnss/config` - Get configuration
- `GET /gnss/device-info` - SDRplay device info

### WebSocket (port 8766)
- Real-time satellite tracking data
- Position fixes (lat/lon)
- GPS jamming/spoofing detection
- C/N0 measurements

## 🐛 Known Issues & Solutions

| Issue | Solution |
|-------|----------|
| Recordings stop at ~60s | ✅ Fixed: Gain set to 30 dB reduction |
| No position fix | ✅ Fixed: 5-minute recordings now work |
| WebSocket disconnected | Restart: `./start_backend.sh restart` |
| SDRplay not found | Check USB connection, run `detect_sdrplay.py` |

## 📞 Support

For issues, check:
1. `./start_backend.sh status`
2. Log files in `logs/`
3. SDRplay device (USB connection)
4. Port availability (5001, 8766)
