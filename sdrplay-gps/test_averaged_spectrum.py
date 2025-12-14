#!/usr/bin/env python3
"""Generate averaged frequency spectrum across full 2 MHz bandwidth"""

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from gps_spectrum_analyzer import GPSSpectrumAnalyzer

# Initialize analyzer
analyzer = GPSSpectrumAnalyzer(sample_rate=2.048e6)

# Load samples - 10 seconds for good averaging
print("Loading 10 seconds of data for averaging...")
samples = analyzer.load_samples('recordings/gps_recording_20251214_082738.dat',
                                max_samples=int(10 * 2.048e6))

# Compute averaged power spectrum
print("Computing averaged power spectrum...")
# Use Welch's method for averaged spectrum
from scipy import signal

# Use moderate FFT size for good frequency resolution
nperseg = 8192  # Gives ~250 Hz resolution
f, psd = signal.welch(samples, fs=analyzer.sample_rate, nperseg=nperseg,
                      noverlap=nperseg//2, window='boxcar',
                      return_onesided=False, scaling='density')

# Shift to center DC
f = np.fft.fftshift(f)
psd = np.fft.fftshift(psd)

# Convert to dB
psd_db = 10 * np.log10(psd + 1e-20)

# Create plot
print("Generating averaged spectrum plot...")
fig, ax = plt.subplots(figsize=(20, 10), dpi=150)

# Dark background
fig.patch.set_facecolor('#0a0a0a')
ax.set_facecolor('#1a1a1a')

# Plot averaged spectrum
ax.plot(f / 1e3, psd_db, color='cyan', linewidth=1.5, alpha=0.9)
ax.fill_between(f / 1e3, psd_db, np.min(psd_db), color='cyan', alpha=0.2)

# Styling
ax.set_xlabel('Frequency Offset (kHz)', fontsize=14, fontweight='bold', color='white')
ax.set_ylabel('Power Spectral Density (dB)', fontsize=14, fontweight='bold', color='white')
ax.set_title(f'Averaged Power Spectrum: Full 2 MHz Bandwidth | 10 seconds | Resolution: {f[1]-f[0]:.1f} Hz',
             fontsize=16, fontweight='bold', color='white')
ax.grid(True, alpha=0.3, color='white', linestyle='--', linewidth=0.5)

# White axes
ax.tick_params(colors='white', which='both')
ax.spines['bottom'].set_color('white')
ax.spines['top'].set_color('white')
ax.spines['left'].set_color('white')
ax.spines['right'].set_color('white')

plt.savefig('recordings/test_averaged_spectrum_2mhz.png', dpi=150, bbox_inches='tight')
plt.close()

print(f"\n✓ Done! Check: recordings/test_averaged_spectrum_2mhz.png")
print(f"  Frequency range: {f[0]/1e3:.1f} to {f[-1]/1e3:.1f} kHz")
print(f"  Frequency resolution: {f[1]-f[0]:.1f} Hz")
print(f"  Power range: {np.min(psd_db):.1f} to {np.max(psd_db):.1f} dB")
