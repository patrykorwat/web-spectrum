# web-spectrum
Web app for spectrum analyzers.

Visit [patrykorwat.github.io/web-spectrum](https://meshuga.github.io/web-spectrum/) to access the app.

The application has two features:
* Spectrum analyzer
* Data decoding

Supported devices:
* tinySA Ultra
* RTL-SDR with RTL2832U (includes V4)
* SDRPlay (tested with RSPduo) (via WebSocket-based bridge)

Supported environments:
* Chrome
* Edge
* Opera

See more: [caniuse.com/web-serial](https://caniuse.com/web-serial), [caniuse.com/webusb](https://caniuse.com/webusb)

## Spectrum analyzer
![spectrum ](spectrum.gif)

Spectrum analyzer allows for showing available spectrum for requested frequencies.

## Data decoding
Data decode sets a trigger and upon detection of a signal, the device captures it for decoding purposes.

### TinySA Ultra
![decode](decode.jpg)

The current implementation is able to decode 1 message at a given time of size around 24 bits.

### RTL-SDR
![decode1](rtl-sdr-ads-b.jpg)
![decode2](rtl-sdr-ism.png)

**Two modes available:**

#### 1. Professional Mode (GNSS-SDR Backend) - **RECOMMENDED for GPS**
Uses industry-standard GNSS-SDR software with RTL-SDR dongles:
- ✅ Works with any RTL-SDR dongle (~$25-40)
- ✅ Professional-grade GPS signal processing
- ✅ Real satellite tracking with C/N0 measurements
- ✅ Automatic WebSocket integration
- ✅ **Single-command operation**

📚 **Documentation:** [RTL-SDR GNSS Setup](./gnss-sdr/README_RTLSDR.md)

**Quick Start:**
```bash
# Install GNSS-SDR (one-time setup)
cd gnss-sdr
./install_gnss_sdr.sh

# Start GNSS-SDR with RTL-SDR
./start_gnss_rtlsdr.sh

# Browser:
# 1. Open http://localhost:3005
# 2. Go to SDRPlay Decoder page
# 3. Click "Listen & Decode"
# 4. See satellites in decode table!
```

#### 2. Browser Processing Mode
Direct browser-based signal processing for ADS-B and ISM protocols:
* ADS-B (aircraft tracking)
* ISM GateTX
* Basic GNSS (GPS L1, Galileo E1, GLONASS L1OF, BeiDou B1I)

### SDRPlay

**Two modes available:**

#### 1. Professional Mode (GNSS-SDR Backend) - **RECOMMENDED**
Uses industry-standard GNSS-SDR software for professional-grade signal processing:
- ✅ Accurate C/N0 measurements (dB-Hz)
- ✅ Real positioning (PVT solutions)
- ✅ Better jamming detection
- ✅ Multi-constellation support
- ✅ Battle-tested algorithms
- ✅ **Single-command operation** (auto-starts GNSS-SDR + SDRPlay streamer)

📚 **Documentation:**
- [Complete Setup Guide](./gnss-sdr/GNSS_SDR_COMPLETE_SETUP.md) - **START HERE** for full installation
- [Quick Setup](./gnss-sdr/GNSS_SDR_SETUP.md) - Basic setup guide
- [Troubleshooting](./gnss-sdr/GNSS_SDR_COMPLETE_SETUP.md#-troubleshooting) - Common issues and fixes

**Quick Start:**
```bash
# Install GNSS-SDR (one-time setup, ~30-40 min)
cd gnss-sdr
./install_gnss_sdr.sh

# Terminal 1: Start web UI (from repo root)
npm start
# Opens at http://localhost:3005

# Terminal 2: Run bridge with auto-start (starts GNSS-SDR + SDRPlay streamer!)
cd gnss-sdr
./run_gnss_sdr_bridge.sh

# Browser:
# 1. Go to SDRPlay Decoder page
# 2. Select "Professional Mode (GNSS-SDR)" at the top
# 3. Click "Listen & Decode"
```

**Alternative: File-Based Processing** (works immediately, no web UI needed)
```bash
cd gnss-sdr

# Record 60 seconds of GPS samples
python3 record_iq_samples.py /tmp/gps_iq_samples.dat 60

# Process with GNSS-SDR
gnss-sdr --config_file=gnss_sdr_file.conf

# You should see satellite tracking messages!
```

#### 2. Raw IQ Mode (Browser Processing)
Streams raw IQ samples to browser for JavaScript-based correlation:
- ⚠️ Simplified algorithms
- ⚠️ Limited accuracy
- ⚠️ Higher bandwidth

Setup: Follow [SDRPlay Quickstart](./SDRPLAY_QUICKSTART.md) and [SDRPlay Setup](./SDRPLAY_SETUP.md)

Supported GNSS Constellations:
* GPS L1 C/A (USA)
* Galileo E1 (Europe)
* GLONASS L1OF (Russia)
* BeiDou B1I (China)

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
