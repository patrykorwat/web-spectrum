#!/usr/bin/env python3
"""Generate full 2 MHz bandwidth spectrum with frequency averaging"""

import numpy as np
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from gps_spectrum_analyzer import GPSSpectrumAnalyzer, plot_narrowband_zoom

# Initialize analyzer
analyzer = GPSSpectrumAnalyzer(sample_rate=2.048e6)

# Load samples - 2 seconds for full bandwidth view
print("Loading 2 seconds of data...")
samples = analyzer.load_samples('recordings/gps_recording_20251214_082738.dat',
                                max_samples=int(2 * 2.048e6))

# Compute spectrogram with moderate resolution for full bandwidth
# Use smaller FFT for faster processing: 2,048,000 / 2048 = 1000 Hz per bin
print("Computing full-band spectrogram...")
nperseg = 2048  # Small FFT for speed
noverlap = int(nperseg * 0.5)  # 50% overlap for speed
f, t, Sxx_db = analyzer.compute_spectrogram(samples, nperseg=nperseg, noverlap=noverlap)

# Generate full bandwidth plot (entire 2 MHz)
print("Generating full 2 MHz bandwidth plot...")
plot_narrowband_zoom(f, t, Sxx_db,
                    'recordings/test_fullband_2mhz_2sec.png',
                    zoom_bw=2.048e6,  # Full bandwidth
                    freq_offset=0)  # Centered

print("\n✓ Done! Check: recordings/test_fullband_2mhz_2sec.png")
