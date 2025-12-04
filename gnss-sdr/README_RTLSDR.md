# GNSS-SDR with RTL-SDR Support

This directory contains complete support for using RTL-SDR dongles with GNSS-SDR for GPS satellite tracking.

## Quick Start with RTL-SDR

### Requirements
- RTL-SDR dongle (RTL2832U chipset)
- GPS antenna with clear sky view
- librtlsdr installed: `brew install librtlsdr` (macOS) or `apt install rtl-sdr` (Linux)

### Usage

**One command to start everything:**

```bash
cd gnss-sdr
./start_gnss_rtlsdr.sh
```

This script:
1. ✅ Checks for RTL-SDR device
2. ✅ Starts WebSocket bridge on port 8766
3. ✅ Records 5-minute GPS samples continuously
4. ✅ Processes samples with GNSS-SDR
5. ✅ Sends satellite data to web UI in real-time
6. ✅ Loops forever (Ctrl+C to stop)

### What You'll See

**In Terminal:**
- Recording progress (5 minutes)
- GNSS-SDR processing (~1-2 minutes)
- Satellite tracking messages
- "🛰️ Tracking PRN XX on channel Y"

**In Web UI:**
- Navigate to SDRPlay Decoder page
- Click "Listen & Decode"
- Satellite data appears in decode table automatically
- Example: "7 sat(s): 9(14.0dB), 6(11.0dB), 22(12.0dB)..."

### Files

**RTL-SDR Specific:**
- `start_gnss_rtlsdr.sh` - Main startup script for RTL-SDR
- `record_iq_samples_rtlsdr.py` - RTL-SDR IQ sample recorder

**Common Files:**
- `gnss_sdr_file.conf` - GNSS-SDR configuration (works for both RTL-SDR and SDRPlay)
- `gnss_sdr_bridge.py` - WebSocket bridge
- `parse_gnss_logs.py` - Log parser for immediate satellite display

### RTL-SDR vs SDRPlay

**RTL-SDR:**
- ✅ Cheaper (~$25-40)
- ✅ Widely available
- ✅ Good for GPS L1 (1575.42 MHz)
- ⚠️ Sample rate: ~2.8 MSPS max
- ⚠️ 8-bit samples (lower dynamic range)

**SDRPlay:**
- ✅ Higher sample rate (10+ MSPS)
- ✅ 12-14 bit samples (better dynamic range)
- ✅ Dual tuner support (RSPduo)
- ⚠️ More expensive (~$100-300)

**For GPS tracking, both work great!** RTL-SDR is perfect for getting started.

## Technical Details

### RTL-SDR Settings
- **Frequency:** 1575.42 MHz (GPS L1)
- **Sample Rate:** 2.048 MSPS
- **Gain:** 40 dB (manual)
- **Bias-Tee:** Enabled if supported (for active GPS antennas)

### Recording
- **Duration:** 5 minutes per cycle
- **File:** `/tmp/gps_iq_samples.dat`
- **Format:** Complex64 (gr_complex)
- **Size:** ~4.9 GB per 5-minute recording

### Processing
- **GNSS-SDR:** Professional-grade GPS signal processing
- **Channels:** 12 (can track up to 12 satellites simultaneously)
- **Acquisition:** ~30-60 seconds
- **Ephemeris:** 30+ seconds to decode
- **Position Fix:** 4+ satellites + ephemeris data

## Troubleshooting

### "No RTL-SDR devices found"
```bash
# Check if RTL-SDR is detected
rtl_test

# Install if missing
brew install librtlsdr  # macOS
apt install rtl-sdr     # Linux
```

### "No satellites tracked"
1. ✅ GPS antenna has **clear sky view** (no roof, no buildings)
2. ✅ Wait 5-10 minutes for first fix (GPS needs time)
3. ✅ Active GPS antenna needs bias-tee power
4. ✅ Check antenna connection

### "Recording failed"
- RTL-SDR might be in use by another program
- Kill other SDR programs: `killall rtl_sdr rtl_tcp`
- Unplug and replug RTL-SDR

## Advanced Usage

### Adjust Gain
Edit `record_iq_samples_rtlsdr.py` line 70:
```python
sdr.setGain(SOAPY_SDR_RX, 0, 40)  # Change 40 to desired dB
```

### Change Recording Duration
Edit `start_gnss_rtlsdr.sh` line 136:
```bash
python3 record_iq_samples_rtlsdr.py /tmp/gps_iq_samples.dat 300  # 300 = seconds
```

### Continuous Recording
```bash
python3 record_iq_samples_rtlsdr.py /tmp/gps.dat --continuous
```

## Comparison with SDRPlay

To use SDRPlay instead:
```bash
./start_gnss.sh  # Uses start_gnss.sh (not start_gnss_rtlsdr.sh)
```

Both scripts use the same web UI and produce identical results!

## Support

For issues or questions:
- Check GNSS-SDR logs: `/tmp/gnss_sdr_output.log`
- Check system logs: `/tmp/gnss_system.log`
- Verify RTL-SDR: `rtl_test`

## License

This software uses GNSS-SDR which is licensed under GPL v3.
