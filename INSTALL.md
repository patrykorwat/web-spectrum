# Web-Spectrum Installation Guide

Complete installation guide for the Web-Spectrum GPS signal analysis platform.

## Table of Contents
- [Quick Start](#quick-start)
- [Detailed Installation](#detailed-installation)
- [Troubleshooting](#troubleshooting)
- [Verification](#verification)

---

## Quick Start

**For experienced users:**

```bash
# 1. Clone repository
git clone https://github.com/meshuga/web-spectrum.git
cd web-spectrum

# 2. Install Python dependencies
pip3 install -r requirements.txt
# OR on macOS with Homebrew: pip3 install --break-system-packages -r requirements.txt

# 3. Install Node.js dependencies
npm install

# 4. Install hardware drivers (see detailed instructions below)

# 5. Start services
./start_backend.sh  # Terminal 1
npm start           # Terminal 2
```

---

## Detailed Installation

### 1. System Requirements

**Operating Systems:**
- macOS 11.0+ (Big Sur or later)
- Linux (Ubuntu 20.04+, Debian 11+)
- Windows 10/11 (partial support)

**Hardware:**
- RTL-SDR dongle ($25-40) OR SDRPlay device ($200-300)
- GPS active antenna (requires bias-T or external power)
- USB 2.0/3.0 port
- 4GB RAM minimum, 8GB recommended
- 10GB free disk space for recordings

**Software:**
- Python 3.9+
- Node.js 16+
- npm 8+
- Git

---

### 2. Clone Repository

```bash
git clone https://github.com/meshuga/web-spectrum.git
cd web-spectrum
```

---

### 3. Python Dependencies

Install Python packages using the comprehensive requirements file:

#### Option 1: Standard Installation (Recommended)

```bash
pip3 install -r requirements.txt
```

#### Option 2: macOS with Homebrew Python

If you get PEP 668 errors on macOS:

```bash
pip3 install --break-system-packages -r requirements.txt
```

#### Option 3: Virtual Environment (Cleanest)

```bash
# Create virtual environment
python3 -m venv venv

# Activate it
source venv/bin/activate  # macOS/Linux
# OR on Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

**Packages Installed:**
- numpy - Signal processing, FFT
- websockets - Real-time data streaming
- requests - HTTP client for Gypsum
- python-dateutil - GPS timestamp parsing
- And other supporting libraries

---

### 4. Hardware Drivers

#### RTL-SDR Drivers

**macOS:**
```bash
brew install librtlsdr
```

**Linux (Ubuntu/Debian):**
```bash
sudo apt-get update
sudo apt-get install rtl-sdr
```

**Verify:**
```bash
rtl_test -t
# Should detect your RTL-SDR device
```

#### SDRPlay API (Optional - only if using SDRPlay)

**macOS:**
1. Download from [SDRplay.com](https://www.sdrplay.com/downloads/)
2. Install SDRplay API v3.15 or later
3. Verify:
```bash
ls /Library/SDRplayAPI/
# Should show: 3.15.1 or similar
```

**Linux:**
1. Download from [SDRplay.com](https://www.sdrplay.com/downloads/)
2. Run the installer script
3. Verify:
```bash
ls /usr/local/lib | grep sdrplay
```

---

### 5. GNSS-SDR Installation (Required for GPS Processing)

GNSS-SDR is the professional GPS signal processor used by both RTL-SDR and SDRPlay modes.

#### macOS Installation

```bash
cd gnss-sdr
./install_gnss_sdr.sh
```

**What it does:**
- Installs Homebrew dependencies (Boost, GLOG, Armadillo, etc.)
- Clones GNSS-SDR source code
- Builds from source (takes 30-40 minutes)
- Installs to `/usr/local/bin/gnss-sdr`

**Verify:**
```bash
gnss-sdr --version
# Should output: gnss-sdr version 0.0.19
```

#### Linux Installation (Ubuntu/Debian)

```bash
# Add GNSS-SDR PPA
sudo add-apt-repository ppa:gnss-sdr/ppa
sudo apt-get update

# Install GNSS-SDR
sudo apt-get install gnss-sdr

# Verify
gnss-sdr --version
```

---

### 6. Node.js Dependencies

```bash
npm install
```

This installs:
- React and Material-UI components
- WebUSB and Web Serial polyfills
- Charting libraries
- Build tools

---

### 7. Gypsum GPS Decoder (Optional)

Gypsum is a Python-based GPS decoder alternative to GNSS-SDR.

**Already included!** The Gypsum repository is cloned in `rtl-sdr-gps/gypsum/`

**Dependencies are installed** via `requirements.txt` in step 3.

**Optional visualization dependencies:**

If you want matplotlib-based satellite tracking:

```bash
pip3 install matplotlib pillow
```

---

## Starting the System

### Easy Mode (Recommended)

```bash
# Terminal 1: Start backend services
./start_backend.sh

# Terminal 2: Start web application
npm start
```

The backend script automatically starts:
- HTTP API on port 5001
- WebSocket server on port 8766

### Manual Mode

```bash
# Terminal 1: HTTP API
cd sdrplay-gps
python3 recording_api_simple.py

# Terminal 2: WebSocket Bridge
python3 gnss_sdr_bridge.py

# Terminal 3: Web UI
npm start
```

### Access the Application

Open your browser to: **http://localhost:3005**

---

## Verification

### 1. Check Backend Services

```bash
# Check if services are running
lsof -i :5001  # HTTP API
lsof -i :8766  # WebSocket

# OR use the status command
./start_backend.sh status
```

### 2. Check RTL-SDR Device

```bash
rtl_test -t
# Should output device info
```

### 3. Test GNSS-SDR

```bash
gnss-sdr --version
# Should output version number
```

### 4. Check Python Dependencies

```bash
python3 -c "import numpy, websockets, requests, dateutil; print('All dependencies OK!')"
# Should print: All dependencies OK!
```

---

## Troubleshooting

### "ModuleNotFoundError: No module named 'requests'"

**Solution:**
```bash
pip3 install -r requirements.txt
```

### "rtl_sdr: command not found"

**macOS:**
```bash
brew install librtlsdr
```

**Linux:**
```bash
sudo apt-get install rtl-sdr
```

### "gnss-sdr: command not found"

**Install GNSS-SDR:**
```bash
cd gnss-sdr
./install_gnss_sdr.sh  # macOS
# OR
sudo apt-get install gnss-sdr  # Linux
```

### "error: externally-managed-environment"

**Solution 1 - Use virtual environment (recommended):**
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

**Solution 2 - Use --break-system-packages (macOS):**
```bash
pip3 install --break-system-packages -r requirements.txt
```

### Backend won't start

**Check Python version:**
```bash
python3 --version
# Should be 3.9 or higher
```

**Check port availability:**
```bash
lsof -i :5001
lsof -i :8766
# If occupied, kill the processes or change ports
```

### No GPS position fix

**Possible causes:**
1. **Indoor location** - Move antenna near window or outdoors
2. **Short recording** - Record at least 60 seconds
3. **Weak antenna** - Use active antenna with bias-T enabled
4. **Bias-T disabled** - Enable in UI settings
5. **Poor satellite visibility** - Check sky is clear

### Gypsum fails with "No position fix"

**Solutions:**
1. Record longer (120+ seconds recommended)
2. Ensure good antenna placement
3. Check dependencies are installed
4. Try GNSS-SDR decoder instead (more robust)

---

## Next Steps

1. **Test with a quick recording:**
   - Select RTL-SDR or SDRPlay tab
   - Choose 30-60 second duration
   - Click "Start Recording"
   - Wait for processing
   - View spectrum and position results

2. **Explore decoder options:**
   - Try both GNSS-SDR and Gypsum
   - Compare processing times
   - Learn about GPS signal processing

3. **Experiment with jamming detection:**
   - Record in different environments
   - Check spectrum analysis for interference
   - View jamming detection metrics

---

## Getting Help

- **GitHub Issues:** https://github.com/meshuga/web-spectrum/issues
- **README:** See main [README.md](README.md) for features and usage
- **Requirements:** See [requirements.txt](requirements.txt) for all dependencies

---

## License

This project is licensed under the GNU Affero General Public License v3.0 - see LICENSE file for details.
