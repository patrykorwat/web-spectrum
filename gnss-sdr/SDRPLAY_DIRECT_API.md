# Direct SDRplay API Access from Python

## Overview

This directory contains Python modules for **direct access** to SDRplay drivers, bypassing SoapySDR and gr-osmosdr entirely. This gives you full control over the SDRplay device and data stream without compatibility issues.

## Why Direct API Access?

### Problems with SoapySDR/gr-osmosdr Approach

Current stack: `SDRplay → SoapySDR → gr-osmosdr → GNSS-SDR`

**Issues:**
- gr-osmosdr calls `setIQBalance()` which SoapySDRPlay doesn't implement
- Causes GNSS-SDR to crash after 2 seconds
- Limited control over device-specific features
- Extra abstraction layers reduce performance
- Difficult to debug when problems occur

See [SDRPLAY_STREAM_FAILURE_ANALYSIS.md](./SDRPLAY_STREAM_FAILURE_ANALYSIS.md) for details.

### Benefits of Direct API

New stack: `SDRplay API → Python → GNSS-SDR`

**Benefits:**
✓ Full control over all SDRplay features
✓ No compatibility layer issues
✓ Better performance (fewer abstractions)
✓ Access to device-specific features (bias-T, notch filters, etc.)
✓ Better error handling and diagnostics
✓ Can implement custom signal processing
✓ Works with all SDRplay devices (RSP1, RSP1A, RSP2, RSPduo, RSPdx)

## Architecture

```
┌─────────────┐
│  SDRplay    │ (Physical device via USB)
│   Device    │
└──────┬──────┘
       │
       │ USB
       │
┌──────▼──────────────┐
│  libsdrplay_api.so  │ (C library from SDRplay)
│   Version 3.15      │
└──────┬──────────────┘
       │
       │ ctypes
       │
┌──────▼───────────────┐
│ sdrplay_streamer.py  │ (Direct Python bindings)
│   - Device control   │
│   - Stream callback  │
│   - IQ data capture  │
└──────┬───────────────┘
       │
       │ File/FIFO
       │
┌──────▼──────────┐
│   GNSS-SDR      │ (File_Signal_Source)
│   Processing    │
└─────────────────┘
```

## Files

### 1. `test_sdrplay_api.py`
Quick verification that SDRplay API is accessible.

```bash
python3 test_sdrplay_api.py
```

**Output:**
```
✓ Successfully loaded library
✓ Successfully opened SDRplay API
✓ SDRplay API Version: 3.15
✓ Closed SDRplay API
SUCCESS: SDRplay API is working!
```

### 2. `sdrplay_direct.py`
Complete Python class for direct SDRplay control with high-level API.

**Features:**
- Pythonic interface to SDRplay API
- All device types supported
- Streaming via callbacks
- Context manager support
- Type hints and documentation

**Example:**
```python
from sdrplay_direct import SDRplayDevice

def data_callback(samples):
    # samples is numpy array of complex64
    print(f"Received {len(samples)} samples")
    # Process samples here...

with SDRplayDevice() as sdr:
    sdr.set_frequency(1575.42e6)  # GPS L1
    sdr.set_sample_rate(2.048e6)
    sdr.set_gain(40)
    sdr.start_streaming(data_callback)
    time.sleep(60)
```

### 3. `sdrplay_streamer.py` ⭐ **Main Tool**
Command-line tool to stream SDRplay data to file for GNSS-SDR processing.

**Features:**
- Stream directly to file (continuous or fixed duration)
- Full control over all parameters
- Real-time statistics
- Optimized buffering for GNSS-SDR
- Graceful shutdown (Ctrl+C)

**Usage:**
```bash
# Stream continuously to file (for GNSS-SDR)
python3 sdrplay_streamer.py --output /tmp/gps_iq_samples.dat

# Stream for 60 seconds
python3 sdrplay_streamer.py --output samples.dat --duration 60

# Custom frequency and gain
python3 sdrplay_streamer.py \
    --output /tmp/gps.dat \
    --frequency 1575.42e6 \
    --sample-rate 2.048e6 \
    --gain 30 \
    --bandwidth 1536

# Disable bias-T
python3 sdrplay_streamer.py --no-bias-tee
```

## Integration with GNSS-SDR

### Method 1: Continuous File Mode (Recommended)

This is the most reliable method that's currently working in your setup.

**Terminal 1 - Start SDRplay streamer:**
```bash
cd gnss-sdr
python3 sdrplay_streamer.py --output /tmp/gps_iq_samples.dat
```

**Terminal 2 - Start GNSS-SDR:**
```bash
cd gnss-sdr
gnss-sdr --config_file=gnss_sdr_file.conf
```

**Or use the integrated bridge:**
```bash
cd gnss-sdr
python3 gnss_sdr_bridge.py --config gnss_sdr_file.conf
```

### Method 2: FIFO Mode (Lower Latency)

Uses a named pipe for real-time streaming.

**Setup FIFO:**
```bash
mkfifo /tmp/gps_fifo
```

**Terminal 1 - Start streamer:**
```bash
python3 sdrplay_streamer.py --output /tmp/gps_fifo
```

**Terminal 2 - Start GNSS-SDR:**
```bash
gnss-sdr --config_file=gnss_sdr_fifo.conf
```

### Method 3: Direct Integration (Future)

Modify `gnss_sdr_bridge.py` to use `sdrplay_direct.py` instead of subprocess recording.

Benefits:
- Single process
- No file I/O overhead
- Real-time processing
- Better resource usage

## Configuration

### SDRplay API Settings

The direct API gives you access to all SDRplay-specific features:

