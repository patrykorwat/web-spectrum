#!/usr/bin/env python3
"""
Fast spectrogram generation using optimized methods
- Downsample intelligently to reduce data
- Use imshow instead of pcolormesh (much faster)
- Optimize FFT parameters
"""
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from scipy import signal, fft
import sys
import time

if len(sys.argv) < 2:
    print("Usage: python3 process_fast.py <input.dat>")
    sys.exit(1)

FILE = sys.argv[1]
PLOT = FILE.replace('.dat', '_fast.jpeg')

start = time.time()
print(f"Loading samples from {FILE}...")
samples = np.fromfile(FILE, dtype=np.complex64)
print(f"Loaded {len(samples):,} samples ({len(samples)/1e6:.1f}M) in {time.time()-start:.1f}s")

# Smart decimation based on file size
# For 3 seconds at 10 MSPS: 30M samples -> decimate 5x -> 6M samples = 1.2 MHz BW
# For 1 second: 10M samples -> decimate 2x -> 5M samples = 4 MHz BW
if len(samples) > 20e6:
    # Large file: heavy decimation
    decim_factor = 5
    samples = samples[::decim_factor]
    fs = 10e6 / decim_factor  # 2 MSPS
    bw_mhz = 1.6
    print(f"Decimated {decim_factor}x -> {len(samples):,} samples, {fs/1e6:.1f} MSPS ({bw_mhz} MHz BW)")
elif len(samples) > 10e6:
    # Medium file: moderate decimation
    decim_factor = 3
    samples = samples[::decim_factor]
    fs = 10e6 / decim_factor  # 3.33 MSPS
    bw_mhz = 2.7
    print(f"Decimated {decim_factor}x -> {len(samples):,} samples, {fs/1e6:.1f} MSPS ({bw_mhz} MHz BW)")
else:
    # Small file: minimal decimation
    decim_factor = 2
    samples = samples[::decim_factor]
    fs = 10e6 / decim_factor  # 5 MSPS
    bw_mhz = 4.0
    print(f"Decimated {decim_factor}x -> {len(samples):,} samples, {fs/1e6:.1f} MSPS ({bw_mhz} MHz BW)")

# Optimized spectrogram parameters
nperseg = 256  # Smaller FFT = faster
noverlap = 128  # 50% overlap

print(f"Computing spectrogram...")
t1 = time.time()
f, t, Sxx = signal.spectrogram(samples, fs=fs, nperseg=nperseg, noverlap=noverlap,
                                return_onesided=False, mode='magnitude')
print(f"Spectrogram computed in {time.time()-t1:.1f}s")

# Convert to dB
Sxx_db = 20 * np.log10(Sxx + 1e-12)  # Use 20*log10 for magnitude

# Shift zero frequency to center
f = fft.fftshift(f)
Sxx_db = fft.fftshift(Sxx_db, axes=0)

print(f"Generating plot (using imshow - much faster)...")
t1 = time.time()

fig, ax = plt.subplots(figsize=(20, 10), dpi=100)  # Reduced DPI for speed
fig.patch.set_facecolor('#0a0a0a')
ax.set_facecolor('#1a1a1a')

# Use imshow instead of pcolormesh (10-100x faster!)
vmin, vmax = np.percentile(Sxx_db, [5, 99.5])
extent = [t[0]*1000, t[-1]*1000, f[0]/1e6, f[-1]/1e6]  # [left, right, bottom, top]

im = ax.imshow(Sxx_db, aspect='auto', origin='lower', extent=extent,
               cmap='viridis', vmin=vmin, vmax=vmax, interpolation='bilinear')

ax.set_ylabel('Frequency Offset (MHz)', fontsize=16, color='white', fontweight='bold')
ax.set_xlabel('Time (ms)', fontsize=16, color='white', fontweight='bold')

duration_s = len(samples) / fs
ax.set_title(f'RSPduo @ 10 MSPS - {duration_s:.1f}s - {bw_mhz} MHz BW (FAST MODE)',
             fontsize=18, color='yellow', fontweight='bold')

ax.tick_params(colors='white', labelsize=12)
ax.grid(True, alpha=0.2, color='white', linewidth=0.5)
for spine in ax.spines.values():
    spine.set_color('white')
    spine.set_linewidth(1.5)

cbar = plt.colorbar(im, ax=ax)
cbar.set_label('Power (dB)', color='white', fontsize=14)
cbar.ax.tick_params(colors='white', labelsize=10)

plt.tight_layout()
plt.savefig(PLOT, bbox_inches='tight', facecolor='#0a0a0a', dpi=100)
print(f"Plot saved in {time.time()-t1:.1f}s")

print(f'\n✓ COMPLETE: {PLOT}')
print(f'Total time: {time.time()-start:.1f}s')
print(f'Spectrogram shape: {Sxx_db.shape}')
