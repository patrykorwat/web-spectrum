# SDRPlay RSPdx Bridge Setup

This guide explains how to use your SDRPlay RSPdx with web-spectrum for GPS/GNSS signal analysis.

## Why SDRPlay RSPdx?

The SDRPlay RSPdx is superior to RTL-SDR for GPS reception:
- **Better Dynamic Range**: 14-bit ADC vs 8-bit (RTL-SDR)
- **Lower Noise Figure**: Better sensitivity for weak GPS signals
- **Wider Frequency Coverage**: DC to 2 GHz
- **Better Filtering**: Sharp tunable filters reduce interference
- **Multiple Antenna Ports**: Antenna A, B, C with different frequency ranges

## Prerequisites

### 1. Install SDRPlay API

Download and install from: https://www.sdrplay.com/downloads/

**macOS:**
```bash
# Download the macOS installer from SDRPlay website
# Install the .pkg file
# Restart your computer
```

**Linux:**
```bash
# Download the Linux installer
chmod +x SDRplay_RSP_API-Linux-3.x.x.run
sudo ./SDRplay_RSP_API-Linux-3.x.x.run
```

**Windows:**
```bash
# Download and run the Windows installer
# Follow the installation wizard
```

### 2. Install SoapySDR with SDRPlay Support

**macOS (Homebrew):**
```bash
brew install soapysdr
brew install soapySDRplay3
```

**Linux:**
```bash
sudo apt-get install soapysdr-tools
sudo apt-get install soapysdr-module-sdrplay3
```

**Windows:**
Download from: https://github.com/pothosware/SoapySDR/wiki

### 3. Verify Installation

```bash
# List available SoapySDR modules
SoapySDRUtil --info

# Should show sdrPlaySupport module

# Find your SDRPlay device
SoapySDRUtil --find

# Should show your RSPdx
```

### 4. Install Python Dependencies

```bash
# Create virtual environment (recommended)
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install requirements
pip install -r requirements.txt
```

## Usage

### 1. Start the SDRPlay Bridge

**GPS L1 (1575.42 MHz):**
```bash
python sdrplay_bridge.py --freq 1575.42e6 --rate 2.048e6 --gain 40
```

**GPS L2 (1227.60 MHz):**
```bash
python sdrplay_bridge.py --freq 1227.60e6 --rate 2.048e6 --gain 40
```

**Galileo E1 (1575.42 MHz):**
```bash
python sdrplay_bridge.py --freq 1575.42e6 --rate 2.048e6 --gain 40
```

**GLONASS L1 (1602.0 MHz):**
```bash
python sdrplay_bridge.py --freq 1602.0e6 --rate 2.048e6 --gain 40
```

**Custom settings:**
```bash
python sdrplay_bridge.py --freq <frequency> --rate <sample_rate> --gain <gain> --port <ws_port>
```

### 2. Connect Web-Spectrum

The bridge creates a WebSocket server on port 8765 (default). You'll need to modify web-spectrum to connect to this WebSocket instead of USB.

**Output:**
```
============================================================
SDRPlay RSPdx to Web-Spectrum Bridge
============================================================
Searching for SDRPlay devices...
Found 1 device(s):
  [0] driver=sdrplay, label=RSPdx, serial=...

Opened: RSPdx

Configuring device:
  Frequency: 1575.42 MHz
  Sample Rate: 2.048 MSPS
  Gain: 40 dB
  Actual Sample Rate: 2.048 MSPS
  Actual Frequency: 1575.420000 MHz
  Actual Gain: 40 dB
  Available antennas: ['Antenna A', 'Antenna B', 'Antenna C']
  Using: Antenna A

SDRPlay configured successfully!
Streaming started!

Starting WebSocket server on port 8765...
Connect web-spectrum to: ws://localhost:8765

Press Ctrl+C to stop

[12:34:56] Streaming: 32.77 Mbps, 1 client(s)
```

## Antenna Selection for GPS

The RSPdx has three antenna ports optimized for different frequency ranges:

- **Antenna A (HDR Port)**: DC - 2 GHz (Best for GPS L1, L2, Galileo)
- **Antenna B**: 50 kHz - 250 MHz (Not suitable for GPS)
- **Antenna C**: 420 MHz - 1 GHz (Not suitable for GPS)

**For GPS/GNSS, always use Antenna A port!**

## Optimal Settings for GPS

### GPS L1 C/A (1575.42 MHz)
```bash
python sdrplay_bridge.py \
  --freq 1575.42e6 \
  --rate 2.048e6 \
  --gain 40
```

**Gain Recommendations:**
- **Outdoor with active antenna**: 30-40 dB
- **Indoor with active antenna**: 40-50 dB
- **Passive antenna**: Not recommended for GPS (signal too weak)

### Bias-T for Active GPS Antennas

If you have an active GPS antenna, you need to enable bias-T to power it:

**SDRPlay doesn't expose bias-T via SoapySDR, you need to use:**

1. **SDRuno** (Windows) - Enable bias-T in settings
2. **CubicSDR** - May have bias-T option
3. **Manual control** - Use SDRplay API directly

**For best results with GPS:**
- Use a quality active GPS antenna with LNA
- Enable bias-T to power the antenna
- Place antenna outdoors with clear sky view
- Use gain around 40 dB
- Monitor J/S ratio in web-spectrum

## Troubleshooting

### "No SDRPlay devices found"
- Make sure RSPdx is connected
- Restart the SDRPlay service: `sudo systemctl restart sdrplay`
- Check USB connection
- Verify API is installed: `SoapySDRUtil --find`

### "Module not found: SoapySDR"
```bash
pip install soapy_sdr
```

### "No module named websockets"
```bash
pip install websockets
```

### Low GPS signal
- Increase gain: `--gain 50`
- Use active antenna with bias-T enabled
- Move antenna outdoors
- Check antenna has clear sky view (no buildings/trees)

### High J/S ratio (>40 dB)
- Reduce gain to avoid saturation
- Move away from interference sources (WiFi, electronics)
- Use notch filter if CW tone jamming detected

## Performance Comparison

| Feature | RTL-SDR | SDRPlay RSPdx |
|---------|---------|---------------|
| ADC Resolution | 8-bit | 14-bit |
| Noise Figure | ~4.5 dB | ~3 dB |
| Dynamic Range | ~45 dB | ~85 dB |
| GPS Sensitivity | Poor | Excellent |
| Price | ~$30 | ~$300 |

For serious GPS/GNSS work, the RSPdx is worth the investment!

## Web-Spectrum Integration

To use this bridge with web-spectrum, you'll need to add WebSocket support to the app. The bridge streams data in RTL-SDR compatible format (interleaved IQ uint8).

**Next steps:**
1. Add WebSocket receiver to web-spectrum
2. Select "WebSocket" as input source
3. Connect to `ws://localhost:8765`
4. Samples will stream automatically

The bridge converts RSPdx's high-quality 14-bit samples to 8-bit RTL-SDR format for compatibility.
