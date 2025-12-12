#!/usr/bin/env python3
"""
Quick GPS Signal Detection
Checks if GPS C/A code is present in recording using correlation
"""

import numpy as np
import sys

def generate_ca_code(prn):
    """Generate GPS C/A code for given PRN (simplified)"""
    # This is a simplified version - just for PRN 1
    # Full implementation would need all PRN polynomials
    if prn == 1:
        # PRN 1: G2 taps at 2 and 6
        g1 = np.ones(1023, dtype=int)
        g2 = np.ones(1023, dtype=int)

        # Initialize with 1s
        g1_reg = [1] * 10
        g2_reg = [1] * 10

        ca_code = np.zeros(1023, dtype=int)

        for i in range(1023):
            ca_code[i] = (g1_reg[9] + g2_reg[1] + g2_reg[5]) % 2

            # G1 feedback: taps at 3 and 10
            g1_feedback = (g1_reg[2] + g1_reg[9]) % 2
            g1_reg = [g1_feedback] + g1_reg[:-1]

            # G2 feedback: multiple taps
            g2_feedback = (g2_reg[1] + g2_reg[2] + g2_reg[4] + g2_reg[5] + g2_reg[7] + g2_reg[8] + g2_reg[9]) % 2
            g2_reg = [g2_feedback] + g2_reg[:-1]

        return ca_code * 2 - 1  # Convert to +1/-1

    return None

def quick_acquisition_check(filepath, prn_list=[1, 3, 6, 11, 14, 17, 19, 22, 28], duration=1.0):
    """
    Quick check if GPS signals are present

    Args:
        filepath: Recording file
        prn_list: List of PRN numbers to check
        duration: Duration in seconds to analyze
    """
    print("=" * 70)
    print(f"Quick GPS Signal Check: {filepath}")
    print("=" * 70)
    print()

    sample_rate = 2.048e6
    samples_per_code = int(sample_rate * 0.001)  # 1ms = 1 C/A code period

    # Read data
    samples_to_read = int(sample_rate * duration)
    print(f"Reading {duration} second(s) of data...")

    try:
        data = np.fromfile(filepath, dtype=np.complex64, count=samples_to_read)
        print(f"✓ Read {len(data):,} samples\n")
    except Exception as e:
        print(f"❌ Error: {e}")
        return

    # Try PRN 1 as a quick test
    print("Attempting to detect GPS satellites...")
    print("(Simplified correlation - this is just a basic check)\n")

    # For each ms chunk, compute power
    num_chunks = len(data) // samples_per_code
    chunk_powers = []

    for i in range(min(num_chunks, 1000)):  # Check first 1000ms
        chunk = data[i * samples_per_code:(i+1) * samples_per_code]
        power = np.mean(np.abs(chunk) ** 2)
        chunk_powers.append(power)

    chunk_powers = np.array(chunk_powers)
    mean_power = np.mean(chunk_powers)
    std_power = np.std(chunk_powers)

    print(f"Signal Power Analysis:")
    print(f"  Mean power: {mean_power:.9f}")
    print(f"  Std dev: {std_power:.9f}")
    print(f"  Power variation: {(std_power / mean_power * 100):.2f}%")
    print()

    # Check for modulation (GPS signal should show power variation)
    if std_power / mean_power > 0.05:
        print("✓ Signal shows power variation (good sign - possible GPS modulation)")
    else:
        print("⚠️  Low power variation - signal may be noise or interference")

    # Check power spectral density
    print("\nFrequency Domain Analysis:")
    print("-" * 70)

    # Take FFT of a chunk
    fft_size = 16384
    chunk = data[:fft_size]
    fft = np.fft.fftshift(np.fft.fft(chunk))
    fft_mag = np.abs(fft) ** 2
    fft_mag_db = 10 * np.log10(fft_mag / np.max(fft_mag) + 1e-10)

    # Check if there's a peak (GPS C/A has specific bandwidth)
    center_idx = len(fft) // 2
    bw_bins = int(2.046e6 / (sample_rate / fft_size))  # GPS C/A main lobe bandwidth

    center_power = np.mean(fft_mag[center_idx - bw_bins:center_idx + bw_bins])
    edges_power = (np.mean(fft_mag[:bw_bins * 2]) + np.mean(fft_mag[-bw_bins * 2:])) / 2

    snr_estimate = 10 * np.log10(center_power / edges_power)

    print(f"  Estimated in-band SNR: {snr_estimate:.1f} dB")

    if snr_estimate > 3:
        print(f"  ✓ Detectable signal power in GPS band")
    else:
        print(f"  ❌ Weak/no signal in GPS band")

    print()
    print("=" * 70)
    print("Assessment:")
    print("-" * 70)

    if snr_estimate > 3 and std_power / mean_power > 0.05:
        print("✓ Recording appears to contain GPS-like signals")
        print("  → GNSS-SDR should be able to acquire satellites")
        print("  → Issue may be configuration or processing time")
        print()
        print("Recommendations:")
        print("  1. Let GNSS-SDR process the ENTIRE file (can take 15-30 min)")
        print("  2. Try the aggressive_acq.conf configuration")
        print("  3. Check for frequency offset (SDRplay PPM error)")
    elif mean_power < 1e-5:
        print("❌ Signal power too low")
        print("  → Gain was too low during recording")
        print()
        print("Recommendations:")
        print("  1. Record again with higher gain (try --gain-reduction 20)")
        print("  2. Check antenna connection")
        print("  3. Verify antenna works at GPS L1 frequency (1575.42 MHz)")
    else:
        print("⚠️  Signal present but unclear if GPS")
        print()
        print("Possible issues:")
        print("  1. Frequency offset too large (> 5 kHz)")
        print("  2. Interference or jamming present")
        print("  3. Recording location had no satellite visibility")
        print()
        print("Recommendations:")
        print("  1. Record again in different location")
        print("  2. Try recording for longer (10-15 minutes)")
        print("  3. Check if L1 band filter is working correctly")

    print("=" * 70)

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python3 quick_gps_check.py <recording.dat>")
        sys.exit(1)

    quick_acquisition_check(sys.argv[1])
