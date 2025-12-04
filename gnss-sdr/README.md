# GNSS-SDR Integration for Web-Spectrum

Professional GNSS signal processing with SDRPlay devices.

## 🚀 ONE Command to Run Backend

```bash
./run_gnss_sdr_bridge.sh
```

This automatically:
- ✅ Kills any previous instances
- ✅ Starts GNSS-SDR with direct SDRPlay access
- ✅ Starts WebSocket server (port 8766)
- ✅ Forwards satellite data to web UI

## 📚 Documentation

- **[GNSS_SDR_COMPLETE_SETUP.md](./GNSS_SDR_COMPLETE_SETUP.md)** - Complete installation guide ⭐ START HERE
- **[GNSS_QUICK_REFERENCE.md](./GNSS_QUICK_REFERENCE.md)** - Daily command reference
- **[GNSS_FILES_REFERENCE.md](./GNSS_FILES_REFERENCE.md)** - File index and dependencies

## 📁 Files Overview

### Scripts (Run These)
- `run_gnss_sdr_bridge.sh` - **Main script** - ONE command to start backend
- `install_gnss_sdr.sh` - Install GNSS-SDR (one-time setup)
- `finish_osmosdr_install.sh` - Enable real-time SDRPlay access
- `record_iq_samples.py` - Record GPS samples for testing

### Configuration
- `gnss_sdr_config.conf` - Bridge mode config
- `gnss_sdr_file.conf` - File processing config
- `gnss_sdr_sdrplay_direct.conf` - Real-time SDRPlay config

### Core Components
- `gnss_sdr_bridge.py` - WebSocket bridge (auto-started)
- `sdrplay_to_gnss_sdr.py` - UDP streamer (auto-started)

## ✅ Quick Test (File-Based)

Verify everything works:

```bash
# 1. Record 60 seconds of GPS samples
python3 record_iq_samples.py /tmp/gps_iq_samples.dat 60

# 2. Process with GNSS-SDR
gnss-sdr --config_file=gnss_sdr_file.conf

# You should see: "Tracking of GPS L1 C/A signal started..."
```

## 🔧 Troubleshooting

### No Satellites?
- Check antenna has clear sky view
- Verify SDRPlay is connected: `SoapySDRUtil --probe="driver=sdrplay"`
- Try file-based test first

### Process Stuck?
The script now auto-kills previous instances, but if needed:
```bash
pkill -9 -f "gnss-sdr"
```

### More Help
See [GNSS_SDR_COMPLETE_SETUP.md](./GNSS_SDR_COMPLETE_SETUP.md) for full troubleshooting guide.

## 📊 What to Expect

**Successful output:**
```
Tracking of GPS L1 C/A signal started on channel 5 for satellite GPS PRN 06
Tracking of GPS L1 C/A signal started on channel 3 for satellite GPS PRN 19
...
```

With 4+ satellites, you'll get position fixes!

---

**Back to main:** [../README.md](../README.md)
