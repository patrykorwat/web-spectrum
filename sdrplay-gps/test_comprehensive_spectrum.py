#!/usr/bin/env python3
"""Generate comprehensive multi-panel spectrum plot"""

import numpy as np
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from gps_spectrum_analyzer import GPSSpectrumAnalyzer, plot_spectrum

# Initialize analyzer
analyzer = GPSSpectrumAnalyzer(sample_rate=2.048e6)

# Load samples - 5 seconds for full bandwidth analysis
print("Loading 5 seconds of data...")
samples = analyzer.load_samples('recordings/gps_recording_20251214_082738.dat',
                                max_samples=int(5 * 2.048e6))

# Compute spectrogram with moderate resolution for full 2 MHz
# 2,048,000 / 2048 = 1000 Hz per bin
print("Computing spectrogram...")
nperseg = 2048
noverlap = int(nperseg * 0.5)
f, t, Sxx_db = analyzer.compute_spectrogram(samples, nperseg=nperseg, noverlap=noverlap)

# Create dummy results (no detection, just visualization)
results = {
    'sweep': {'detected': False},
    'pulse': {'detected': False},
    'noise': {'detected': False},
    'meaconing': {'detected': False},
    'narrowband': {'detected': False}
}

# Generate comprehensive plot with spectrogram, average spectrum, and power vs time
print("Generating comprehensive plot...")
plot_spectrum(f, t, Sxx_db, results, 'recordings/test_comprehensive_spectrum.png',
              sample_rate=analyzer.sample_rate)

print("\n✓ Done! Check: recordings/test_comprehensive_spectrum.png")
