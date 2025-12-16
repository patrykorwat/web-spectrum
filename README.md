# web-spectrum

Web-based spectrum analyzer and GPS signal analysis platform.

Visit [patrykorwat.github.io/web-spectrum](https://meshuga.github.io/web-spectrum/) to access the app.

## Features
* **Spectrum analyzer** - Real-time frequency analysis
* **GPS signal recording & analysis** - Professional-grade GNSS processing
* **Data decoding** - ADS-B, ISM, and multi-constellation GNSS

## Supported Devices
* **tinySA Ultra** - Spectrum analyzer
* **RTL-SDR** (RTL2832U) - Including V4 dongles ($25-40)
* **SDRPlay** (RSPduo, RSP1A, etc.) - Professional SDR receivers ($200-300)

## Supported Browsers
* Chrome
* Edge
* Opera

See more: [caniuse.com/web-serial](https://caniuse.com/web-serial), [caniuse.com/webusb](https://caniuse.com/webusb)

## Installation

### Prerequisites
```bash
# Clone repository
git clone https://github.com/meshuga/web-spectrum.git
cd web-spectrum

# Install Node.js dependencies
npm install
```

### GNSS-SDR Installation (Required for GPS Analysis)

GNSS-SDR is required for professional GPS signal processing with both SDRPlay and RTL-SDR devices.

**macOS Installation:**
```bash
cd gnss-sdr
./install_gnss_sdr.sh
```

The installation script will:
- Install Homebrew dependencies (Boost, GLOG, Armadillo, etc.)
- Clone and build GNSS-SDR from source
- Install to `/usr/local/bin/gnss-sdr`
- Takes approximately 30-40 minutes

**Verify Installation:**
```bash
gnss-sdr --version
# Should output: gnss-sdr version 0.0.19
```

### SDRPlay API Installation

**macOS:**
```bash
# Download from SDRplay website
# https://www.sdrplay.com/downloads/
# Install SDRplay API v3.15 or later

# Verify installation
ls /Library/SDRplayAPI/
# Should show: 3.15.1 (or similar)
```

### Python Dependencies
```bash
# Install Python packages for SDRPlay recording
pip3 install numpy websockets

# Optional: For protobuf PVT message parsing
pip3 install protobuf
```

## Quick Start

### Start the Web Application
```bash
npm start
# Opens browser at http://localhost:3005
```

### Start Backend Services

**For SDRPlay GPS Recording:**
```bash
# Terminal 1: Start recording API server
cd sdrplay-gps
python3 recording_api_simple.py
# Listens on http://localhost:3001

# Terminal 2: Start GNSS-SDR bridge
python3 gnss_sdr_bridge.py
# Listens on ws://localhost:8766
```

**For RTL-SDR GPS Recording:**
```bash
# Terminal 1: Start recording API server
cd rtl-sdr-gps
python3 recording_api_simple.py
# Listens on http://localhost:3001

# Terminal 2: Start GNSS-SDR bridge
python3 gnss_sdr_bridge.py
# Listens on ws://localhost:8766
```

### Using the GPS Recording Feature

1. **Open browser** at [http://localhost:3005](http://localhost:3005)
2. **Navigate** to SDRPlay or RTL-SDR Decoder page
3. **Select mode**: "Professional Mode (GNSS-SDR)"
4. **Start recording**: Click "⏺ Start Recording (5 min)"
5. **Wait for processing**: Spectrum analysis runs automatically
6. **View results**:
   - Spectrum waterfall showing GPS signals and jamming
   - Position fix (latitude, longitude, altitude)
   - Satellite tracking status

## Device-Specific Features

### TinySA Ultra
![decode](decode.jpg)

**Spectrum Analyzer Mode:**
- Real-time frequency sweep and display
- Signal strength measurements
- Waterfall display

**Decode Mode:**
- Trigger-based signal capture
- Decodes messages up to ~24 bits
- Supports various modulation schemes

### RTL-SDR

![decode1](rtl-sdr-ads-b.jpg)
![decode2](rtl-sdr-ism.png)

**Browser Processing Mode:**
Direct in-browser signal decoding:
- **ADS-B** - Aircraft position tracking (1090 MHz)
- **ISM GateTX** - 433/868 MHz protocols
- **Basic GNSS** - GPS L1, Galileo E1, GLONASS L1OF, BeiDou B1I

**Professional Mode (GNSS-SDR):**
- Record GPS signals to file (2.048 MSPS)
- Process with GNSS-SDR for satellite tracking
- Spectrum analysis with jamming detection
- Position fix calculation
- Works with any RTL-SDR dongle ($25-40)

### SDRPlay (RSPduo, RSP1A, etc.)

![sdrplay-gnss-sdr](sdrplay-gnss-sdr.png)

**Professional GPS Recording & Analysis:**

SDRPlay devices work with GNSS-SDR for professional-grade GPS signal analysis:

**Features:**
- ✅ **5-minute GPS recordings** at 2.048 MSPS (4.9 GB files)
- ✅ **Automatic spectrum analysis** - Detects GPS satellites and jamming
- ✅ **Position calculation** - Latitude, longitude, altitude from GNSS-SDR
- ✅ **Jamming detection** - Visual spectrum + statistical analysis
- ✅ **Direct API control** - Python-based SDRPlay API (no SoapySDR required)
- ✅ **Web-based UI** - Monitor recordings and results in browser

**Recording Configuration:**
- Frequency: 1575.42 MHz (GPS L1 C/A)
- Sample rate: 2.048 MSPS
- Bandwidth: 1.536 MHz (captures GPS main lobe)
- Gain: 29 dB (prevents thermal issues)
- Format: Complex64 (IQ)
- Tuner: Selectable (RSPduo Tuner 1 or 2)
- Bias-T: Enabled for active antennas

**Workflow:**
1. **Record** → 5-minute IQ sample capture to `.dat` file
2. **Process** → GNSS-SDR analyzes signal, tracks satellites
3. **Analyze** → Python generates spectrum waterfall
4. **Display** → View results in web UI

**Output Files:**
- `gps_recording_YYYYMMDD_HHMMSS.dat` - Raw IQ samples (4.9 GB)
- `gps_recording_YYYYMMDD_HHMMSS_spectrum.png` - Spectrum waterfall
- `gps_recording_YYYYMMDD_HHMMSS_spectrum_analysis.json` - Jamming metrics
- `gps_recording_YYYYMMDD_HHMMSS.nmea` - Position fixes
- `gps_recording_YYYYMMDD_HHMMSS.kml` - Google Earth track

**Supported Constellations:**
- GPS L1 C/A (USA) - 1575.42 MHz
- Galileo E1 (Europe) - 1575.42 MHz
- GLONASS L1OF (Russia) - 1602 MHz
- BeiDou B1I (China) - 1561.098 MHz

## References

YT videos with explanations and tests:
* [Web (r)evolution in lab electronics? Building a Web Spectrum Analyzer for TinySA Ultra](https://www.youtube.com/watch?v=XeK0TL0F8DI)
* [Signal decoding with TinySA Ultra](https://www.youtube.com/watch?v=bqgmftWSKPc)
* [RTL-SDR signal decoding in a web application](https://www.youtube.com/watch?v=Wm7sMXXT5Xs)

## Development

In the project directory, you can run:

### `npm start`

Runs the app in the development mode.\
Open [http://localhost:3005](http://localhost:3005) to view it in your browser.

The page will reload when you make changes.\
You may also see any lint errors in the console.

### `npm test`

Launches the test runner in the interactive watch mode.\
See the section about [running tests](https://facebook.github.io/create-react-app/docs/running-tests) for more information.

### `npm run build`

Builds the app for production to the `build` folder.\
It correctly bundles React in production mode and optimizes the build for the best performance.

The build is minified and the filenames include the hashes.\
Your app is ready to be deployed!

See the section about [deployment](https://facebook.github.io/create-react-app/docs/deployment) for more information.
