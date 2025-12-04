# GNSS-SDR Quick Reference Card

Quick commands for daily use of GNSS-SDR with SDRPlay.

## 🚀 Quick Start Commands

### File-Based Processing (Recommended for Testing)

```bash
# 1. Record 60 seconds of GPS samples
DYLD_LIBRARY_PATH="/usr/local/lib:$DYLD_LIBRARY_PATH" \
PYTHONPATH="/opt/homebrew/lib/python3.14/site-packages:$PYTHONPATH" \
python3 record_iq_samples.py /tmp/gps_iq_samples.dat 60

# 2. Process with GNSS-SDR
gnss-sdr --config_file=gnss_sdr_file.conf
```

### Web UI Integration (Bridge Mode)

```bash
# Terminal 1: Start web UI
npm start

# Terminal 2: Start bridge (auto-starts GNSS-SDR + SDRPlay)
./run_gnss_sdr_bridge.sh

# Browser: http://localhost:3005
# Go to SDRPlay Decoder → Professional Mode → Listen & Decode
```

### Real-Time Direct Access (Requires gr-osmosdr)

```bash
DYLD_LIBRARY_PATH="/usr/local/lib:$DYLD_LIBRARY_PATH" \
gnss-sdr --config_file=gnss_sdr_sdrplay_direct.conf
```

## 🔧 Diagnostic Commands

### Check SDRPlay Detection

```bash
# Verify SDRPlay API is working
SoapySDRUtil --probe="driver=sdrplay"
# Should show: driver=SDRplay, hardware=RSPduo
```

### Test IQ Sample Recording

```bash
# Record 10 seconds (should be ~80MB)
python3 record_iq_samples.py /tmp/test.dat 10
ls -lh /tmp/test.dat
```

### Check GNSS-SDR Logs

```bash
# View latest GNSS-SDR log
tail -100 /var/folders/kb/vvb0_0451_x3q_xpkdt_ggpw0000gn/T/gnss-sdr.log
```

### Kill Stuck Processes

```bash
# Kill all GNSS-SDR and SDRPlay processes
pkill -9 gnss-sdr
pkill -9 -f "python.*sdrplay"
```

## 📝 Configuration Files

| File | Purpose | Mode |
|------|---------|------|
| `gnss_sdr_file.conf` | Process recorded files | File-based |
| `gnss_sdr_sdrplay_direct.conf` | Real-time SDRPlay | Direct Osmosdr |
| `gnss_sdr_config.conf` | UDP streaming | Bridge (experimental) |

## 🎯 Expected Output

### Successful Satellite Tracking

```
Tracking of GPS L1 C/A signal started on channel 5 for satellite GPS PRN 06
Tracking of GPS L1 C/A signal started on channel 3 for satellite GPS PRN 19
Tracking of GPS L1 C/A signal started on channel 4 for satellite GPS PRN 13
...
```

### No Satellites (Troubleshooting Needed)

```
Current receiver time: 1 s
Current receiver time: 2 s
...
# No "Tracking" messages = problem with signal/antenna
```

## 🔍 Troubleshooting Quick Fixes

### No Satellites Detected

```bash
# 1. Check antenna placement (needs clear sky view)
# 2. Verify bias-T is enabled (for active antenna)
# 3. Try recording samples to check if SDRPlay is working
python3 record_iq_samples.py /tmp/test.dat 10
ls -lh /tmp/test.dat  # Should be ~80MB
```

### "No SDRPlay devices found"

```bash
# Check SDRPlay API
ls /Library/SDRplayAPI/
# Should exist and contain API files

# Restart SDRPlay service
sudo killall sdrplay_apiService
# Service will auto-restart when needed
```

### Library Path Errors

```bash
# Always export these before running commands
export DYLD_LIBRARY_PATH="/usr/local/lib:$DYLD_LIBRARY_PATH"
export PYTHONPATH="/opt/homebrew/lib/python3.14/site-packages:$PYTHONPATH"
```

## 📊 Performance Optimization

### Run VOLK Profiler (One-Time)

```bash
volk_gnsssdr_profile
# Takes 5-10 minutes, optimizes for your CPU
```

### Adjust for Weak Signals

Edit config file:
```ini
Acquisition_1C.threshold=0.005  # Lower = more sensitive (default: 0.008)
```

## 📁 Output File Locations

| File Type | Location | Purpose |
|-----------|----------|---------|
| KML tracks | `/tmp/PVT_*.kml` | Google Earth visualization |
| GPX tracks | `/tmp/PVT_*.gpx` | GPS tracks for mapping apps |
| IQ samples | `/tmp/gps_iq_samples.dat` | Recorded signal data |
| Logs | `/var/folders/.../gnss-sdr.log` | Debug information |

## 🔄 Common Workflows

### Daily GPS Testing

```bash
# Quick test (file-based)
python3 record_iq_samples.py /tmp/gps_iq_samples.dat 60
gnss-sdr --config_file=gnss_sdr_file.conf

# Check for satellites in output
```

### Web UI Development

```bash
# Terminal 1: Run bridge
./run_gnss_sdr_bridge.sh

# Terminal 2: Run web UI in dev mode
npm start

# Browser: http://localhost:3005
```

### Batch Processing Multiple Files

```bash
# Record multiple samples
for i in {1..5}; do
    python3 record_iq_samples.py /tmp/gps_sample_$i.dat 60
    sleep 10
done

# Process each file
for i in {1..5}; do
    gnss-sdr --config_file=gnss_sdr_file.conf \
             --GNSS-SDR.internal_fs_sps=2048000 \
             --SignalSource.filename=/tmp/gps_sample_$i.dat
done
```

## ⚡ Quick Tips

1. **First time setup?** Start with file-based processing
2. **No satellites?** Check antenna has clear sky view
3. **Want real-time?** Run `./finish_osmosdr_install.sh` first
4. **Process stuck?** Kill with `pkill -9 gnss-sdr`
5. **Need help?** Check [Complete Setup Guide](./GNSS_SDR_COMPLETE_SETUP.md)

## 📞 Support

- **Documentation:** [GNSS_SDR_COMPLETE_SETUP.md](./GNSS_SDR_COMPLETE_SETUP.md)
- **Issues:** [GitHub Issues](https://github.com/patrykorwat/web-spectrum/issues)
- **GNSS-SDR Docs:** [gnss-sdr.org/docs](https://gnss-sdr.org/docs/)

---

**Tip:** Bookmark this page for quick reference! 📌
