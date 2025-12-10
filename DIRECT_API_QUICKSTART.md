# 🚀 Direct SDRplay API - Quick Start

## ONE Command to Rule Them All!

Your `start_all.sh` script now supports **direct SDRplay API access**!

### Usage

```bash
# Start with Direct SDRplay API (NEW - RECOMMENDED)
./start_all.sh direct

# Or use existing modes:
./start_all.sh file    # File-based mode (default)
./start_all.sh live    # Live Osmosdr mode (has compatibility issues)
```

## What Happens in Direct Mode?

When you run `./start_all.sh direct`, it automatically:

1. ✅ **Starts SDRplay Direct API Streamer**
   - Connects directly to SDRplay hardware (no SoapySDR/gr-osmosdr)
   - Streams IQ samples to `/tmp/gps_iq_samples.dat`
   - Full control over device parameters

2. ✅ **Starts Control API** (port 8767)
   - Web UI buttons to Start/Stop/Restart GPS

3. ✅ **Starts GNSS Bridge** (port 8766)
   - Relays satellite data to web UI via WebSocket

4. ✅ **Starts Web UI** (port 3005)
   - Professional GNSS-SDR interface

## Architecture Comparison

### Old Way (File Mode)
```
Manual recording → File → GNSS-SDR → Bridge → Web UI
     ↑
  YOU have to start recorder manually
```

### Old Way (Live Mode - Has Issues)
```
SDRplay → SoapySDR → gr-osmosdr → GNSS-SDR → Bridge → Web UI
                         ↑
                    ❌ CRASHES on setIQBalance
```

### **NEW WAY (Direct Mode)** ✨
```
SDRplay → Python Direct API → File → GNSS-SDR → Bridge → Web UI
              ↑
         ✅ AUTOMATIC & STABLE
         Full device control
         No compatibility issues
```

## Step-by-Step

### 1. Stop any running instances
```bash
pkill -9 -f "npm start"
pkill -9 -f "control_api.py"
pkill -9 -f "gnss_sdr_bridge.py"
pkill -9 -f "gnss-sdr"
```

### 2. Start everything with ONE command
```bash
./start_all.sh direct
```

### 3. Wait for services to start (~10 seconds)
You'll see:
```
✓ SDRplay API is ready
✓ SDRplay Direct API Streamer started
✓ Control API started
✓ GNSS Bridge started
✓ Web UI started
```

### 4. Open browser
```
http://localhost:3005
```

### 5. Use the UI
1. Select "Professional Mode (GNSS-SDR)"
2. Click "Listen & Decode"
3. See satellite data in real-time!

### 6. Monitor logs (optional)
```bash
# In separate terminals:
tail -f /tmp/sdrplay_streamer.log    # Direct API streamer
tail -f /tmp/gnss_bridge.log         # GNSS-SDR output
tail -f /tmp/control_api.log         # Control API
tail -f /tmp/webui.log               # Web UI
```

### 7. Stop everything
Just press **Ctrl+C** in the terminal where you ran `./start_all.sh`

All services will shut down gracefully.

## Benefits of Direct Mode

| Feature | File Mode | Live Mode | **Direct Mode** |
|---------|-----------|-----------|----------------|
| **Auto-start** | ❌ Manual | ⚠️ Crashes | ✅ Automatic |
| **Stability** | ✅ Stable | ❌ Crashes | ✅ Stable |
| **Control** | ⚠️ Limited | ⚠️ Limited | ✅ Full |
| **Setup** | Manual | Failed | **ONE command** |
| **Device features** | ⚠️ Basic | ⚠️ Limited | ✅ All |
| **Dependencies** | Many | Many | **Minimal** |

## Customization

Want to adjust parameters? Edit `start_all.sh` around line 124:

```bash
python3 -u sdrplay_streamer.py \
    --output /tmp/gps_iq_samples.dat \
    --frequency 1575.42e6 \      # GPS L1 frequency
    --sample-rate 2.048e6 \      # Sample rate
    --gain 40 \                  # Gain reduction (lower = more gain)
    --bandwidth 1536 \           # Bandwidth in kHz
    > /tmp/sdrplay_streamer.log 2>&1 &
```

