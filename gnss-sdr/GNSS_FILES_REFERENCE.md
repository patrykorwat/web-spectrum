# GNSS-SDR Files Reference

Complete list of files created for GNSS-SDR + SDRPlay integration.

## 📚 Documentation Files

| File | Purpose | Audience |
|------|---------|----------|
| `GNSS_SDR_COMPLETE_SETUP.md` | **Main setup guide** - Complete installation instructions | New users |
| `GNSS_SDR_SETUP.md` | Basic setup guide | Quick reference |
| `GNSS_QUICK_REFERENCE.md` | **Command cheat sheet** - Daily use commands | Daily users |
| `GNSS_FILES_REFERENCE.md` | This file - Lists all GNSS-related files | Developers |
| `README.md` | Main project README (updated with GNSS section) | All users |

## 🔧 Configuration Files

| File | Purpose | Usage |
|------|---------|-------|
| `gnss_sdr_file.conf` | GNSS-SDR config for file processing | `gnss-sdr --config_file=gnss_sdr_file.conf` |
| `gnss_sdr_sdrplay_direct.conf` | GNSS-SDR config for direct SDRPlay | `gnss-sdr --config_file=gnss_sdr_sdrplay_direct.conf` |
| `gnss_sdr_config.conf` | GNSS-SDR config for UDP streaming | Used by bridge (experimental) |

## 🐍 Python Scripts

| File | Purpose | Usage |
|------|---------|-------|
| `record_iq_samples.py` | **Record GPS IQ samples** from SDRPlay to file | `python3 record_iq_samples.py /tmp/gps.dat 60` |
| `sdrplay_to_gnss_sdr.py` | Stream SDRPlay IQ to GNSS-SDR via UDP | Called by bridge automatically |
| `gnss_sdr_bridge.py` | **Main bridge** - Connects GNSS-SDR to web UI | `python3 gnss_sdr_bridge.py` |

**Key Features of record_iq_samples.py:**
- Records GPS L1 signals (1575.42 MHz)
- 2.048 MSPS sample rate
- Tuner 2 with bias-T enabled
- gr_complex format (32-bit float I/Q)
- Progress bar shows completion

**Key Features of gnss_sdr_bridge.py:**
- Auto-starts GNSS-SDR as subprocess
- Auto-starts SDRPlay streamer
- Receives GNSS-SDR monitor data (UDP 1234)
- Serves WebSocket (port 8766)
- Formats data for web UI

## 🔨 Installation Scripts

| File | Purpose | Estimated Time |
|------|---------|---------------|
| `install_gnss_sdr.sh` | Basic GNSS-SDR installation | 30-40 min |
| `rebuild_gnss_sdr_with_osmosdr.sh` | Build gr-osmosdr + rebuild GNSS-SDR | 60-90 min |
| `finish_osmosdr_install.sh` | Complete gr-osmosdr installation | 30-40 min |

**When to use which:**
- **install_gnss_sdr.sh:** First-time install, file processing only
- **finish_osmosdr_install.sh:** Enable real-time SDRPlay access (requires gr-osmosdr built first)
- **rebuild_gnss_sdr_with_osmosdr.sh:** Full rebuild from scratch (includes gr-osmosdr)

## 🚀 Runtime Scripts

| File | Purpose | When to Use |
|------|---------|-------------|
| `run_gnss_sdr_bridge.sh` | **Main launcher** - Starts bridge + GNSS-SDR + SDRPlay | Daily use with web UI |
| `run_sdrplay_to_gnss.sh` | Standalone SDRPlay→GNSS-SDR streamer | Testing/debugging |

**Environment variables set by scripts:**
```bash
DYLD_LIBRARY_PATH="/usr/local/lib:$DYLD_LIBRARY_PATH"
PYTHONPATH="/opt/homebrew/lib/python3.14/site-packages:$PYTHONPATH"
```

## 📊 Data Files (Generated at Runtime)

### Input Files
| File | Location | Size | Purpose |
|------|----------|------|---------|
| GPS IQ samples | `/tmp/gps_iq_samples.dat` | ~16 MB/sec | Recorded GPS signals |

### Output Files
| File | Location | Format | Purpose |
|------|----------|--------|---------|
| KML tracks | `/tmp/PVT_*.kml` | KML | Google Earth tracks |
| GPX tracks | `/tmp/PVT_*.gpx` | GPX | GPS tracks |
| Logs | `/var/folders/.../gnss-sdr.log` | Text | Debug logs |

## 🔍 File Dependencies

