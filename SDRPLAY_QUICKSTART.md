# SDRPlay Quick Start Guide

## 🎯 Goal
Use your SDRPlay device (RSPdx, RSPduo, RSP1A, etc.) with web-spectrum for superior GPS/GNSS signal analysis compared to RTL-SDR.

## 📋 Prerequisites
- SDRPlay device connected via USB (RSPdx, RSPduo, RSP1A, etc.)
- SDRPlay API installed (download from https://www.sdrplay.com/downloads/)
- Python 3.7+ installed
- Web-spectrum running

## ⚡ Quick Start (5 steps)

### 1. Run the Automated Installer
```bash
cd /path/to/web-spectrum
./install_sdrplay_macos.sh
```

This will:
- Install SoapySDR and SDRPlay support via Homebrew
- Create a Python virtual environment (`venv/`)
- Install all Python dependencies

**Or manually:**
```bash
# Create virtual environment
python3 -m venv venv

# Activate it
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Start the SDRPlay Bridge
```bash
# Activate virtual environment (if not already active)
source venv/bin/activate

# For GPS L1 (most common)
python sdrplay_bridge.py --freq 1575.42e6 --rate 2.048e6 --gain 40
```

**Output you should see:**
```
============================================================
SDRPlay RSPdx to Web-Spectrum Bridge
============================================================
Searching for SDRPlay devices...
Found 1 device(s):
  [0] driver=sdrplay, label=RSPdx, serial=...

Configuring device:
  Frequency: 1575.42 MHz
  Sample Rate: 2.048 MSPS
  Gain: 40 dB

SDRPlay configured successfully!
Streaming started!

Starting WebSocket server on port 8765...
Connect web-spectrum to: ws://localhost:8765
```

### 3. Open Web-Spectrum
Navigate to: http://localhost:3005

### 4. Configure Web-Spectrum

1. **Input Source**: Select `WebSocket (SDRPlay/Remote)` from dropdown
2. **WebSocket URL**: Should show `ws://localhost:8765` (default)
3. **Protocol**: Select `GPS L1 C/A (USA)` or your desired GNSS constellation
4. Click **Listen&Decode**

### 5. Monitor GPS Signals

You should now see:
```
⚠️ JAMMING: BROADBAND_NOISE (J/S: 23.0dB) | 3 sat(s): 7(4.2dB), 11(3.8dB), 23(5.1dB)
```

**What this means:**
- **J/S 23.0dB**: Realistic jamming-to-signal ratio ✅
- **3 sat(s)**: 3 GPS satellites detected
- **PRN 7, 11, 23**: Satellite identifiers with SNR values

## 🎛️ Configuration Options

### GPS L1 (Most Common)
```bash
# RSPdx or RSPduo Tuner 1
python sdrplay_bridge.py --freq 1575.42e6 --rate 2.048e6 --gain 40

# RSPduo Tuner 2 (for dual independent receiver setups)
python sdrplay_bridge.py --freq 1575.42e6 --rate 2.048e6 --gain 40 --tuner 2
```

### GPS L1 with Active Antenna (RSPduo Only)
```bash
# Enable T-bias on Tuner 2 for active antenna power
python sdrplay_bridge.py --freq 1575.42e6 --rate 2.048e6 --gain 40 --tuner 2 --bias-tee
```
**Note:** T-bias provides ~4.5V power to active GPS antennas and is only available on RSPduo Tuner 2.

### GPS L2
```bash
python sdrplay_bridge.py --freq 1227.60e6 --rate 2.048e6 --gain 40
```

### Galileo E1
```bash
python sdrplay_bridge.py --freq 1575.42e6 --rate 2.048e6 --gain 40
```
Then select "Galileo E1 (Europe)" in web-spectrum.

### GLONASS L1
```bash
python sdrplay_bridge.py --freq 1602.0e6 --rate 2.048e6 --gain 40
```
Then select "GLONASS L1OF (Russia)" in web-spectrum.

## 🔌 RSPduo-Specific Features

### Tuner Selection
The RSPduo has two independent tuners. You can select which one to use:
```bash
# Use Tuner 1 (default)
python sdrplay_bridge.py --tuner 1 ...

# Use Tuner 2
python sdrplay_bridge.py --tuner 2 ...
```

### T-bias for Active Antennas
RSPduo's Tuner 2 can provide power to active antennas via T-bias:
```bash
# Enable T-bias on Tuner 2
python sdrplay_bridge.py --tuner 2 --bias-tee ...
```

**Important:**
- T-bias is ONLY available on Tuner 2
- T-bias provides ~4.5V DC power through the antenna connector
- Only use with active antennas designed for T-bias power
- DO NOT use T-bias with passive antennas (may damage equipment)

In the web interface, you'll see:
- **RSPduo Tuner Selection**: Dropdown to choose Tuner 1 or Tuner 2
- **T-bias toggle**: Checkbox to enable T-bias (shows warning if not using Tuner 2)

## 🔧 Troubleshooting

### "ERROR: No SDRPlay devices found!"
**Solution:**
1. Check USB connection
2. Verify SDRPlay API is installed: `SoapySDRUtil --find`
3. On Linux, restart SDRPlay service: `sudo systemctl restart sdrplay`

### "Failed to connect to WebSocket server"
**Solution:**
1. Make sure `sdrplay_bridge.py` is running
2. Check the terminal shows: `Starting WebSocket server on port 8765...`
3. Verify firewall isn't blocking port 8765

### "No satellites acquired"
**Solution:**
1. **Use an active GPS antenna** (passive won't work indoors)
2. **Move antenna outdoors** with clear sky view
3. **Increase gain**: Try `--gain 50` or `--gain 60`
4. **Wait 2-3 minutes** for satellite acquisition
5. **Check antenna has power**:
   - For RSPduo Tuner 2: Enable T-bias with `--bias-tee` flag
   - For other devices: Use external power injector or LNA

### Low SNR / Weak Signals
**Solution:**
1. Increase gain: `--gain 50`
2. Use Antenna A port (RSPdx) or Tuner 2 (RSPduo) - optimized for GPS frequencies
3. Ensure active antenna is powered:
   - RSPduo: Use `--tuner 2 --bias-tee`
   - RSPdx/others: Use external power injector
4. Move antenna to rooftop or window with sky view
5. Avoid interference from WiFi, Bluetooth, etc.

## 📊 Understanding the Output

### J/S (Jamming-to-Signal) Ratio
- **0-10 dB**: Excellent - Clean GPS signal
- **10-20 dB**: Good - Light interference
- **20-30 dB**: Fair - Moderate noise (typical indoors)
- **30-40 dB**: Poor - Heavy jamming
- **>40 dB**: Severe - GPS likely unusable

### SNR (Signal-to-Noise Ratio)
- **>6 dB**: Strong satellite signal
- **3-6 dB**: Acceptable signal
- **<3 dB**: Weak signal (may lose tracking)

### Jamming Types
- **BROADBAND_NOISE**: Normal background RF noise
- **CW_TONE**: Single-frequency jammer (frequency shown)
- **PULSED**: Intermittent high-power interference
- **SWEPT_CW**: Frequency-hopping jammer

## 🎥 For YouTube Video

Perfect settings for demonstration:
```bash
python sdrplay_bridge.py --freq 1575.42e6 --rate 2.048e6 --gain 45
```

**What to show:**
1. J/S ratio (now realistic 20-30 dB, not fake 111.9 dB!)
2. Satellite PRNs being detected
3. SNR values for each satellite
4. How jamming type changes (BROADBAND_NOISE vs CW_TONE)
5. Compare RTL-SDR vs SDRPlay (RSPdx should show more satellites)

**Talking points:**
- SDRPlay RSPdx has 14-bit ADC vs RTL-SDR's 8-bit
- Better dynamic range = more satellites detected
- Lower noise figure = better weak signal performance
- Fixed J/S calculation now shows realistic values

## 🎯 Next Steps

1. Try different GNSS constellations (Galileo, GLONASS, BeiDou)
2. Compare performance: RTL-SDR vs SDRPlay
3. Test in different locations (outdoor, indoor, urban canyon)
4. Monitor jamming in different RF environments
5. Create your YouTube content! 📹

## 💡 Pro Tips

1. **RSPdx**: Use Antenna A port - It's optimized for 1-2 GHz (GPS range)
2. **RSPduo**: Use Tuner 2 with T-bias for active antennas (easiest setup!)
3. **Start with gain=40** - Adjust up if signals weak, down if saturated
4. **Wait for buffer to fill** - First results appear after ~15 seconds
5. **Check console logs** - Shows satellite acquisition progress
6. **Compare with TinySA** - Verify signal levels match your measurements
7. **T-bias safety**: Only use with active antennas, never with passive ones!

---

Need help? Check the detailed setup guide in [SDRPLAY_SETUP.md](SDRPLAY_SETUP.md)
