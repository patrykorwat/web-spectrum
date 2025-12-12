#!/usr/bin/env python3
"""
Analyze GPS Recording Signal Quality
Quick check to see if recording contains GPS signals
"""

import numpy as np
import sys

def analyze_gps_recording(filepath, duration_seconds=10):
    """
    Analyze GPS recording to check signal quality

    Args:
        filepath: Path to .dat file
        duration_seconds: How many seconds to analyze (default 10)
    """
    print("=" * 70)
    print(f"GPS Recording Analysis: {filepath}")
    print("=" * 70)
    print()

    # GPS L1 C/A parameters
    sample_rate = 2.048e6  # 2.048 MSPS
    gps_l1_freq = 1575.42e6  # GPS L1 frequency

    # Read samples
    samples_to_read = int(sample_rate * duration_seconds)
    print(f"Reading {duration_seconds} seconds ({samples_to_read:,} samples)...")

    try:
        data = np.fromfile(filepath, dtype=np.complex64, count=samples_to_read)
        print(f"✓ Read {len(data):,} samples")
    except Exception as e:
        print(f"❌ Error reading file: {e}")
        return

    print()
    print("Signal Statistics:")
    print("-" * 70)
    print(f"  I (real) range: [{data.real.min():.6f}, {data.real.max():.6f}]")
    print(f"  Q (imag) range: [{data.imag.min():.6f}, {data.imag.max():.6f}]")
    print(f"  I mean: {data.real.mean():.6f}")
    print(f"  Q mean: {data.imag.mean():.6f}")
    print(f"  I std dev: {data.real.std():.6f}")
    print(f"  Q std dev: {data.imag.std():.6f}")
    print(f"  Power (magnitude²): {np.mean(np.abs(data)**2):.6f}")
    print()

    # Check for common issues
    print("Signal Quality Checks:")
    print("-" * 70)

    if np.all(data == 0):
        print("❌ FATAL: All samples are zero - recording failed!")
        return

    if data.std() < 0.001:
        print("❌ FATAL: Very low signal variance - likely no signal captured")
        return

    # Check dynamic range
    dynamic_range_db = 20 * np.log10(np.abs(data).max() / (np.abs(data).mean() + 1e-10))
    print(f"✓ Dynamic range: {dynamic_range_db:.1f} dB")

    if dynamic_range_db < 10:
        print("⚠️  WARNING: Low dynamic range - signal may be weak")

    # Check for DC offset
    dc_offset = np.abs(data.mean())
    if dc_offset > 0.01:
        print(f"⚠️  WARNING: Significant DC offset: {dc_offset:.6f}")
    else:
        print(f"✓ DC offset acceptable: {dc_offset:.6f}")

    # Simple power spectrum check (very rough)
    print()
    print("Basic Frequency Analysis:")
    print("-" * 70)

    # Take a small chunk for FFT
    chunk_size = 8192
    chunk = data[:chunk_size]

    # Compute FFT
    fft_result = np.fft.fft(chunk)
    fft_mag = np.abs(fft_result)
    fft_mag_db = 20 * np.log10(fft_mag / fft_mag.max())

    # Find peaks
    peak_indices = np.argsort(fft_mag)[-5:]  # Top 5 peaks

    print(f"  FFT size: {chunk_size}")
    print(f"  Frequency resolution: {sample_rate / chunk_size / 1000:.1f} kHz")
    print()
    print("  Top 5 frequency components:")
    for i, idx in enumerate(reversed(peak_indices)):
        freq = (idx * sample_rate / chunk_size)
        if freq > sample_rate / 2:
            freq -= sample_rate
        power_db = fft_mag_db[idx]
        print(f"    {i+1}. {freq/1e6:+8.3f} MHz: {power_db:+6.1f} dB")

    print()
    print("Overall Assessment:")
    print("-" * 70)

    # Estimate signal quality
    snr_estimate = dynamic_range_db - 10  # Very rough estimate

    if data.std() < 0.002:
        print("❌ Signal appears too weak - likely no GPS satellites visible")
        print("   → Try recording outdoors with clear sky view")
        print("   → Check antenna connection")
        print("   → Increase gain (lower --gain-reduction value)")
    elif data.std() > 0.02:
        print("⚠️  Signal may be too strong - possible saturation")
        print("   → Consider reducing gain")
    else:
        print("✓ Signal level looks reasonable")
        print(f"  Estimated SNR: ~{snr_estimate:.1f} dB")

        if snr_estimate < 5:
            print("⚠️  Low SNR - may struggle to acquire satellites")
            print("   → Try longer recording (10-15 minutes)")
            print("   → Ensure antenna has clear view of sky")
        else:
            print("✓ SNR should be sufficient for satellite acquisition")

    print()
    print("=" * 70)


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python3 analyze_recording.py <recording.dat>")
        print()
        print("Example:")
        print("  python3 analyze_recording.py recordings/gps_recording_20251212_082153.dat")
        sys.exit(1)

    filepath = sys.argv[1]
    analyze_gps_recording(filepath)