**Frequency:**
- Range: Device-dependent (typically 1 kHz - 2 GHz)
- GPS L1: 1575.42 MHz
- GPS L2: 1227.60 MHz
- Galileo E1: 1575.42 MHz

**Sample Rate:**
- Native rates: 2 MHz, 6 MHz, 8 MHz, 10 MHz
- Use decimation for other rates
- Recommended for GPS: 2.048 MSPS

**Gain Control:**
- Gain Reduction: 0-59 dB (lower = more gain)
- LNA states: 0-9 (device-dependent)
- AGC: Can be enabled for automatic gain control
- Typical for GPS: 40-50 dB gain reduction (10-20 dB gain)

**Bandwidth:**
- Options: 200, 300, 600, 1536, 5000, 6000, 7000, 8000 kHz
- Recommended for GPS: 1536 kHz or 5000 kHz

**IF Mode:**
- Zero-IF (default, recommended)
- 450 kHz IF
- 1620 kHz IF
- 2048 kHz IF

**Bias-T:**
- Enables DC power on antenna port (3.3V typical)
- Required for active GPS antennas
- Not available on all devices/ports
- Check device manual before enabling

**Device-Specific Features:**
- RSP2: Antenna selection, RF notch, AM notch
- RSPduo: Dual tuner mode, master/slave
- RSPdx: HDR mode, antenna selection, RF/DAB notches

## Troubleshooting

### API Won't Load

```
Error: Failed to load SDRplay API library
```

**Solution:**
1. Install SDRplay API from https://www.sdrplay.com/downloads/
2. Check library path: `ls -la /usr/local/lib/libsdrplay_api.*`
3. Verify service is running: `ps aux | grep sdrplay`
4. Restart service: `sudo /Library/SDRplayAPI/3.15.1/bin/sdrplay_apiService restart`

### No Devices Found

```
Error: No SDRplay devices found
```

**Solution:**
1. Check USB connection
2. Verify device is detected: `system_profiler SPUSBDataType | grep -A 10 SDRplay`
3. Check if another program is using it: `ps aux | grep -i sdr`
4. Try: `SoapySDRUtil --find="driver=sdrplay"` (if SoapySDR is installed)

### Device In Use

```
Error: Failed to select device: error 1
```

**Solution:**
1. Stop other programs using SDRplay
2. Kill any stuck processes: `pkill -9 gnss-sdr`
3. Restart SDRplay service

### Low Sample Rate

```
Warning: Actual rate lower than expected
```

**Solution:**
1. USB2 has lower bandwidth than USB3
2. Try lower sample rate (2 MSPS instead of 10 MSPS)
3. Check system load (reduce other processes)
4. Increase buffer sizes in code

### No GPS Signal

```
GNSS-SDR: No satellites acquired
```

**Solution:**
1. Check antenna has clear sky view
2. Verify bias-T is enabled (if using active antenna)
3. Check gain settings (try 30-50 dB)
4. Verify frequency is correct (1575.42 MHz for GPS L1)
5. Wait 1-2 minutes for cold start acquisition

## Performance Optimization

### For Maximum Throughput:

1. **Use Zero-IF mode** (least processing overhead)
2. **Increase buffer sizes** (in `sdrplay_streamer.py`)
3. **Use USB 3.0** connection
4. **Disable DC offset** and IQ balance corrections
5. **Use continuous file mode** with large buffer
6. **Monitor CPU usage** (should be <50% per core)

### For Best Signal Quality:

1. **Enable DC offset correction**
2. **Enable IQ balance correction**
3. **Use appropriate bandwidth** (1536 or 5000 kHz for GPS)
4. **Optimize gain** (maximize SNR without saturation)
5. **Enable notch filters** if interference present
6. **Use high-quality antenna** with clear sky view

## Next Steps

1. **Test the streamer:**
   ```bash
   python3 test_sdrplay_api.py
   python3 sdrplay_streamer.py --duration 10 --output /tmp/test.dat
   ```

2. **Integrate with GNSS-SDR:**
   ```bash
   # Terminal 1:
   python3 sdrplay_streamer.py --output /tmp/gps_iq_samples.dat

   # Terminal 2:
   python3 gnss_sdr_bridge.py --config gnss_sdr_file.conf --no-sdrplay
   ```

3. **Monitor performance:**
   - Check sample rate is stable (should be ~2.048 MSPS)
   - Monitor file size growth (~16 MB/sec for 2.048 MSPS)
   - Watch GNSS-SDR logs for satellite acquisition
   - Check CPU usage (should be moderate)

4. **Optimize for your use case:**
   - Adjust gain for best SNR
   - Try different bandwidth settings
   - Test FIFO mode for lower latency
   - Implement custom processing in callback

## API Reference

See `sdrplay_direct.py` for complete API documentation.

**Main Class: `SDRplayDevice`**

Methods:
- `__init__(serial_number=None)` - Open device
- `set_frequency(freq_hz)` - Set center frequency
- `set_sample_rate(rate_hz)` - Set sample rate
- `set_gain(gain_db)` - Set gain
- `set_bias_tee(enable)` - Enable/disable bias-T
- `start_streaming(callback)` - Start with callback
- `stop_streaming()` - Stop streaming
- `close()` - Cleanup

**Callback Signature:**
```python
def callback(samples: np.ndarray):
    # samples is complex64 numpy array
    # normalized to [-1.0, 1.0]
    pass
```

## Support

For SDRplay API documentation:
- https://www.sdrplay.com/docs/
- `/Library/SDRplayAPI/3.15.1/include/sdrplay_api.h`

For GNSS-SDR:
- https://gnss-sdr.org/docs/
- Check other .md files in this directory

## License

These Python bindings are provided as-is for interfacing with the SDRplay API.
The SDRplay API itself is proprietary software from SDRplay Ltd.
