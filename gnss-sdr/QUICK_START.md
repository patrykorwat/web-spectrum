# GNSS-SDR Quick Start Guide

## 🚀 Two Scripts Available

### Option 1: `simple_start.sh` - One-Time Recording
**Best for**: Testing, manual operation, single recordings

```bash
cd gnss-sdr
./simple_start.sh
```

**What it does:**
1. Records 2 minutes of GPS samples
2. Processes with GNSS-SDR (takes ~60 seconds)
3. **Stops** when done

**Use when:**
- Testing the system for the first time
- You want manual control
- You only need one recording session

---

### Option 2: `continuous_start.sh` - Infinite Loop ⭐ RECOMMENDED
**Best for**: Continuous operation, long-term monitoring

```bash
cd gnss-sdr
./continuous_start.sh
```

**What it does:**
1. Records 2 minutes of GPS samples
2. Processes with GNSS-SDR (takes ~60 seconds)
3. Shows satellite tracking results
4. **Repeats forever** (Ctrl+C to stop)

**Use when:**
- You want continuous GPS monitoring
- Running long-term (hours/days)
- Want fresh data every cycle

---

## 📊 Comparison

| Feature | simple_start.sh | continuous_start.sh |
|---------|-----------------|---------------------|
| **Runs continuously** | ❌ No | ✅ Yes |
| **Recording time** | 2 minutes | 2 min per cycle |
| **Auto-restart** | ❌ No | ✅ Yes |
| **Shows progress** | ✅ Yes | ✅ Yes + cycle count |
| **Satellite count** | ❌ No | ✅ Yes |
| **Good for testing** | ✅ Yes | ⚠️ Overkill |
| **Good for production** | ❌ No | ✅ Yes |

---

## 🎯 My Recommendation

**First time?** Start with `simple_start.sh` to test everything works.

**For actual use?** Run `continuous_start.sh` for continuous operation.

---

## 📱 Web UI Connection

Both scripts work with your Web UI:

1. Your Web UI **already defaults to SDRPlay/GNSS-SDR page** ✅
2. Open browser to your web-spectrum UI
3. It will auto-connect to WebSocket (no manual setup needed)
4. You'll see satellite data appear during GNSS-SDR processing

**Note:** The continuous script processes files in cycles, so you'll see satellite data appear during each processing phase (after recording completes).

---

## ⚠️ Important Notes

### Antenna Placement
- **Must have clear sky view** (outside or window)
- GPS signals are VERY weak (-160 dBm)
- Obstructions = no satellites

### Timing
- Recording: 2 minutes (be patient!)
- Processing: ~60 seconds
- Total cycle time: ~3 minutes

### Stopping
- Press `Ctrl+C` to stop either script
- Automatic cleanup on exit
- Safe to restart anytime

---

## 🔧 Troubleshooting

### "SDRPlay not found"
```bash
# Check if SDRPlay is detected
SoapySDRUtil --find="driver=sdrplay"
```

### "No satellites tracked"
- Check antenna has clear sky view
- Try placing antenna outside
- Wait for full 2-minute recording
- Check `/tmp/gnss_sdr_output.log` for details

### Script hangs during recording
- SDRPlay may be in use by another program
- Kill all: `killall -9 python3 gnss-sdr`
- Restart script

---

## 📁 What Gets Created

Both scripts create:
- `/tmp/gps_iq_samples.dat` - Recorded IQ samples (~1.8GB per 2 minutes)
- `/tmp/gnss_sdr_output.log` - GNSS-SDR processing log
- `/tmp/*.kml` - GPS position tracks (if fix achieved)
- `/tmp/*.gpx` - GPS position tracks (if fix achieved)

---

## 🎉 Quick Summary

**Want continuous operation?**
```bash
cd gnss-sdr
./continuous_start.sh
```

**Want one-time test?**
```bash
cd gnss-sdr
./simple_start.sh
```

That's it! 🛰️
