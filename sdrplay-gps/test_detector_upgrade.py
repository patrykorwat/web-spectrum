#!/usr/bin/env python3
"""Functional self-test for the REWRITTEN pulse/noise detectors.

Verifies on synthetic IQ that:
1. clean Gaussian noise  -> pulse detector does NOT fire (old one always fired),
2. pulsed jammer 110 Hz / 45% duty -> detected with rate ~110 Hz,
3. time_series rows are produced for charting,
4. noise detector: flat elevated band detected; delta vs baseline reported.
"""
import sys, os, json, subprocess, tempfile
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gps_spectrum_analyzer import GPSSpectrumAnalyzer

FS = 2_048_000
DUR = 6.0
N = int(FS * DUR)
rng = np.random.default_rng(42)

def to_c64(iq):
    return (iq.real.astype(np.float32) + 1j * iq.imag.astype(np.float32)).astype(np.complex64)

fails = []

# --- 1) clean noise ---
clean = (rng.normal(0, 1000, N) + 1j * rng.normal(0, 1000, N)).astype(np.complex64)
a = GPSSpectrumAnalyzer(FS)
ts = []
p_clean = a.detect_pulse_jammer(clean, verbose=True, time_series=ts)
print("clean:", json.dumps({k: p_clean[k] for k in ('detected', 'pulse_rate_hz', 'acf_peak', 'confidence')}))
print("time_series rows:", len(ts), "first:", ts[0] if ts else None)
if p_clean['detected']:
    fails.append("clean noise flagged as pulsed (false positive)")
if not ts:
    fails.append("no time series rows for clean")
if any(('acf' not in r or 'nf' not in r) for r in ts):
    fails.append("time series rows missing keys")

# --- 2) pulsed jammer 110 Hz, 45% duty ---
t = np.arange(N) / FS
gate = ((t * 110.0) % 1.0) < 0.45
jam = clean + gate * (rng.normal(0, 20000, N) + 1j * rng.normal(0, 20000, N))
a2 = GPSSpectrumAnalyzer(FS)
ts2 = []
p_jam = a2.detect_pulse_jammer(jam, verbose=True, time_series=ts2)
print("pulsed:", json.dumps({k: p_jam[k] for k in ('detected', 'pulse_rate_hz', 'duty_cycle', 'acf_peak', 'confidence', 'num_pulses')}))
if not p_jam['detected']:
    fails.append("110 Hz pulsed jammer NOT detected")
elif abs(p_jam['pulse_rate_hz'] - 110.0) > 3.0:
    fails.append(f"pulse rate off: {p_jam['pulse_rate_hz']:.1f} vs 110")
if not ts2 or any(r['rate'] == 0 for r in ts2):
    fails.append("pulsed time series missing rate annotation")

# --- 3) noise detector: baseline vs jammed wideband ---
base_file = os.path.join(tempfile.gettempdir(), "ws_base.dat")
jam_file = os.path.join(tempfile.gettempdir(), "ws_jam.dat")
to_c64(rng.normal(0, 1000, N) + 1j * rng.normal(0, 1000, N)).tofile(base_file)
noisy = (rng.normal(0, 1000, N) + 1j * rng.normal(0, 1000, N)) + (rng.normal(0, 8000, N) + 1j * rng.normal(0, 8000, N))
to_c64(noisy).tofile(jam_file)
n_base = a2.detect_noise_jammer(np.fromfile(base_file, dtype=np.complex64), verbose=False)
n_jam = a2.detect_noise_jammer(np.fromfile(jam_file, dtype=np.complex64), baseline_file=base_file, verbose=True)
print("noise jam:", json.dumps({k: n_jam[k] for k in ('detected', 'noise_floor_db', 'spectrum_flatness_db', 'delta_vs_baseline_db', 'confidence')}))
if not n_jam['detected']:
    fails.append("wideband noise lift not detected")
if n_jam['delta_vs_baseline_db'] is None or n_jam['delta_vs_baseline_db'] < 5:
    fails.append(f"delta vs baseline too small: {n_jam['delta_vs_baseline_db']}")

# --- 4) sweep detector: clean noise must NOT fire; chirp must be caught ---
sl = int(FS * 2.0)
f_c, t_c, Sxx_clean = a.compute_spectrogram(clean[:sl], nperseg=2048, noverlap=1024, n_jobs=1)
s_clean = a.detect_sweep_jammer(f_c, t_c, Sxx_clean)
print("sweep clean:", {k: s_clean[k] for k in ('detected', 'sweep_rate_hz_per_sec', 'track_residual_hz')})
if s_clean['detected']:
    fails.append("sweep flagged on clean noise")

k_rate = 100e3  # Hz/s
phase = 2 * np.pi * (0.5 * k_rate * t[:sl] ** 2)
chirp = clean[:sl] + 8000 * (np.cos(phase) + 1j * np.sin(phase))
f_s, t_s, Sxx_chirp = a2.compute_spectrogram(chirp, nperseg=2048, noverlap=1024, n_jobs=1)
s_chirp = a2.detect_sweep_jammer(f_s, t_s, Sxx_chirp)
print("sweep chirp:", {k: s_chirp[k] for k in ('detected', 'sweep_rate_hz_per_sec', 'track_residual_hz', 'confidence')})
if not s_chirp['detected']:
    fails.append("100 kHz/s chirp NOT detected by sweep detector")
elif abs(s_chirp['sweep_rate_hz_per_sec'] - k_rate) > 0.25 * k_rate:
    fails.append(f"sweep rate off: {s_chirp['sweep_rate_hz_per_sec']:.0f} vs {k_rate:.0f}")

# --- 5) noise detector without baseline must NOT flag flat clean noise ---
n_nobase = a.detect_noise_jammer(clean, verbose=False)
if n_nobase['detected']:
    fails.append("noise detector flagged clean noise without baseline")
if not n_nobase.get('note'):
    fails.append("noise detector missing no-baseline note")


print("\nTIME_SERIES sample (pulsed, every ~4th row):")
for r in ts2[::4][:8]:
    print("  ", {k: (round(v, 2) if isinstance(v, float) else v) for k, v in r.items()})

if fails:
    print("\nFAILURES:", fails)
    sys.exit(1)
print("\nALL DETECTOR TESTS PASSED")
