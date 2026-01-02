# RSPduo GPS Spectrum Monitor

Optimized GPS L1 (1575.42 MHz) spectrum monitoring system using SDRplay RSPduo at 8 MSPS.

## Quick Start

### Continuous Monitoring
```bash
./continuous_monitor.sh
```
Captures 10-second recordings every 15 seconds, generates spectrograms automatically.
Latest image: `recordings/*_monitor.jpeg`

### Single Recording
```bash
python3 simple_record.py 10.0  # Record 10 seconds
```

## Optimized Configuration

**Current settings (Jan 2026):**
- **Sample Rate:** 8 MSPS (full 8 MHz bandwidth)
- **Gain:** gRdB=21 (~38 dB system gain, ~58 dB total with active antenna)
- **IQ Correction:** ENABLED (reduces parabolic artifact)
- **Bias-T:** ENABLED (powers active antenna)
- **Bandwidth Filter:** BW_8_000 (8 MHz)

**Performance:**
- Noise floor: -112.27 dB
- Dynamic range: 4.05 dB
- GPS signals clearly visible
- Parabolic artifact: 0.11 (minimized)

## Files

### Core Scripts
- **sdrplay_direct.py** - SDRplay API wrapper (optimized config)
- **simple_record.py** - Basic recording script
- **continuous_monitor.sh** - Background monitoring loop
- **process_fast.py** - Fast spectrogram generation

### Alternatives
- **rtlsdr_direct.py** - RTL-SDR support
- **soapy_record.py** - SoapySDR support
- **gps_spectrum_analyzer.py** - Real-time spectrum analyzer
- **recording_api_simple.py** - HTTP API server

## Usage Examples

### Background Monitoring
```bash
nohup ./continuous_monitor.sh > monitor.log 2>&1 &
tail -f monitor.log
```

### Custom Recording
```bash
python3 simple_record.py 30.0  # 30-second recording
python3 process_fast.py recordings/gps_recording_*.dat
```

### Change Sample Rate
Edit simple_record.py line 12:
```python
SAMPLE_RATE = 8e6  # 8 MSPS (can be 2.048, 6, 8, or 10 MSPS)
```

### Adjust Gain
Edit sdrplay_direct.py line 813:
```python
rx_params.tunerParams.gain.gRdB = 21  # Lower = more gain
```

## Optimization History

**2026-01-02:** Binary search optimization
- Previous: gRdB=54 (~5 dB gain) - signals buried in noise
- Optimized: gRdB=21 (~38 dB gain) - GPS signals visible
- Improvement: +33 dB gain, -7.6 dB noise floor

## Requirements

- Python 3.x
- SDRplay API 3.15+ (libsdrplay_api.dylib)
- numpy, scipy, matplotlib

## License

Research/educational use
