# GNSS-SDR + SDRPlay Complete Setup Guide

Complete guide for setting up professional GNSS signal processing with SDRPlay devices on macOS.

## 🎯 Overview

This guide will help you set up:
- **SDRPlay RSPduo** (or other SDRPlay devices) for GPS signal reception
- **GNSS-SDR** professional signal processing software
- **Web-Spectrum bridge** for visualization and analysis

## ✅ What You'll Get

- Real-time GPS satellite tracking
- Accurate C/N0 (Carrier-to-Noise) measurements
- Position/Velocity/Time (PVT) solutions
- Jamming and interference detection
- Support for GPS, Galileo, GLONASS, BeiDou

## 📋 Prerequisites

- **macOS 10.15+** (Catalina or later)
- **Homebrew** installed ([brew.sh](https://brew.sh))
- **SDRPlay RSPduo** (or other SDRPlay device)
- **GPS antenna** (active antenna recommended - needs bias-T power)
- **2-3 hours** for installation
- **~3GB** free disk space

## 🚀 Quick Start (Recommended)

If you just want to test with file-based processing (works immediately):

```bash
# 1. Record GPS samples (60 seconds)
DYLD_LIBRARY_PATH="/usr/local/lib:$DYLD_LIBRARY_PATH" \
PYTHONPATH="/opt/homebrew/lib/python3.14/site-packages:$PYTHONPATH" \
python3 record_iq_samples.py /tmp/gps_iq_samples.dat 60

# 2. Process with GNSS-SDR
gnss-sdr --config_file=gnss_sdr_file.conf

# You should see satellite tracking messages!
```

## 📦 Full Installation

### Step 1: Install SDRPlay API

```bash
# Download SDRPlay API from:
# https://www.sdrplay.com/downloads/

# Install the .pkg file
# This installs the API to /Library/SDRplayAPI/
```

### Step 2: Install System Dependencies

```bash
# Update Homebrew
brew update

# Install build tools
brew install cmake git pkg-config

# Install SDR libraries
brew install soapysdr

# Verify SDRPlay detection
SoapySDRUtil --probe="driver=sdrplay"
# You should see your SDRPlay device listed
```

### Step 3: Install GNSS-SDR

#### Option A: Basic Install (File Processing Only)

```bash
./install_gnss_sdr.sh
```

This installs GNSS-SDR with basic file processing support. Good for testing!

#### Option B: Full Install (Real-Time + File Processing)

For real-time SDRPlay access, you need gr-osmosdr with SoapySDR support:

```bash
# This script:
# 1. Builds gr-osmosdr with SoapySDR support
# 2. Rebuilds GNSS-SDR with Osmosdr enabled
# 3. Takes ~30-40 minutes
./finish_osmosdr_install.sh
```

### Step 4: Install Python Dependencies

```bash
# Create virtual environment (recommended)
python3 -m venv venv
source venv/bin/activate

# Install required packages
pip install numpy websockets
```

### Step 5: Setup Web UI

```bash
# Install Node.js dependencies
npm install

# Start web UI
npm start
# Opens at http://localhost:3005
```

## 🔧 Configuration Files

### For File Processing

**Config:** `gnss_sdr_file.conf`
- Processes pre-recorded IQ samples
- Output: KML/GPX files in `/tmp/`

### For Real-Time SDRPlay Access

**Config:** `gnss_sdr_sdrplay_direct.conf`
- Direct SDRPlay access via Osmosdr
- Requires gr-osmosdr installation

### For UDP Streaming (Bridge Mode)

**Config:** `gnss_sdr_config.conf`
- Receives IQ samples via UDP from SDRPlay streamer
- Currently has known issues (use file or direct mode instead)

## 🎮 Usage

### Method 1: File-Based Processing (Works Now!)

**Record samples:**
```bash
DYLD_LIBRARY_PATH="/usr/local/lib:$DYLD_LIBRARY_PATH" \
PYTHONPATH="/opt/homebrew/lib/python3.14/site-packages:$PYTHONPATH" \
python3 record_iq_samples.py /tmp/gps_iq_samples.dat 60
```

**Process with GNSS-SDR:**
```bash
gnss-sdr --config_file=gnss_sdr_file.conf
```

**Expected output:**
```
Tracking of GPS L1 C/A signal started on channel 5 for satellite GPS PRN 06 (Block IIF)
Tracking of GPS L1 C/A signal started on channel 3 for satellite GPS PRN 19 (Block IIR)
...
```

### Method 2: Real-Time Direct Access

**Prerequisites:** Completed Option B installation

```bash
DYLD_LIBRARY_PATH="/usr/local/lib:$DYLD_LIBRARY_PATH" \
gnss-sdr --config_file=gnss_sdr_sdrplay_direct.conf
```

### Method 3: Bridge Mode (Web UI Integration)

**Start the bridge:**
```bash
./run_gnss_sdr_bridge.sh
```

**Connect web UI:**
1. Go to SDRPlay Decoder page
2. Select "Professional Mode (GNSS-SDR)"
3. Click "Listen & Decode"

## 🐛 Troubleshooting

### No Satellites Detected

**Check antenna:**
```bash
# Verify SDRPlay is receiving signals
# Record samples and check file size
python3 record_iq_samples.py /tmp/test.dat 10
ls -lh /tmp/test.dat
# Should be ~80MB for 10 seconds
```

**Check antenna location:**
- GPS requires **clear view of sky**
- Move antenna **near window or outside**
- **Active antenna** needs bias-T power (enabled by default on Tuner 2)

### SDRPlay Not Detected

```bash
# Check if SDRPlay API is installed
ls /Library/SDRplayAPI/

# Check if SoapySDR can see it
SoapySDRUtil --probe="driver=sdrplay"

# Should show "driver=SDRplay, hardware=RSPduo" etc.
```

### Library Path Issues

The scripts set these automatically, but if you run commands manually:

```bash
export DYLD_LIBRARY_PATH="/usr/local/lib:$DYLD_LIBRARY_PATH"
export PYTHONPATH="/opt/homebrew/lib/python3.14/site-packages:$PYTHONPATH"
```

### "boost_system not found" Error

This was fixed in our scripts by patching gr-osmosdr's CMakeLists.txt to remove the `system` component (it's header-only in Boost 1.89).

### "Custom_UDP_Signal_Source not available"

Your GNSS-SDR build doesn't have UDP support. Use:
- **File processing** (works now)
- **Direct Osmosdr access** (requires full installation)

## 📊 Performance Tips

### Run VOLK Profiler

Optimizes signal processing for your CPU:
```bash
volk_gnsssdr_profile
```

### Adjust Acquisition Threshold

In config file, lower threshold for weak signals:
```ini
Acquisition_1C.threshold=0.005  # Default: 0.008
```

### Increase Doppler Range

For moving platforms:
```ini
Acquisition_1C.doppler_max=10000  # Default: 5000
```

## 📁 Output Files

GNSS-SDR generates several output files:

- **KML files:** `/tmp/PVT_*.kml` - View in Google Earth
- **GPX files:** `/tmp/PVT_*.gpx` - GPS tracks
- **RINEX:** (if enabled) - Post-processing data

## 🔬 Technical Details

### SDRPlay Configuration

- **Frequency:** 1575.42 MHz (GPS L1)
- **Sample Rate:** 2.048 MSPS
- **Gain:** 40 dB
- **Tuner:** 2 (with bias-T for active antenna)
- **Format:** gr_complex (32-bit float I/Q)

### GNSS-SDR Settings

- **Channels:** 8 simultaneous satellites
- **Acquisition:** PCPS algorithm
- **Tracking:** DLL/PLL with FLL pull-in
- **PVT:** RTKLIB Single Point Positioning

## 📚 References

- [GNSS-SDR Official Docs](https://gnss-sdr.org/docs/)
- [SDRPlay API Documentation](https://www.sdrplay.com/docs/)
- [SoapySDR Documentation](https://github.com/pothosware/SoapySDR/wiki)
- [gr-osmosdr GitHub](https://github.com/osmocom/gr-osmosdr)

## 🆘 Getting Help

If you encounter issues:

1. Check the log files:
   - GNSS-SDR logs: `/var/folders/.../gnss-sdr.log`
   - Bridge logs: Console output

2. Verify hardware:
   ```bash
   SoapySDRUtil --probe="driver=sdrplay"
   ```

3. Test file processing first (proves everything works)

4. Check [web-spectrum issues](https://github.com/patrykorwat/web-spectrum/issues)

## ✅ Verification Checklist

- [ ] SDRPlay API installed
- [ ] SoapySDR detects SDRPlay device
- [ ] GNSS-SDR installed and runs
- [ ] Can record IQ samples successfully
- [ ] File processing detects satellites
- [ ] (Optional) Real-time mode works
- [ ] Web UI connects to bridge

## 🎉 Success Indicators

You know it's working when you see:
```
Tracking of GPS L1 C/A signal started on channel X for satellite GPS PRN XX
```

With 4+ satellites tracking, you'll get PVT solutions (position fixes)!

---

**Last Updated:** December 2024
**Tested On:** macOS 15.2 (Sequoia), SDRPlay RSPduo, GNSS-SDR v0.0.20
