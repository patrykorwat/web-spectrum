#!/usr/bin/env python3
"""
Record IQ Samples from SDRPlay to File

Records GPS L1 IQ samples for processing with GNSS-SDR
"""

import SoapySDR
import numpy as np
import sys
import time

def record_samples(output_file, duration_seconds=60, continuous=False):
    """Record IQ samples to file

    Args:
        output_file: Path to output file
        duration_seconds: Duration in seconds (ignored if continuous=True)
        continuous: If True, record continuously until interrupted
    """

    print("=" * 70)
    print("SDRPlay IQ Sample Recorder")
    print("=" * 70)
    print(f"\nOutput file: {output_file}")
    if continuous:
        print(f"Mode: CONTINUOUS (recording until stopped)")
    else:
        print(f"Duration: {duration_seconds} seconds")
    print(f"Frequency: 1575.42 MHz (GPS L1)")
    print(f"Sample rate: 2.048 MSPS")
    print("")

    # Find and open SDRPlay
    results = SoapySDR.Device.enumerate("driver=sdrplay")
    if not results:
        print("❌ No SDRPlay devices found!")
        sys.exit(1)

    print(f"✓ Found {len(results)} SDRPlay device(s)")

    # Open device (Single Tuner mode)
    sdr = SoapySDR.Device(results[0])
    print("✓ Opened SDRPlay device")

    # Configure
    sdr.setAntenna(SoapySDR.SOAPY_SDR_RX, 0, "Tuner 2 50 ohm")
    sdr.setSampleRate(SoapySDR.SOAPY_SDR_RX, 0, 2.048e6)
    sdr.setFrequency(SoapySDR.SOAPY_SDR_RX, 0, 1575.42e6)
    sdr.setGainMode(SoapySDR.SOAPY_SDR_RX, 0, False)
    sdr.setGain(SoapySDR.SOAPY_SDR_RX, 0, 40)

    # Enable bias-T for active antenna
    try:
        sdr.writeSetting("biasT_ctrl", "true")
        print("✓ Bias-T enabled")
    except:
        pass

    print("✓ Configuration complete")
    print("")

    # Open output file
    with open(output_file, 'wb') as f:
        # Setup stream
        stream = sdr.setupStream(SoapySDR.SOAPY_SDR_RX, SoapySDR.SOAPY_SDR_CF32)
        sdr.activateStream(stream)

        if continuous:
            print("🎙️  Recording continuously (Ctrl+C to stop)...")
        else:
            print("🎙️  Recording...")
        print("")

        buffer_size = 8192
        buff = np.zeros(buffer_size, dtype=np.complex64)

        total_samples = 0
        start_time = time.time()
        last_update = time.time()

        try:
            while continuous or (time.time() - start_time) < duration_seconds:
                sr = sdr.readStream(stream, [buff], len(buff), timeoutUs=1000000)

                if sr.ret > 0:
                    # Write to file (gr_complex format)
                    f.write(buff[:sr.ret].tobytes())
                    f.flush()  # Flush to disk for continuous reading
                    total_samples += sr.ret

                    # Update every second
                    now = time.time()
                    if now - last_update >= 1.0:
                        elapsed = now - start_time

                        if continuous:
                            print(f"\r[{elapsed:.0f}s] "
                                  f"{total_samples / 1e6:.1f} MSamples | "
                                  f"{(total_samples / elapsed) / 1e6:.2f} MSPS",
                                  end='', flush=True)
                        else:
                            remaining = duration_seconds - elapsed
                            progress = (elapsed / duration_seconds) * 100
                            print(f"\r[{elapsed:.0f}s / {duration_seconds}s] "
                                  f"{progress:.0f}% complete | "
                                  f"{total_samples / 1e6:.1f} MSamples",
                                  end='', flush=True)

                        last_update = now

        except KeyboardInterrupt:
            print("\n\n⏹️  Recording stopped by user")

        # Cleanup
        sdr.deactivateStream(stream)
        sdr.closeStream(stream)

        # Disable bias-T
        try:
            sdr.writeSetting("biasT_ctrl", "false")
        except:
            pass

    elapsed = time.time() - start_time
    file_size_mb = total_samples * 8 / 1e6  # Complex64 = 8 bytes per sample

    print(f"\n\n✅ Recording complete!")
    print(f"   Samples: {total_samples / 1e6:.1f} MSamples")
    print(f"   Duration: {elapsed:.1f} seconds")
    print(f"   File size: {file_size_mb:.1f} MB")
    print("")

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Record IQ samples from SDRPlay')
    parser.add_argument('output_file', nargs='?', default='/tmp/gps_iq_samples.dat',
                        help='Output file path (default: /tmp/gps_iq_samples.dat)')
    parser.add_argument('duration', type=int, nargs='?', default=60,
                        help='Duration in seconds (default: 60)')
    parser.add_argument('--continuous', '-c', action='store_true',
                        help='Record continuously until stopped (Ctrl+C)')
    args = parser.parse_args()

    record_samples(args.output_file, args.duration, continuous=args.continuous)
