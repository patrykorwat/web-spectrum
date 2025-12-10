# Osmosdr Connection Monitoring

This document explains how the GNSS-SDR bridge monitors Osmosdr connectivity with SDRPlay in live mode.

## Prerequisites: Library Path Setup (REQUIRED)

Before using live mode, you **must** configure the library path so SoapySDR can find the SDRplay API:

### Problem
Without proper library path configuration, you'll see:
```
[ERROR] SoapySDR::loadModule() dlopen() failed:
  Library not loaded: @rpath/libsdrplay_api.so.3
No devices found! driver=sdrplay
```

### Solution

**Option 1: Automated Fix (Recommended)**
```bash
cd gnss-sdr
./fix_sdrplay_library_path.sh
# Then restart your terminal
```

**Option 2: Manual Fix**
Add to your `~/.zshrc` (or `~/.bash_profile`):
```bash
export DYLD_LIBRARY_PATH="/usr/local/lib:$DYLD_LIBRARY_PATH"
```

Then reload your shell:
```bash
source ~/.zshrc  # or source ~/.bash_profile
```

**Option 3: Current Session Only**
```bash
export DYLD_LIBRARY_PATH="/usr/local/lib:$DYLD_LIBRARY_PATH"
```

### Verification
Test that it works:
```bash
SoapySDRUtil --find="driver=sdrplay"
```

Should show:
```
Found device 0
  driver = sdrplay
  label = SDRplay Dev0 RSPduo ...
```

NOT:
```
No devices found! driver=sdrplay
```

## Overview

In live mode (`./start_all.sh live`), GNSS-SDR uses Osmosdr to directly access the SDRPlay device. The bridge monitors this connection through multiple mechanisms to detect disconnections and failures.

## Monitoring Architecture

```
SDRPlay → Osmosdr → GNSS-SDR → UDP Monitor → Bridge → WebSocket → UI
                        ↓
                  Process Monitor
                        ↓
                   Health Checks
```

## Monitoring Methods

### 1. Process Health Monitoring

