# GPS Backend Services - Quick Start Guide

## 🚀 One-Command Startup

Start all backend services with a single command:

```bash
cd /Users/patrykorwat/git/web-spectrum/gnss-sdr
./start_backend.sh
```

This will start:
- **HTTP API Server** (port 5001) - Handles GPS recording requests
- **WebSocket Server** (port 8766) - Streams live GNSS data to UI

## 📋 Commands

```bash
./start_backend.sh start    # Start all services (default)
./start_backend.sh stop     # Stop all services
./start_backend.sh restart  # Restart all services
./start_backend.sh status   # Check service status
```

## 🔧 What Each Service Does

### 1. HTTP API Server (`recording_api_simple.py`)
- **Port**: 5001
- **Purpose**: RESTful API for GPS recording and processing
- **Endpoints**:
  - `POST /gnss/record` - Start GPS recording
  - `POST /gnss/process` - Process recorded data with GNSS-SDR
  - `GET /gnss/status` - Get recording/processing status
  - `GET /gnss/config` - Get current configuration
  - `GET /gnss/device-info` - Get SDRplay device information

### 2. WebSocket Server (`gnss_sdr_bridge.py`)
- **Port**: 8766
- **Purpose**: Real-time GPS data streaming to UI
- **Features**:
  - Parses GNSS-SDR output
  - Sends satellite tracking data
  - Sends position fixes (latitude/longitude)
  - GPS jamming/spoofing detection

## 📊 Logs

Service logs are saved to:
```
/Users/patrykorwat/git/web-spectrum/gnss-sdr/logs/
├── http_api.log      # HTTP API server logs
└── websocket.log     # WebSocket server logs
```

## ⚙️ Configuration

### Current Settings (Fixed for Thermal Stability)
- **Gain Reduction**: 30 dB (29 dB actual gain)
- **Sample Rate**: 2.048 MSPS
- **Frequency**: 1575.42 MHz (GPS L1)
- **Recording Duration**: 300 seconds (5 minutes)
- **Bias-T**: ENABLED (for active GPS antenna)
- **Port**: Antenna B (Port 2)

> ⚠️ **Important**: Gain is set to 30 dB reduction to prevent SDRplay thermal shutdown. Do not increase gain above this or recordings will stop after ~60 seconds!

## 🌐 Frontend Integration

After starting the backend, start the React frontend:

```bash
cd /Users/patrykorwat/git/web-spectrum
npm start
```

The UI will automatically connect to:
- HTTP API: `http://localhost:5001`
- WebSocket: `ws://localhost:8766`

## 🔍 Troubleshooting

### Backend not starting?
```bash
# Check status
./start_backend.sh status

# View logs
tail -f logs/http_api.log
tail -f logs/websocket.log

# Kill any stuck processes
pkill -f recording_api_simple.py
pkill -f gnss_sdr_bridge.py

# Restart
./start_backend.sh restart
```

### Ports already in use?
```bash
# Check what's using the ports
lsof -i :5001
lsof -i :8766

# Kill processes if needed
kill $(lsof -ti:5001)
kill $(lsof -ti:8766)
```

### SDRplay device not found?
```bash
# Check if device is connected
python3 detect_sdrplay.py

# Check SDRplay API service (macOS)
ps aux | grep sdrplay
```

## 📝 Key Files

- `start_backend.sh` - Main startup script
- `recording_api_simple.py` - HTTP API server
- `gnss_sdr_bridge.py` - WebSocket server
- `sdrplay_direct.py` - SDRplay device interface
- `gnss_sdr_file.conf` - GNSS-SDR configuration

## 🎯 Workflow

1. **Start backend**: `./start_backend.sh`
2. **Start frontend**: `npm start` (in parent directory)
3. **Open browser**: `http://localhost:3000`
4. **Click "Start Recording"** in UI
5. **Wait 5 minutes** for recording to complete
6. **Processing starts automatically**
7. **View position fix** after ~5-10 minutes

## ✅ Success Indicators

When working correctly, you should see:
- Both services showing "RUNNING" in status
- No errors in log files
- UI showing "Connected to WebSocket"
- After recording: Satellite data streaming to UI
- After processing: GPS coordinates displayed

## 🐛 Known Issues & Solutions

### Issue: Recordings stop at ~60 seconds
**Cause**: High gain causes SDRplay thermal shutdown
**Solution**: ✅ Already fixed! Gain set to 30 dB reduction

### Issue: No position fix after processing
**Cause**: Recording too short (< 3 minutes)
**Solution**: ✅ Already fixed! 5-minute recordings now work

### Issue: WebSocket shows "Disconnected"
**Cause**: gnss_sdr_bridge.py not running
**Solution**: `./start_backend.sh restart`

## 📞 Support

For issues, check:
1. Service status: `./start_backend.sh status`
2. Log files in `logs/` directory
3. SDRplay device connection
4. USB power (use powered hub if needed)
