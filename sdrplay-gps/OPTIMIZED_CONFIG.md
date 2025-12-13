# Optimized GPS Configuration

## Recording Settings (SDRplay RSP2)

### Hardware Configuration
- **Frequency**: 1575.42 MHz (GPS L1)
- **Sample Rate**: 2.048 MSPS (optimal for GPS L1 C/A)
- **Gain Reduction**: 30 dB (prevents thermal issues, tested stable for 10+ min)
- **Actual Gain**: ~29 dB (hardware reports this)
- **Tuner**: Tuner B (Port 2) - for RSP2 antenna port
- **Bias-T**: ENABLED (required for active GPS antennas)

### Recording Performance
- **Expected File Size**: ~980 MB per minute (~58 MB/s)
- **5-minute recording**: ~4.9 GB
- **10-minute recording**: ~9.4 GB
- **Sample format**: Complex64 (IQ interleaved float32)

## GNSS-SDR Processing Settings

### Signal Source
```
SignalSource.implementation=File_Signal_Source
SignalSource.item_type=gr_complex
SignalSource.sampling_frequency=2048000
SignalSource.enable_throttle_control=true
```

**Note**: IQ swap is **disabled** - testing showed better performance without it.

### Input Filter
- **Type**: Freq_Xlating_Fir_Filter
- **Bandwidth**: Bandpass 0-0.45 normalized frequency
- **Purpose**: Anti-aliasing filter for GPS L1 signal

### Channels
- **Count**: 8 channels (sufficient for typical GPS constellation)
- **Simultaneous Acquisition**: 1 (serial acquisition reduces CPU load)

### Acquisition Settings
- **Coherent Integration**: 1 ms
- **Doppler Range**: ±5 kHz (covers stationary to low-speed receivers)
- **Doppler Step**: 250 Hz
- **Threshold**: 0.008
- **PFA**: 0.01 (1% false alarm probability)

### Tracking Settings (Optimized for Stationary Receiver)

**CRITICAL**: These narrow loop bandwidths are optimized for:
- Stationary receivers
- Good C/N0 (>35 dB-Hz)
- Low dynamics

```
Tracking_1C.pll_bw_hz=10.0          # PLL bandwidth (was 35 Hz, now 10 Hz)
Tracking_1C.dll_bw_hz=1.0           # DLL bandwidth (was 2 Hz, now 1 Hz)
Tracking_1C.fll_bw_hz=10.0          # FLL bandwidth for pull-in
Tracking_1C.enable_fll_pull_in=true
Tracking_1C.pll_bw_narrow_hz=5.0    # Narrow mode PLL (after lock)
Tracking_1C.dll_bw_narrow_hz=0.5    # Narrow mode DLL (after lock)
```

**Why narrow bandwidths?**
- **Wider loops** (35-50 Hz): Better for high dynamics, weak signals
- **Narrower loops** (5-10 Hz): Better for stationary, strong signals
- With C/N0 of 40+ dB-Hz and stationary antenna, narrow loops reduce noise and improve lock stability

### PVT (Position/Velocity/Time) Settings
```
PVT.positioning_mode=Single         # Standard single-point positioning
PVT.output_rate_ms=100              # 10 Hz position updates
PVT.display_rate_ms=500             # 2 Hz console output
PVT.kml_output_enabled=true         # Google Earth output
PVT.gpx_output_enabled=true         # GPX track output
PVT.enable_monitor=true             # UDP monitoring on port 1234
```

## Known Issues & Limitations

### GPS Availability in Gdańsk Area

**Test Results (December 2025)**:
- **Outdoor antenna**: High-precision antenna on balcony balustrade
- **Recording quality**: Excellent (10 minutes, stable 2.048 MSPS)
- **Signal strength**: C/N0 39-46 dB-Hz (very strong)
- **Ephemeris data**: Complete (subframes 1-5 received)
- **Satellite tracking**: **UNSTABLE** - frequent lock losses
- **Position fix**: **FAILED** - only 1 satellite maintained stable lock

**Root Cause**: Likely **GPS jamming/interference** in Baltic region
- Need 4+ satellites for 3D position fix
- Only 1 satellite (PRN 15) maintained stable tracking
- 149 lock losses in 10-minute recording
- Gdańsk proximity to Kaliningrad/Russian border
- Known GPS jamming activity in Baltic region

### Recommendations

1. **For Testing**: Try recording at different times of day
2. **For Production**: Consider using multi-GNSS (GPS + GLONASS + Galileo) if supported
3. **For Debugging**: Monitor satellite visibility with online tools (e.g., GPS Status apps)

## File Locations

### Configuration Files
- `/sdrplay-gps/gnss_sdr_file.conf` - Standalone GNSS-SDR config
- `/sdrplay-gps/recording_api_simple.py` - Backend API with embedded config

### Scripts
- `/sdrplay-gps/sdrplay_direct.py` - Recording script
- `/sdrplay-gps/start_backend.sh` - Start HTTP API + WebSocket servers

### Output Files
- `/sdrplay-gps/recordings/*.dat` - IQ recordings
- `/sdrplay-gps/recordings/*.nmea` - GPS position fixes (if achieved)
- `/sdrplay-gps/recordings/*.kml` - Google Earth tracks
- `/sdrplay-gps/recordings/*.gpx` - GPX tracks

## Testing Results

### What Works ✅
- SDRplay RSP2 hardware initialization
- Bias-T power for active antenna
- Stable 10-minute recordings at 2.048 MSPS
- GPS signal acquisition (C/N0 39-46 dB-Hz)
- Ephemeris data download (complete subframes)
- Event handling (PowerOverload acknowledgment)

### What Doesn't Work ❌
- **Position fix** - GPS jamming prevents stable tracking of 4+ satellites
- Long-duration recordings sometimes stop early (USB/thermal issue)

## Change Log

**2025-12-13**:
- Disabled IQ swap (better performance without it)
- Reduced PLL bandwidth from 35 Hz to 10 Hz (stationary receiver optimization)
- Reduced DLL bandwidth from 2 Hz to 1 Hz
- Added narrow tracking mode (5 Hz PLL, 0.5 Hz DLL)
- Reduced channels from 12 to 8 (CPU optimization)
- Reduced acquisition channels from 12 to 1 (serial acquisition)
- Set gain reduction to 30 dB (prevents thermal shutdown)
- Confirmed Bias-T enabled for active antenna
- Documented GPS jamming issue in Gdańsk area