**File:** [gnss_sdr_bridge.py:629-677](gnss_sdr_bridge.py#L629-L677)

The bridge monitors the GNSS-SDR process every 2 seconds:

```python
async def monitor_gnss_sdr_process(self):
    """Monitor GNSS-SDR process health"""
    while self.running:
        if self.gnss_sdr_process:
            if self.gnss_sdr_process.poll() is not None:
                # Process died - likely Osmosdr connection failed
                print("❌ GNSS-SDR CRASHED")
                # Notify clients via WebSocket
```

**Detects:**
- GNSS-SDR crashes
- Osmosdr driver failures
- Device disconnections (GNSS-SDR exits when Osmosdr loses device)

### 2. Data Flow Monitoring

**File:** [gnss_sdr_bridge.py:838-863](gnss_sdr_bridge.py#L838-L863)

The bridge tracks when data was last received:

```python
# Update timestamp when data arrives
self.last_data_time = time.time()

# Check if data is stale (>2 minutes old)
data_stale = (now - self.last_data_time) > 120.0
```

**Detects:**
- Osmosdr connection lost (device still connected but not streaming)
- Device in use by another program
- No GPS signal (antenna issue)

### 3. Device Status Checking

**File:** [gnss_sdr_bridge.py:585-603](gnss_sdr_bridge.py#L585-L617)

Safe device checking without using SoapySDRUtil (which can hang):

```python
def check_sdrplay_connected(self):
    """Check if SDRPlay device is still connected"""
    # Check if GNSS-SDR process is alive
    if self.gnss_sdr_process:
        if self.gnss_sdr_process.poll() is not None:
            return False  # Process died
    return True
```

**Why not SoapySDRUtil?**
- SoapySDRUtil can hang or crash
- Safer to infer status from GNSS-SDR process health
- Osmosdr manages the actual device connection

## Status Messages Sent to UI

The bridge sends detailed status in every WebSocket message:

```json
{
  "protocol": "GNSS_GPS_L1",
  "satellites": [...],
  "deviceStatus": {
    "sdrplayConnected": true/false,
    "gnssSdrCrashed": true/false,
    "dataStale": true/false,
    "deviceError": "Error message or null"
  }
}
```

### Error Messages

**When GNSS-SDR crashes:**
```
"GNSS-SDR stopped unexpectedly. Check if SDRPlay is connected
and not in use by another program."
```

**When data stops flowing:**
```
"No data received for 120s. Osmosdr connection may be lost."
```

**When connection is lost:**
```
"SDRPlay/Osmosdr connection lost. Check device and restart GNSS-SDR."
```

## What Gets Monitored

| Metric | Check Interval | Threshold | Action |
|--------|---------------|-----------|--------|
| GNSS-SDR process alive | 2 seconds | Process exit | Alert UI, log crash |
| Data received | 5 seconds | >120s since last | Alert UI, mark stale |
| Device connection | 5 seconds | Process status | Update UI status |

## Troubleshooting

### "GNSS-SDR CRASHED"

**Likely causes:**
1. SDRPlay disconnected during operation
2. Device already in use by another program (CubicSDR, SDRuno, etc.)
3. Osmosdr driver issue
4. Insufficient USB power
5. Permission issues

**Check:**
```bash
# 1. Check if device is detected
SoapySDRUtil --find="driver=sdrplay"

# 2. Check if device is in use
lsof | grep sdrplay

# 3. Check GNSS-SDR logs for Osmosdr errors
tail -f /tmp/gnss_bridge.log
```

**Fix:**
```bash
# Stop all programs using SDRPlay
pkill -f "CubicSDR|SDRuno|gnss-sdr"

# Restart GNSS-SDR
gnss-sdr --config_file=gnss_sdr_sdrplay_direct.conf

# Or use start_all.sh
./start_all.sh live
```

### "No data received for 120s"

**Likely causes:**
1. Osmosdr connection dropped (device still physically connected)
2. SDRPlay in use by another program (silent conflict)
3. No GPS signal (antenna issue)
4. Sample rate mismatch

**Check:**
```bash
# Monitor GNSS-SDR output for errors
tail -f /tmp/gnss_bridge.log | grep -i error

# Check antenna connection
# - Antenna should have clear sky view
# - Bias-T should be enabled (Tuner 2)
# - Check antenna cable for damage
```

### "SDRPlay/Osmosdr connection lost"

**This means GNSS-SDR process is running but marked as disconnected**

**Likely causes:**
1. Brief USB glitch (usually recovers)
2. Transitioning state (wait a few seconds)
3. Bridge couldn't verify device status

**Fix:**
- Usually recovers automatically
- If persists >30s, restart: `./start_all.sh live`

## Configuration

### Osmosdr Arguments

**File:** [gnss_sdr_sdrplay_direct.conf:23](gnss_sdr_sdrplay_direct.conf#L23)

```ini
SignalSource.osmosdr_args=sdrplay=0,driver=sdrplay,antenna="Tuner 2 50 ohm",biasT_ctrl=true
```

**Important parameters:**
- `sdrplay=0` - Use first SDRPlay device (device index)
- `driver=sdrplay` - Use SDRPlay driver
- `antenna="Tuner 2 50 ohm"` - Use Tuner 2 (supports bias-T)
- `biasT_ctrl=true` - Enable bias-T for active antenna

### Monitoring Thresholds

You can adjust thresholds in [gnss_sdr_bridge.py](gnss_sdr_bridge.py):

```python
# Line 843: Data staleness threshold (default: 120s)
data_stale = (now - self.last_data_time) > 120.0

# Line 677: Process check interval (default: 2s)
await asyncio.sleep(2.0)

# Line 863: Device check interval (default: 5s)
if now - self.last_device_check >= 5.0:
```

## Monitoring Output Examples

### Successful Operation
```
[10:30:15] 🛰️  SATELLITES LOCKED: 4 tracking
   Tracking: PRN 2, PRN 5, PRN 12, PRN 24
   ✅ Sufficient for position fix!
[10:30:15] 📤 Satellite data changed - broadcast to 1 client(s)
```

### Connection Lost
```
[10:35:22] ⚠️  NO DATA FOR 125s!
   Possible causes:
   • Osmosdr connection lost
   • SDRPlay in use by another program
   • No GPS signal (check antenna placement)
```

### GNSS-SDR Crash
```
[10:40:10] ❌ GNSS-SDR CRASHED (exit code: 1)
   Last error: [Osmosdr_Signal_Source] Cannot open SDRplay device
   Possible causes:
   • SDRPlay device disconnected
   • Device is in use by another program
   • Osmosdr driver issue
   • Insufficient permissions
```

## Best Practices

### For Reliable Operation

1. **Use dedicated USB port**
   - Avoid USB hubs if possible
   - Use USB 3.0 port for best power delivery

2. **Close other SDR software**
   - CubicSDR, SDRuno, GQRX, etc.
   - Only one program can access SDRPlay at a time

3. **Monitor the logs**
   ```bash
   # Watch bridge output in real-time
   tail -f /tmp/gnss_bridge.log
   ```

4. **Check antenna regularly**
   - Must have clear sky view (outdoors or window)
   - Bias-T must be enabled for active antennas
   - Check cable connections

5. **Use the Web UI**
   - Shows device status in real-time
   - Displays error messages automatically
   - No need to check logs manually

## Advanced Monitoring

### Add Custom Checks

You can extend monitoring by modifying [gnss_sdr_bridge.py](gnss_sdr_bridge.py):

```python
# Example: Monitor CPU usage
import psutil

def check_gnss_sdr_cpu(self):
    if self.gnss_sdr_process:
        try:
            process = psutil.Process(self.gnss_sdr_process.pid)
            cpu_percent = process.cpu_percent(interval=1.0)

            if cpu_percent > 90:
                print("⚠️ GNSS-SDR high CPU usage!")
        except:
            pass
```

### Log Analysis

```bash
# Find all connection issues
grep -E "(CRASHED|NO DATA|connection lost)" /tmp/gnss_bridge.log

# Count crashes
grep -c "GNSS-SDR CRASHED" /tmp/gnss_bridge.log

# Find Osmosdr errors
grep -i "osmosdr" /tmp/gnss_bridge.log
```

## See Also

- [GNSS-SDR Signal Source Documentation](https://gnss-sdr.org/docs/sp-blocks/signal-source/#implementation-osmosdr_signal_source)
- [SoapySDR SDRplay Module](https://github.com/pothosware/SoapySDRPlay3)
- [Osmosdr Source Block](https://github.com/osmocom/gr-osmosdr)