### For File-Based Processing
```
record_iq_samples.py
    ↓ creates
/tmp/gps_iq_samples.dat
    ↓ processed by
gnss_sdr (with gnss_sdr_file.conf)
    ↓ generates
/tmp/PVT_*.kml, /tmp/PVT_*.gpx
```

### For Bridge Mode
```
run_gnss_sdr_bridge.sh
    ↓ starts
gnss_sdr_bridge.py
    ↓ starts (subprocess)
gnss-sdr (with gnss_sdr_config.conf)
    ↓ expects UDP from
sdrplay_to_gnss_sdr.py (started by bridge)
    ↓ sends WebSocket to
Web UI (localhost:8766)
```

### For Direct Real-Time
```
gnss-sdr (with gnss_sdr_sdrplay_direct.conf)
    ↓ directly accesses
SDRPlay via Osmosdr/SoapySDR
    ↓ generates
/tmp/PVT_*.kml, /tmp/PVT_*.gpx
```

## 🛠️ Key File Modifications Made

### Fixed Issues in sdrplay_to_gnss_sdr.py
1. ✅ RSPduo device mode selection (use enumeration result)
2. ✅ Tuner 2 selection via antenna setting
3. ✅ AGC disable before manual gain
4. ✅ UDP packet chunking (1472 bytes)
5. ✅ Library path in environment

### Enhanced gnss_sdr_bridge.py
1. ✅ Auto-start GNSS-SDR subprocess
2. ✅ Auto-start SDRPlay streamer
3. ✅ Environment variables for subprocess
4. ✅ Python -B -u flags (no bytecode cache)

### Updated run_gnss_sdr_bridge.sh
1. ✅ Export DYLD_LIBRARY_PATH
2. ✅ Export PYTHONPATH
3. ✅ Activate venv if exists

## 📋 Complete File Checklist

Use this to verify your installation:

### Documentation (5 files)
- [ ] GNSS_SDR_COMPLETE_SETUP.md
- [ ] GNSS_SDR_SETUP.md
- [ ] GNSS_QUICK_REFERENCE.md
- [ ] GNSS_FILES_REFERENCE.md
- [ ] README.md (updated)

### Configuration (3 files)
- [ ] gnss_sdr_file.conf
- [ ] gnss_sdr_sdrplay_direct.conf
- [ ] gnss_sdr_config.conf

### Python Scripts (3 files)
- [ ] record_iq_samples.py
- [ ] sdrplay_to_gnss_sdr.py (fixed)
- [ ] gnss_sdr_bridge.py (enhanced)

### Installation Scripts (3 files)
- [ ] install_gnss_sdr.sh
- [ ] rebuild_gnss_sdr_with_osmosdr.sh
- [ ] finish_osmosdr_install.sh

### Runtime Scripts (2 files)
- [ ] run_gnss_sdr_bridge.sh (updated)
- [ ] run_sdrplay_to_gnss.sh (updated)

**Total: 16 files**

## 🎯 Quick Start Decision Tree

```
Do you want to test GNSS-SDR right now?
├─ YES → Use record_iq_samples.py + gnss_sdr_file.conf
│         (File-based processing, works immediately)
│
└─ NO, I want real-time streaming
   ├─ Web UI integration?
   │  ├─ YES → run_gnss_sdr_bridge.sh
   │  │        (Bridge mode, auto-starts everything)
   │  │
   │  └─ NO → gnss-sdr with gnss_sdr_sdrplay_direct.conf
   │           (Direct mode, requires gr-osmosdr)
   │
   └─ gr-osmosdr installed?
      ├─ YES → You're good to go!
      │
      └─ NO → Run finish_osmosdr_install.sh first
```

## 💡 Pro Tips

1. **Start simple:** Use file-based processing first
2. **Read docs:** GNSS_SDR_COMPLETE_SETUP.md has troubleshooting
3. **Check reference:** GNSS_QUICK_REFERENCE.md for daily commands
4. **Need help:** All files have inline comments

## 🔄 Update History

- **2024-12-04:** Created comprehensive documentation set
- **2024-12-04:** Fixed SDRPlay integration issues
- **2024-12-04:** Added file-based processing support
- **2024-12-04:** Built gr-osmosdr with Boost 1.89 compatibility

---

**Quick Links:**
- [Complete Setup Guide](./GNSS_SDR_COMPLETE_SETUP.md)
- [Quick Reference](./GNSS_QUICK_REFERENCE.md)
- [Main README](./README.md)
