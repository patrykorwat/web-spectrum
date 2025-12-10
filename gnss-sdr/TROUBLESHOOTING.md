# GNSS-SDR Pipeline Troubleshooting

## SDRplay Segmentation Fault (Exit Code -11)

### Symptom
```
WARNING: Streamer process exited immediately with code -11
```

This indicates a segmentation fault when initializing the SDRplay device.

### Common Causes

1. **SDRplay API Service Issues**
   - The sdrplay_apiService might be in a bad state
   - Device might be locked by another process

2. **Device Already in Use**
   - Another application is using the SDRplay device
   - Previous session didn't clean up properly

3. **Library Version Mismatch**
   - SDRplay API library version incompatible with device

### Solutions

#### 1. Restart SDRplay API Service (Recommended)

```bash
# Kill the service (it will auto-restart)
sudo killall sdrplay_apiService

# Wait a moment
sleep 3

# Verify it restarted
ps aux | grep sdrplay_apiService | grep -v grep
```

You should see output like:
```
root   12345  0.0  0.0  ...  /Library/SDRplayAPI/3.15.1/bin/sdrplay_apiService
```

#### 2. Check for Processes Using the Device

```bash
# Check if any other process is using SDRplay
lsof | grep sdrplay
ps aux | grep -i sdr | grep -v grep

# Kill any hanging processes
pkill -f sdrplay
pkill -f gnss-sdr
```

#### 3. Unplug and Replug the Device

```bash
# After unplugging and replugging the USB device:
# Restart the API service
sudo killall sdrplay_apiService
sleep 2

# Test the device
python3 -c "from sdrplay_direct import SDRplayDevice; sdr = SDRplayDevice(); print('OK')"
```

#### 4. Verify SDRplay API Installation

```bash
# Check library exists
ls -l /usr/local/lib/libsdrplay_api.dylib

# Check framework
ls -l /Library/Frameworks/sdrplay_api.framework/

# Check service
ps aux | grep sdrplay_apiService
```

### Testing After Fix

Once you've applied a fix, test the device:

```bash
cd gnss-sdr

# Quick test
python3 -c "
from sdrplay_direct import SDRplayDevice
print('Creating device...')
sdr = SDRplayDevice()
print('✓ Device OK')
sdr.set_frequency(1575.42e6)
print('✓ Frequency set')
"

# If that works, run the full pipeline
./run_gnss.sh
```

### Still Not Working?

If the above doesn't help:

1. **Check System Logs**
   ```bash
   # macOS
   log show --predicate 'process == "sdrplay_apiService"' --last 5m

   # Or check crash logs
   ls -lt ~/Library/Logs/DiagnosticReports/ | head -5
   ```

2. **Reinstall SDRplay API**
   - Download latest from https://www.sdrplay.com/downloads/
   - Reinstall completely
   - Restart your Mac

3. **Try SoapySDR Approach** (Alternative)
   ```bash
   # If direct API doesn't work, try via SoapySDR
   SoapySDRUtil --find="driver=sdrplay"
   ```

## Other Common Issues

### FIFO Blocking

**Symptom:** Pipeline hangs without output

**Solution:** The new version has 30-second timeouts, but if stuck:
```bash
# Kill everything
pkill -f sdrplay_fifo_streamer
pkill -f gnss-sdr

# Clean up FIFO
rm -f /tmp/gnss_fifo

# Restart
./run_gnss.sh
```

### No GPS Satellites Found

**Symptom:** GNSS-SDR runs but doesn't acquire satellites

**Solutions:**
1. Move device near window (GPS needs sky view)
2. Check antenna is connected
3. Wait 5-10 minutes for cold start
4. Verify device is tuned to GPS L1 (1575.42 MHz)

### Monitor Port 2101 Not Accessible

**Symptom:** Web interface can't connect

**Solution:**
```bash
# Check if GNSS-SDR is running
ps aux | grep gnss-sdr

# Check if port is listening
lsof -i :2101

# Check firewall settings
```

## Getting Help

Include this information when asking for help:

```bash
# System info
uname -a
sw_vers

# SDRplay info
ls -l /usr/local/lib/libsdrplay_api.dylib
ps aux | grep sdrplay_apiService

# Device info
python3 -c "from sdrplay_direct import SDRplayDevice; print('OK')" 2>&1

# Recent errors
ls -lt ~/Library/Logs/DiagnosticReports/ | head -3
```