### Common Adjustments

**Higher gain (weak signal):**
```bash
--gain 20  # More gain (40 → 20 = +20dB more gain)
```

**Lower gain (strong signal/interference):**
```bash
--gain 50  # Less gain (40 → 50 = -10dB less gain)
```

**Different frequency (e.g., GPS L2):**
```bash
--frequency 1227.60e6
```

**Different bandwidth:**
```bash
--bandwidth 5000  # Wider bandwidth
```

## Troubleshooting

### "SDRplay API not available"

**Check service:**
```bash
ps aux | grep sdrplay_apiService
```

Should show: `/Library/SDRplayAPI/3.15.1/bin/sdrplay_apiService`

**If not running:**
```bash
sudo /Library/SDRplayAPI/3.15.1/bin/sdrplay_apiService restart
```

### "No SDRplay devices found"

**Check USB connection:**
```bash
system_profiler SPUSBDataType | grep -A 10 SDRplay
```

Should show your SDRplay device.

### "Failed to start SDRplay streamer"

**Check logs:**
```bash
tail -f /tmp/sdrplay_streamer.log
```

**Test manually:**
```bash
cd gnss-sdr
python3 test_sdrplay_api.py
```

Should show "SUCCESS: SDRplay API is working!"

### No satellite data

**Wait 1-2 minutes** for GPS cold start acquisition

**Check antenna:**
- Clear sky view required
- Active antenna needs bias-T (enabled by default)
- Try different location (near window)

**Check gain:**
Try adjusting gain in `start_all.sh` (20-50 range)

**Monitor streamer:**
```bash
tail -f /tmp/sdrplay_streamer.log
```

Should show sample rate ~2.048 MSPS

## What's Running?

After `./start_all.sh direct`, you have:

```
┌─────────────────────┐
│  SDRplay Hardware   │ (USB device)
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ sdrplay_streamer.py │ (PID shown at startup)
│ Port: None          │
│ Output: /tmp/*.dat  │
│ Log: sdrplay_*.log  │
└──────────┬──────────┘
           │
           ▼ (file)
┌─────────────────────┐
│     gnss-sdr        │ (Started by bridge)
│ Reads: /tmp/*.dat   │
│ Sends: UDP port 1234│
└──────────┬──────────┘
           │
           ▼ (UDP)
┌─────────────────────┐
│  gnss_sdr_bridge.py │ (Shows satellites)
│ Port: 8766 (WS)     │
│ Log: gnss_bridge.*  │
└──────────┬──────────┘
           │
           ▼ (WebSocket)
┌─────────────────────┐
│      Web UI         │ (Browser interface)
│ Port: 3005 (HTTP)   │
│ Log: webui.log      │
└─────────────────────┘
     ▲
     │ (HTTP API)
     │
┌─────────────────────┐
│   control_api.py    │ (Start/Stop buttons)
│ Port: 8767 (HTTP)   │
│ Log: control_api.*  │
└─────────────────────┘
```

## Advanced: Manual Control

If you want fine control, you can run components separately:

```bash
# Terminal 1: Start streamer manually
cd gnss-sdr
python3 sdrplay_streamer.py --output /tmp/gps_iq_samples.dat

# Terminal 2: Start GNSS bridge
python3 gnss_sdr_bridge.py --config gnss_sdr_file.conf --no-sdrplay

# Terminal 3: Start web UI
cd ..
npm start
```

But why do that when `./start_all.sh direct` does it all? 😊

## More Information

- **Complete API docs:** [gnss-sdr/SDRPLAY_DIRECT_API.md](gnss-sdr/SDRPLAY_DIRECT_API.md)
- **Quick reference:** [gnss-sdr/README_DIRECT_API.md](gnss-sdr/README_DIRECT_API.md)
- **Implementation details:** [gnss-sdr/DIRECT_API_SUMMARY.txt](gnss-sdr/DIRECT_API_SUMMARY.txt)

---

## Summary

```bash
# Everything you need:
./start_all.sh direct

# Open browser:
http://localhost:3005

# Stop everything:
Ctrl+C
```

**That's it! Enjoy your direct SDRplay access! 🎉**
