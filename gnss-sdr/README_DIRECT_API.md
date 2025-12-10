# SDRplay Direct API Integration - Quick Start

## What's New?

You now have **direct Python access to SDRplay drivers** without needing SoapySDR or gr-osmosdr. This gives you:

✅ **Full control** over all SDRplay features
✅ **No compatibility issues** (bypasses gr-osmosdr setIQBalance crash)
✅ **Better performance** (fewer abstraction layers)
✅ **Access to device-specific features** (bias-T, notch filters, etc.)
✅ **Works with all SDRplay devices** (RSP1, RSP1A, RSP2, RSPduo, RSPdx)

## Quick Test

Verify SDRplay API is working:

```bash
cd /Users/patrykorwat/git/web-spectrum/gnss-sdr
python3 test_sdrplay_api.py
```

Expected output:
```
✓ Successfully loaded library
✓ Successfully opened SDRplay API
✓ SDRplay API Version: 3.15
SUCCESS: SDRplay API is working!
```

## Usage

### Option 1: Direct Streaming (New Method)

Stream directly from SDRplay to file using Python API:

```bash
# Terminal 1 - Start SDRplay streamer
./start_sdrplay_direct.sh

# Terminal 2 - Start GNSS-SDR with the file
python3 gnss_sdr_bridge.py --config gnss_sdr_file.conf --no-sdrplay
```

### Option 2: Existing Method (Still Works)

Use your existing file-based approach:

```bash
./start_all.sh file
```

## Files Overview

| File | Purpose |
|------|---------|
| `test_sdrplay_api.py` | Quick test that SDRplay API works |
| `sdrplay_direct.py` | Python class for direct SDRplay control |
| `sdrplay_streamer.py` | CLI tool to stream SDRplay → file |
| `start_sdrplay_direct.sh` | Wrapper script (easiest to use) |
| `SDRPLAY_DIRECT_API.md` | Complete documentation |

## Advanced Usage

### Custom Parameters

```bash
# Different frequency (e.g., GPS L2)
python3 sdrplay_streamer.py \
    --frequency 1227.60e6 \
    --output /tmp/gps_l2.dat

# Higher gain
python3 sdrplay_streamer.py \
    --gain 20 \
    --output /tmp/gps_high_gain.dat

# Disable bias-T
python3 sdrplay_streamer.py \
    --no-bias-tee \
    --output /tmp/gps.dat

# Record for specific duration
python3 sdrplay_streamer.py \
    --duration 60 \
    --output samples_60s.dat
```

### In Your Code

```python
from sdrplay_direct import SDRplayDevice
import numpy as np

def process_samples(samples):
    """
    samples: numpy array of complex64
    Shape: (num_samples,)
    Range: [-1.0, 1.0]
    """
    print(f"Got {len(samples)} samples")
    # Your processing here...

# Open device and stream
with SDRplayDevice() as sdr:
    sdr.set_frequency(1575.42e6)  # GPS L1
    sdr.set_gain(40)               # dB
    sdr.set_bias_tee(True)         # Active antenna

    sdr.start_streaming(process_samples)

    # Streaming happens in background
    import time
    time.sleep(60)

    sdr.stop_streaming()
# Device auto-closes
```

## Comparison with SoapySDR

### Old Stack (Has Issues)
```
SDRplay → SoapySDR → gr-osmosdr → GNSS-SDR
                          ↑
                   ❌ CRASHES HERE
                   (setIQBalance not supported)
```

### New Stack (Direct API)
```
SDRplay → Python API → File → GNSS-SDR
              ↑
         ✅ FULL CONTROL
         No compatibility issues
```

## Troubleshooting

### "No SDRplay devices found"

1. Check USB connection
2. Verify device appears in system:
   ```bash
   system_profiler SPUSBDataType | grep -A 10 SDRplay
   ```
3. Check if another program is using it:
   ```bash
   ps aux | grep -E "(sdrplay|gnss-sdr|SoapySDR)"
   ```

### "Failed to load SDRplay API library"

1. Verify installation:
   ```bash
   ls -la /usr/local/lib/libsdrplay_api.*
   ```
2. Check service is running:
   ```bash
   ps aux | grep sdrplay_apiService
   ```
3. Restart if needed:
   ```bash
   sudo /Library/SDRplayAPI/3.15.1/bin/sdrplay_apiService restart
   ```

### Low sample rate

- USB2 has limited bandwidth
- Use USB3 port if available
- Try lower sample rate (2 MSPS instead of 10 MSPS)

### No GPS signal

1. **Antenna placement**: Clear sky view required
2. **Bias-T**: Must be enabled for active antennas
3. **Gain**: Try 30-50 dB range
4. **Wait time**: GPS cold start can take 1-2 minutes
5. **Frequency**: Verify 1575.42 MHz for GPS L1

## Next Steps

1. **Test the API**: `python3 test_sdrplay_api.py`
2. **Try streaming**: `./start_sdrplay_direct.sh` (Ctrl+C to stop)
3. **Full integration**: Start streamer + GNSS-SDR bridge
4. **Read docs**: See `SDRPLAY_DIRECT_API.md` for complete reference

## Benefits Summary

| Feature | SoapySDR/gr-osmosdr | Direct API |
|---------|-------------------|------------|
| **Stability** | ❌ Crashes on setIQBalance | ✅ Stable |
| **Control** | ⚠️ Limited | ✅ Full access |
| **Performance** | ⚠️ Multiple layers | ✅ Optimized |
| **Device Features** | ⚠️ Limited | ✅ All features |
| **Debugging** | ❌ Difficult | ✅ Easy |
| **Updates** | ⚠️ Depends on gr-osmosdr | ✅ Direct from SDRplay |

## Documentation

- **Complete API docs**: `SDRPLAY_DIRECT_API.md`
- **Stream failure analysis**: `SDRPLAY_STREAM_FAILURE_ANALYSIS.md`
- **SDRplay API**: https://www.sdrplay.com/docs/
- **GNSS-SDR**: https://gnss-sdr.org/docs/

## Support

If you have issues:

1. Check the troubleshooting section above
2. Review `SDRPLAY_DIRECT_API.md` for detailed info
3. Verify SDRplay API is working: `python3 test_sdrplay_api.py`
4. Check GNSS-SDR configuration files

---

**You now have full, direct access to your SDRplay device from Python! 🚀**
