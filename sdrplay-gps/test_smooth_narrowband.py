#!/usr/bin/env python3
"""Quick test of smooth narrowband rendering"""

import numpy as np
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from gps_spectrum_analyzer import GPSSpectrumAnalyzer, plot_narrowband_zoom

# Initialize analyzer
analyzer = GPSSpectrumAnalyzer(sample_rate=2.048e6)

# Load samples - 14 seconds for extended analysis
print("Loading 14 seconds of data for extended analysis...")
samples = analyzer.load_samples('recordings/gps_recording_20251214_082738.dat',
                                max_samples=int(14 * 2.048e6))

# Compute spectrogram with 5 Hz resolution
# For 5 Hz bins: FFT size = 2,048,000 / 5 = 409,600
print("Computing high-res spectrogram (5 Hz bins)...")
nperseg = 409600
noverlap = int(nperseg * 0.75)  # 75% overlap for more time bins
f, t, Sxx_db = analyzer.compute_spectrogram(samples, nperseg=nperseg, noverlap=noverlap)

# Generate narrowband plot with smooth rendering
# Wider zoom (300 kHz = ±150 kHz) with frequency offset
print("Generating smooth narrowband plot...")
plot_narrowband_zoom(f, t, Sxx_db,
                    'recordings/test_smooth_300khz_14sec.png',
                    zoom_bw=300e3,  # ±150 kHz
                    freq_offset=200e3)  # Offset by 200 kHz

print("\n✓ Done! Check: recordings/test_smooth_300khz_14sec.png")
