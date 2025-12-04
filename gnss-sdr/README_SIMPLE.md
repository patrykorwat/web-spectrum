# GNSS-SDR Simple Start Guide

## ✅ Proven Working Approach

This is the **simplest and most reliable** way to use GNSS-SDR with your SDRPlay.

## Quick Start (ONE COMMAND!)

```bash
cd gnss-sdr
./simple_start.sh
```

That's it! The script will:
1. ✅ Check SDRPlay connection
2. ✅ Record 2 minutes of GPS IQ samples to `/tmp/gps_iq_samples.dat`
3. ✅ Automatically start GNSS-SDR + WebSocket bridge
4. ✅ Forward satellite data to web UI on `ws://localhost:8766`

## What You'll See

### Step 1: Recording (2 minutes)
```
========================================================================
Step 1: Recording IQ Samples
========================================================================

⚠️  IMPORTANT: Make sure your GPS antenna has a CLEAR SKY VIEW!

Recording 2 minutes of GPS L1 samples...
Output: /tmp/gps_iq_samples.dat

[10s / 120s] 8% complete | 20.5 MSamples
[20s / 120s] 17% complete | 41.0 MSamples
...
```

**IMPORTANT**: During recording, make sure:
- Antenna is outside or near a window
- Clear view of the sky (no obstructions)
- Bias-T is enabled (antenna gets power from SDRPlay)

### Step 2: Processing
```
========================================================================
Step 2: Starting GNSS-SDR + Bridge
========================================================================

Starting bridge with file-based processing...
This will:
  1. Start GNSS-SDR to process the recorded file
  2. Start WebSocket bridge on port 8766
  3. Forward satellite data to your web UI

Connect your browser to: ws://localhost:8766
```

GNSS-SDR will start acquiring satellites. You should see:
```
Tracking of GPS L1 C/A signal started on channel 0 for satellite GPS PRN 16
Tracking of GPS L1 C/A signal started on channel 1 for satellite GPS PRN 26
Tracking of GPS L1 C/A signal started on channel 2 for satellite GPS PRN 17
...
```

Once **4+ satellites** are tracked with decoded ephemeris data, the bridge will start receiving monitor data and forward it to your web UI!

## Web UI Connection

1. Open your browser to your web-spectrum UI
2. **It already defaults to SDRPlay/GNSS-SDR decoder** ✅ (just updated)
3. It will auto-connect to `ws://localhost:8766`
4. You'll see satellite data appear!

## Troubleshooting

### No satellites acquired
- **Antenna placement**: GPS needs clear sky view. Try placing antenna outside.
- **Recording duration**: Try longer recording (edit script to 180 or 300 seconds)
- **Signal strength**: Check if antenna Bias-T is working (antenna needs power)

### "Config file not found" error
Make sure you're running from the `gnss-sdr` directory:
```bash
cd /Users/patrykorwat/git/web-spectrum/gnss-sdr
./simple_start.sh
```

### "No monitor data" warning
This is normal during acquisition (first 30-60 seconds). Wait for satellites to be tracked and ephemeris decoded. If it persists >2 minutes, antenna placement may need improvement.

### Script interrupted
Just run it again:
```bash
./simple_start.sh
```
It will clean up automatically and start fresh.

## How It Works

```
┌─────────────┐      ┌──────────────┐      ┌───────────┐
│   SDRPlay   │ ───▶ │ IQ Recording │ ───▶ │   File    │
│  (GPS L1)   │      │  2 minutes   │      │ /tmp/*.dat│
└─────────────┘      └──────────────┘      └─────┬─────┘
                                                   │
                                                   ▼
                                            ┌─────────────┐
                                            │  GNSS-SDR   │
                                            │ (Processes) │
                                            └──────┬──────┘
                                                   │
                                                   ▼
                                            ┌─────────────┐
                                            │ UDP Monitor │
                                            │  Port 1234  │
                                            └──────┬──────┘
                                                   │
                                                   ▼
                                            ┌─────────────┐
                                            │   Bridge    │
                                            │  WebSocket  │
                                            └──────┬──────┘
                                                   │
                                                   ▼
                                            ┌─────────────┐
                                            │   Web UI    │
                                            │  Port 8766  │
                                            └─────────────┘
```

## Files Involved

- `simple_start.sh` - Main script (THIS IS WHAT YOU RUN!)
- `record_iq_samples.py` - Records IQ samples from SDRPlay
- `gnss_sdr_bridge.py` - WebSocket bridge
- `gnss_sdr_file.conf` - GNSS-SDR configuration for file processing
- `/tmp/gps_iq_samples.dat` - Recorded IQ samples (auto-created)

## Verified Results

This approach has been **proven to work**:
- ✅ Successfully acquired 6 satellites (PRN 26, 17, 06, 16, 03, 02)
- ✅ File-based processing works reliably
- ✅ GNSS-SDR tracking confirmed in logs

The only requirement is good antenna placement!

## Alternative: Continuous Mode

If you want real-time continuous processing (instead of batch file), see:
- [CONTINUOUS_MODE.md](CONTINUOUS_MODE.md) - Continuous recording approach
- [gnss_sdr_sdrplay_direct.conf](gnss_sdr_sdrplay_direct.conf) - Direct Osmosdr approach

But **start with this simple approach first** to verify everything works!

## Support

If you have issues:
1. Check antenna has clear sky view
2. Try longer recording duration
3. Check `/tmp/*.log` for GNSS-SDR errors
4. Verify SDRPlay with: `SoapySDRUtil --find="driver=sdrplay"`

Good luck! 🛰️
