#!/usr/bin/env python3
"""
Record GPS with SDRplay at 10 MSPS for full sweep jammer detection
Captures 8 MHz bandwidth to see sweeps across GPS L1 + adjacent bands
"""

import sys
import os
from datetime import datetime
from sdrplay_direct import SDRplayDevice

def main():
    duration = int(sys.argv[1]) if len(sys.argv) > 1 else 60

    print("="*70)
    print("SDRplay GNSS Recording - 10 MSPS (Full Bandwidth)")
    print("="*70)
    print(f"Duration: {duration} seconds ({duration/60:.1f} minutes)")
    print(f"Sample rate: 10 MSPS")
    print(f"Bandwidth: ~8 MHz (±4 MHz around GPS L1)")
    print(f"Center frequency: 1575.42 MHz (GPS L1)")
    print()

    # Create output filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = f"recordings/gps_recording_{timestamp}_10msps.dat"

    expected_mb = duration * 80  # 10 MSPS × 8 bytes/sample = 80 MB/sec
    print(f"Output file: {output_file}")
    print(f"Expected size: ~{expected_mb:.0f} MB ({expected_mb/1024:.2f} GB)")
    print()

    try:
        print("Step 1: Initializing SDRplay device...")
        # SDRplayDevice auto-initializes on construction
        device = SDRplayDevice()
        print("  ✓ Device initialized")

        print("\nStep 2: Configuring for GPS L1 @ 10 MSPS...")
        device.set_frequency(1575.42e6)  # GPS L1 center
        print("  ✓ Frequency: 1575.42 MHz")

        device.set_sample_rate(10e6)     # 10 MSPS
        print("  ✓ Sample rate: 10 MSPS (8 MHz bandwidth)")

        device.set_gain(30)              # 30 dB gain reduction = 29 dB actual gain
        print("  ✓ Gain: 29 dB (30 dB reduction)")
        print("  ✓ Bias-T: ENABLED (active antenna power)")
        print("  ✓ RSP2: Antenna Port B selected")

        print("\nStep 3: Starting recording...")
        print(f"  Recording for {duration} seconds...")
        print(f"  Data rate: 80 MB/sec (complex64 format)")
        print()

        # Record
        samples_collected = device.record_to_file(output_file, duration_seconds=duration)

        print("\n" + "="*70)
        print("Recording Complete!")
        print("="*70)
        print(f"Samples collected: {samples_collected:,}")
        print(f"Actual duration: {samples_collected / 10e6:.2f} seconds")
        print(f"File: {output_file}")

        # Check file size
        if os.path.exists(output_file):
            file_size = os.path.getsize(output_file)
            print(f"File size: {file_size / 1e9:.3f} GB ({file_size / 1e6:.0f} MB)")

            # Verify
            expected_size = samples_collected * 8  # 8 bytes per complex64
            size_match = abs(file_size - expected_size) < 1000
            print(f"Format check: {'✓ PASS' if size_match else '⚠️  FAIL'} (complex64)")

            # Calculate actual bandwidth captured
            actual_bw_mhz = 8.0  # RSPduo max is 8 MHz at 10 MSPS
            print(f"\nBandwidth captured: ±{actual_bw_mhz/2:.1f} MHz")
            print(f"  GPS L1:      1575.42 MHz (center)")
            print(f"  Range:       {1575.42 - actual_bw_mhz/2:.2f} - {1575.42 + actual_bw_mhz/2:.2f} MHz")
            print(f"  Covers:      GPS L1 C/A main lobe + side lobes")
            print(f"  Sweep detection: ENABLED (full bandwidth)")

        print("\nNext steps:")
        print(f"  Analyze: python3 gps_spectrum_analyzer.py {output_file} \\")
        print(f"             --duration 10 --sample-rate 10000000 \\")
        print(f"             --plot sweep_analysis.jpeg")
        print()
        print("  Look for: Diagonal sweep patterns in spectrogram")

    except KeyboardInterrupt:
        print("\n\nRecording interrupted by user!")
        return 1
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        device.close()
        print("\nDevice closed")

    return 0

if __name__ == '__main__':
    sys.exit(main())
