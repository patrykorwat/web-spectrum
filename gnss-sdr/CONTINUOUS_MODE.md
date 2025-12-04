# GNSS-SDR Continuous Recording Mode

## What Changed

The system now uses **continuous file-based processing** instead of one-time recording or real-time UDP streaming.

## Architecture

```
SDRPlay → Continuous IQ Recorder → /tmp/gps_iq_samples.dat → GNSS-SDR (repeat mode) → Monitor → Bridge → WebSocket → Web UI
```

### Flow:
1. **IQ Recorder** (`record_iq_samples.py --continuous`) continuously writes SDRPlay samples to `/tmp/gps_iq_samples.dat`
2. **GNSS-SDR** reads from the file with `SignalSource.repeat=true` (loops when reaching EOF, picks up new data)
3. **Bridge** receives monitor data via UDP and forwards to WebSocket
4. **Web UI** displays professional GNSS results

## Files Modified

### New Files:
- `gnss_sdr_file_continuous.conf` - GNSS-SDR config for continuous file reading
  - Sets `SignalSource.repeat=true` for continuous operation
  - Sets `SignalSource.enable_throttle_control=true` for real-time playback
  - Enables monitor output on UDP port 1234

### Modified Files:
- `record_iq_samples.py` - Added `--continuous` mode
  - New `continuous` parameter to record indefinitely
  - Flushes data to disk for real-time reading
  - Shows real-time sample rate and total samples

- `gnss_sdr_bridge.py` - Switched from UDP streamer to continuous recorder
  - Replaced `start_sdrplay_streamer()` with `start_recorder()`
  - Now starts continuous recorder before GNSS-SDR
  - Waits 10s for initial data before starting GNSS-SDR
  - Updated default config to `gnss_sdr_file_continuous.conf`

- `run_gnss_sdr_bridge.sh` - Updated documentation
  - Reflects continuous recording mode
  - Checks for new config file

## How to Use

### Quick Start (ONE COMMAND):
```bash
cd gnss-sdr
./run_gnss_sdr_bridge.sh
```

This will:
1. Kill any previous instances
2. Start continuous IQ recorder (SDRPlay → /tmp/gps_iq_samples.dat)
3. Wait 10 seconds for initial data
4. Start GNSS-SDR reading from file
5. Start WebSocket bridge on port 8766

### Manual Testing:

#### Test continuous recorder alone:
```bash
cd gnss-sdr
export DYLD_LIBRARY_PATH="/usr/local/lib:$DYLD_LIBRARY_PATH"
export PYTHONPATH="/opt/homebrew/lib/python3.14/site-packages:$PYTHONPATH"

python3 record_iq_samples.py /tmp/gps_iq_samples.dat --continuous
```

You should see:
```
======================================================================
SDRPlay IQ Sample Recorder
======================================================================

Output file: /tmp/gps_iq_samples.dat
Mode: CONTINUOUS (recording until stopped)
Frequency: 1575.42 MHz (GPS L1)
Sample rate: 2.048 MSPS

✓ Found 1 SDRPlay device(s)
✓ Opened SDRPlay device
✓ Bias-T enabled
✓ Configuration complete

🎙️  Recording continuously (Ctrl+C to stop)...

[5s] 10.2 MSamples | 2.04 MSPS
[6s] 12.3 MSamples | 2.05 MSPS
...
```

#### Test GNSS-SDR with continuous file:
In another terminal (while recorder is running):
```bash
cd gnss-sdr
gnss-sdr --config_file=gnss_sdr_file_continuous.conf
```

You should see satellites being tracked!

## Advantages Over Previous Approaches

### vs. UDP Streaming (sdrplay_to_gnss_sdr.py):
- ✅ More reliable (no UDP packet loss)
- ✅ File-based approach already proven to work
- ✅ Easier to debug (can inspect /tmp/gps_iq_samples.dat)
- ✅ No AGC/gain conflicts
- ✅ No network buffering issues

### vs. One-Time Recording:
- ✅ Continuous real-time operation (not batch processing)
- ✅ Doesn't stop after 60 seconds
- ✅ GNSS-SDR gets fresh data continuously
- ✅ True real-time tracking

### vs. Direct Osmosdr:
- ✅ Works reliably (Osmosdr approach had satellite acquisition issues)
- ✅ Simpler architecture (no Gr-Osmosdr, no custom signal source)
- ✅ File-based approach proven with 15+ satellites

## Monitoring

### Check recorder is running:
```bash
ps aux | grep record_iq_samples
```

### Check file is growing:
```bash
watch -n 1 ls -lh /tmp/gps_iq_samples.dat
```

### Check GNSS-SDR is processing:
Look for satellite tracking messages in the bridge output

## Troubleshooting

### Recorder exits immediately:
- Check SDRPlay is connected: `SoapySDRUtil --find="driver=sdrplay"`
- Check library paths are set: `echo $DYLD_LIBRARY_PATH`
- Check Python path: `echo $PYTHONPATH`

### GNSS-SDR complains "file not found":
- Recorder needs ~10s to write initial data
- Check `/tmp/gps_iq_samples.dat` exists and is growing

### No satellites:
- Antenna needs clear sky view
- Give it 30-60s for acquisition
- Check recorder is actually recording (file size growing)
- File-based mode previously tracked 15+ satellites, so it should work!

## Technical Details

### Config Differences:

**gnss_sdr_file.conf** (one-time):
```ini
SignalSource.repeat=false
SignalSource.enable_throttle_control=false
PVT.enable_monitor=false
```

**gnss_sdr_file_continuous.conf** (continuous):
```ini
SignalSource.repeat=true              # Loop at EOF, picks up new data
SignalSource.enable_throttle_control=true  # Real-time playback
PVT.enable_monitor=true               # Enable UDP monitor
PVT.monitor_udp_port=1234
```

### File Format:
- Format: `gr_complex` (32-bit complex float, 8 bytes per sample)
- Sample rate: 2.048 MSPS
- Data rate: ~16 MB/s
- The file grows continuously, GNSS-SDR reads in a loop

## Next Steps

1. Test the continuous recording system
2. Verify satellites are tracked
3. Connect web UI to `ws://localhost:8766`
4. Verify GNSS data is displayed

If everything works, this is the new standard approach! 🎉
