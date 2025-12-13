#!/usr/bin/env python3
"""
GPS Spectrum Analyzer for Jamming Detection
Analyzes IQ recordings to detect Russian GPS jamming signatures

Detects:
- Sweep jammers: Linear frequency sweep through GPS band
- Pulsed jammers: On/off pattern (explains tracking loss)
- Noise jammers: Broadband noise floor elevation
- Meaconing: Fake GPS signals (sophisticated spoofing)

Usage:
    python3 gps_spectrum_analyzer.py <recording.dat> [options]

Author: Generated for Gdańsk GPS jamming analysis (Kaliningrad threat)
"""

import numpy as np
import argparse
import sys
import os
from datetime import datetime
import json

try:
    import matplotlib
    matplotlib.use('Agg')  # Non-interactive backend
    import matplotlib.pyplot as plt
    from matplotlib.gridspec import GridSpec
    PLOTTING_AVAILABLE = True
except ImportError:
    PLOTTING_AVAILABLE = False
    print("Warning: matplotlib not available, plots will be disabled")

try:
    from scipy import signal
    from scipy.fft import fft, fftfreq, fftshift
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False
    print("Warning: scipy not available, using numpy FFT")


class GPSSpectrumAnalyzer:
    """Analyzes GPS IQ samples for jamming signatures"""

    def __init__(self, sample_rate=2048000):
        self.sample_rate = sample_rate
        self.center_freq = 1575.42e6  # GPS L1
        self.gps_bandwidth = 2.046e6  # GPS C/A code bandwidth

    def load_samples(self, filename, max_samples=None, skip_seconds=0.3):
        """Load complex64 IQ samples from file"""
        print(f"Loading samples from: {filename}")

        # Calculate samples to skip (default: skip first 300ms for SDR settling)
        skip_samples = int(skip_seconds * self.sample_rate)

        # Read as complex64 (8 bytes per sample: 2x float32)
        # Skip initial samples by offsetting file pointer
        if max_samples is not None:
            max_samples += skip_samples  # Read extra to account for skip

        samples = np.fromfile(filename, dtype=np.complex64, count=max_samples)

        # Skip initial samples
        if len(samples) > skip_samples:
            samples = samples[skip_samples:]
            print(f"  Skipped first {skip_seconds * 1000:.0f} ms ({skip_samples:,} samples)")

        file_size = os.path.getsize(filename)
        duration = len(samples) / self.sample_rate

        print(f"  File size: {file_size / 1e9:.2f} GB")
        print(f"  Samples loaded: {len(samples):,}")
        print(f"  Duration: {duration:.1f} seconds")
        print(f"  Sample rate: {self.sample_rate / 1e6:.3f} MSPS")

        return samples

    def compute_spectrogram(self, samples, nperseg=2048, noverlap=None):
        """Compute spectrogram for time-frequency analysis"""
        if noverlap is None:
            noverlap = nperseg // 2

        print(f"\nComputing spectrogram...")
        print(f"  FFT size: {nperseg}")
        print(f"  Overlap: {noverlap}")

        if SCIPY_AVAILABLE:
            f, t, Sxx = signal.spectrogram(
                samples,
                fs=self.sample_rate,
                nperseg=nperseg,
                noverlap=noverlap,
                window='hann',
                return_onesided=False
            )
            # Shift to center DC
            f = fftshift(f)
            Sxx = fftshift(Sxx, axes=0)
        else:
            # Manual spectrogram using numpy
            hop_size = nperseg - noverlap
            num_frames = (len(samples) - nperseg) // hop_size + 1

            Sxx = np.zeros((nperseg, num_frames))
            t = np.arange(num_frames) * hop_size / self.sample_rate

            for i in range(num_frames):
                start = i * hop_size
                frame = samples[start:start + nperseg]
                if len(frame) == nperseg:
                    # Apply Hann window
                    windowed = frame * np.hanning(nperseg)
                    spectrum = np.abs(fft(windowed)) ** 2
                    Sxx[:, i] = fftshift(spectrum)

            f = fftshift(fftfreq(nperseg, 1/self.sample_rate))

        # Convert to dB
        Sxx_db = 10 * np.log10(Sxx + 1e-12)

        # Trim first 100ms of spectrogram to remove edge artifacts
        trim_time = 0.1  # 100ms
        trim_bins = int(trim_time * len(t) / (len(samples) / self.sample_rate))

        if trim_bins > 0 and trim_bins < len(t):
            t = t[trim_bins:]
            Sxx_db = Sxx_db[:, trim_bins:]
            print(f"  Trimmed first {trim_time * 1000:.0f} ms from spectrogram (edge artifacts)")

        print(f"  Time bins: {len(t)}")
        print(f"  Frequency bins: {len(f)}")

        return f, t, Sxx_db

    def detect_sweep_jammer(self, f, t, Sxx_db):
        """Detect linear frequency sweep (common Russian jammer)"""
        print("\n[1/4] Detecting SWEEP JAMMER...")

        # Look for linear frequency progression over time
        # Sweep jammers show diagonal lines in spectrogram

        detected = False
        sweep_rate = 0
        confidence = 0.0

        # Calculate power variation across frequency bins over time
        freq_variance = np.var(Sxx_db, axis=1)
        max_variance_idx = np.argmax(freq_variance)
        max_variance = freq_variance[max_variance_idx]

        # High variance in a frequency bin suggests sweeping
        if max_variance > 15:  # dB threshold
            # Estimate sweep rate by finding slope in spectrogram
            peak_freq_per_time = np.argmax(Sxx_db, axis=0)
            sweep_rate = np.polyfit(t, f[peak_freq_per_time], 1)[0]

            # Only consider it a sweep if there's actual frequency movement
            # Sweep rate should be > 10 kHz/s (otherwise it's likely pulse/noise jammer)
            if abs(sweep_rate) > 10000:  # 10 kHz/s minimum
                detected = True
                confidence = min(max_variance / 30, 1.0)

                print(f"  ✓ SWEEP DETECTED")
                print(f"    Confidence: {confidence * 100:.1f}%")
                print(f"    Sweep rate: {sweep_rate / 1e6:.3f} MHz/s")
            else:
                print(f"  ✗ No sweep pattern detected (high variance but no frequency movement)")
        else:
            print(f"  ✗ No sweep pattern detected")

        return {
            'detected': bool(detected),
            'confidence': float(confidence),
            'sweep_rate_hz_per_sec': float(sweep_rate),
            'type': 'LINEAR_SWEEP'
        }

    def detect_pulse_jammer(self, samples):
        """Detect pulsed jamming (on/off pattern)"""
        print("\n[2/4] Detecting PULSE JAMMER...")

        # Calculate instantaneous power
        power = np.abs(samples) ** 2

        # Smooth power envelope
        window_size = int(self.sample_rate * 0.001)  # 1ms window
        power_smooth = np.convolve(power, np.ones(window_size)/window_size, mode='same')

        # Detect sharp transitions
        power_diff = np.abs(np.diff(power_smooth))
        threshold = np.percentile(power_diff, 99)  # Top 1% of transitions

        pulses = power_diff > threshold
        num_pulses = np.sum(pulses)

        detected = False
        pulse_rate = 0
        duty_cycle = 0
        confidence = 0.0

        if num_pulses > 10:  # At least 10 pulses
            detected = True

            # Calculate pulse rate from total transitions
            # Each pulse cycle has 2 transitions (rising + falling edge)
            duration = len(samples) / self.sample_rate
            pulse_rate = (num_pulses / 2) / duration

            # Estimate duty cycle
            high_power = power_smooth > np.median(power_smooth)
            duty_cycle = np.sum(high_power) / len(high_power)

            confidence = min(num_pulses / 100, 1.0)

            print(f"  ✓ PULSE JAMMING DETECTED")
            print(f"    Confidence: {confidence * 100:.1f}%")
            print(f"    Pulse rate: {pulse_rate:.1f} Hz")
            print(f"    Duty cycle: {duty_cycle * 100:.1f}%")
            print(f"    Total pulses: {num_pulses}")
        else:
            print(f"  ✗ No pulse pattern detected")

        return {
            'detected': bool(detected),
            'confidence': float(confidence),
            'pulse_rate_hz': float(pulse_rate),
            'duty_cycle': float(duty_cycle),
            'num_pulses': int(num_pulses),
            'type': 'PULSE_JAMMER'
        }

    def detect_noise_jammer(self, samples):
        """Detect broadband noise jamming"""
        print("\n[3/4] Detecting NOISE JAMMER...")

        # Compute power spectral density
        if SCIPY_AVAILABLE:
            f, psd = signal.welch(samples, fs=self.sample_rate, nperseg=4096)
        else:
            spectrum = np.abs(fft(samples[:4096])) ** 2
            psd = spectrum / len(spectrum)
            f = fftfreq(len(spectrum), 1/self.sample_rate)

        psd_db = 10 * np.log10(psd + 1e-12)

        # Calculate flatness (noise should be flat across band)
        psd_variation = np.std(psd_db)
        noise_floor = np.median(psd_db)

        detected = False
        noise_floor_db = float(noise_floor)
        bandwidth_hz = 0
        confidence = 0.0

        # Flat spectrum with low variation = noise jammer
        if psd_variation < 5:  # Very flat spectrum
            detected = True
            confidence = min((5 - psd_variation) / 5, 1.0)

            # Calculate -3dB bandwidth
            threshold = noise_floor - 3
            above_threshold = psd_db > threshold
            bandwidth_hz = np.sum(above_threshold) * (self.sample_rate / len(psd_db))

            print(f"  ✓ NOISE JAMMING DETECTED")
            print(f"    Confidence: {confidence * 100:.1f}%")
            print(f"    Noise floor: {noise_floor_db:.1f} dBFS")
            print(f"    Bandwidth: {bandwidth_hz / 1e6:.3f} MHz")
            print(f"    Spectrum flatness: {psd_variation:.2f} dB")
        else:
            print(f"  ✗ No broadband noise detected")

        return {
            'detected': bool(detected),
            'confidence': float(confidence),
            'noise_floor_db': float(noise_floor_db),
            'bandwidth_hz': float(bandwidth_hz),
            'spectrum_flatness_db': float(psd_variation),
            'type': 'BROADBAND_NOISE'
        }

    def detect_meaconing(self, samples, f, t, Sxx_db):
        """Detect meaconing (GPS signal spoofing)"""
        print("\n[4/4] Detecting MEACONING/SPOOFING...")

        # Meaconing characteristics:
        # 1. Unusually strong signals (-100 dBm vs normal -130 dBm)
        # 2. Signals with zero Doppler shift (stationary transmitter)
        # 3. Multiple signals with identical time evolution

        detected = False
        num_signals = 0
        confidence = 0.0
        max_power_db = 0
        doppler_variation = 0

        # Calculate power in time domain
        power = np.abs(samples) ** 2
        avg_power = np.mean(power)
        max_power_dbfs = 10 * np.log10(avg_power + 1e-12)

        # Convert to estimated dBm (assuming 50 ohm, 0 dBFS = full scale)
        # For SDRplay, typical full scale is around -10 dBm
        max_power_db = max_power_dbfs + (-10)  # Approximate dBm

        # Check for abnormally strong signals
        # Real GPS satellites: -130 to -140 dBm
        # Spoofed signals: -90 to -110 dBm (much stronger)
        if max_power_db > -120:  # Stronger than normal GPS
            # Analyze frequency stability over time
            # Real satellites have changing Doppler (±5 kHz over time)
            # Spoofed signals from ground transmitter are static

            peak_freq_per_time = np.argmax(Sxx_db, axis=0)
            doppler_variation = np.std(f[peak_freq_per_time])

            # Low Doppler variation suggests stationary transmitter (spoofing)
            if doppler_variation < 1000:  # Less than 1 kHz variation
                detected = True

                # Higher confidence for stronger signals with static frequency
                power_factor = min((max_power_db + 130) / 30, 1.0)  # 0 at -130 dBm, 1 at -100 dBm
                static_factor = max(0, (1000 - doppler_variation) / 1000)  # 1 for zero Doppler
                confidence = min(power_factor * static_factor, 0.95)

                num_signals = 1  # At least one spoofed signal

                print(f"  ⚠️  MEACONING/SPOOFING DETECTED")
                print(f"    Confidence: {confidence * 100:.1f}%")
                print(f"    Signal power: {max_power_db:.1f} dBm (normal: -130 dBm)")
                print(f"    Doppler variation: {doppler_variation:.0f} Hz (normal: ±5000 Hz)")
                print(f"    ⚠️  Signals are unusually strong and stationary!")
                print(f"    ⚠️  Likely ground-based spoofing transmitter")
            else:
                print(f"  ✓ Strong signals but with normal Doppler variation")
        else:
            print(f"  ✓ No spoofing signatures detected")
            print(f"    Signal power: {max_power_db:.1f} dBm (normal GPS levels)")

        return {
            'detected': bool(detected),
            'confidence': float(confidence),
            'num_signals': int(num_signals),
            'signal_power_dbm': float(max_power_db),
            'doppler_variation_hz': float(doppler_variation),
            'type': 'MEACONING'
        }

    def generate_report(self, results, output_path):
        """Generate JSON report"""
        report = {
            'timestamp': datetime.now().isoformat(),
            'analysis': {
                'sample_rate': self.sample_rate,
                'center_frequency': self.center_freq,
                'location': 'Gdańsk, Poland',
                'threat_source': 'Russian military (Kaliningrad, ~150-200 km)',
            },
            'detections': results,
            'summary': {
                'jamming_detected': any(r['detected'] for r in results.values()),
                'primary_threat': max(results.keys(), key=lambda k: results[k]['confidence']),
                'max_confidence': max(r['confidence'] for r in results.values())
            }
        }

        with open(output_path, 'w') as f:
            json.dump(report, f, indent=2)

        print(f"\n✓ Report saved: {output_path}")
        return report


def main():
    parser = argparse.ArgumentParser(
        description='GPS Spectrum Analyzer for Jamming Detection',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Analyze full recording
  python3 gps_spectrum_analyzer.py recording.dat

  # Quick analysis (first 10 seconds)
  python3 gps_spectrum_analyzer.py recording.dat --duration 10

  # Save plots
  python3 gps_spectrum_analyzer.py recording.dat --plot output.png

Detection capabilities:
  ✓ Sweep jammers (Russian R-934BMV)
  ✓ Pulse jammers (explains tracking loss)
  ✓ Noise jammers (broadband)
  ✓ Meaconing (GPS spoofing)
        """
    )

    parser.add_argument('input_file', help='GPS IQ recording file (.dat)')
    parser.add_argument('-d', '--duration', type=float, help='Analyze first N seconds')
    parser.add_argument('-p', '--plot', type=str, help='Save spectrum plot to file')
    parser.add_argument('-o', '--output', type=str, help='JSON report output path')
    parser.add_argument('--sample-rate', type=float, default=2.048e6, help='Sample rate (default: 2.048 MSPS)')

    args = parser.parse_args()

    if not os.path.exists(args.input_file):
        print(f"Error: File not found: {args.input_file}")
        sys.exit(1)

    print("=" * 70)
    print("GPS SPECTRUM ANALYZER - JAMMING DETECTION")
    print("=" * 70)
    print(f"\nInput: {args.input_file}")
    print(f"Location context: Gdańsk, Poland")
    print(f"Known threat: Russian jamming from Kaliningrad (~150-200 km)")
    print("")

    # Initialize analyzer
    analyzer = GPSSpectrumAnalyzer(sample_rate=args.sample_rate)

    # Load samples
    max_samples = None
    if args.duration:
        max_samples = int(args.duration * args.sample_rate)

    samples = analyzer.load_samples(args.input_file, max_samples)

    # Compute spectrogram with very high frequency resolution
    # Use large FFT to resolve ~300 Hz wide GPS spectral lines
    # nperseg=65536 gives ~31 Hz bins (2.048 MHz / 65536)
    # This allows clear resolution of individual GPS signals
    f, t, Sxx_db = analyzer.compute_spectrogram(samples, nperseg=65536)

    # Run all detections
    results = {}
    results['sweep'] = analyzer.detect_sweep_jammer(f, t, Sxx_db)
    results['pulse'] = analyzer.detect_pulse_jammer(samples)
    results['noise'] = analyzer.detect_noise_jammer(samples)
    results['meaconing'] = analyzer.detect_meaconing(samples, f, t, Sxx_db)

    # Generate report
    output_path = args.output or args.input_file.replace('.dat', '_spectrum_analysis.json')
    report = analyzer.generate_report(results, output_path)

    # Print summary
    print("\n" + "=" * 70)
    print("DETECTION SUMMARY")
    print("=" * 70)

    for name, result in results.items():
        status = "✓ DETECTED" if result['detected'] else "✗ Not detected"
        confidence = result['confidence'] * 100
        print(f"{name.upper():15s}: {status:15s} ({confidence:5.1f}% confidence)")

    if report['summary']['jamming_detected']:
        print(f"\n⚠️  PRIMARY THREAT: {report['summary']['primary_threat'].upper()}")
    else:
        print(f"\n✓ No jamming detected (clean signal)")

    # Generate plot if requested
    if args.plot and PLOTTING_AVAILABLE:
        print(f"\nGenerating spectrum plot...")
        plot_spectrum(f, t, Sxx_db, results, args.plot)
        print(f"✓ Plot saved: {args.plot}")

    print("\n" + "=" * 70)


def plot_spectrum(f, t, Sxx_db, results, output_path):
    """Generate comprehensive spectrum analysis plot"""
    # Downsample spectrogram for faster plotting (keep every Nth point)
    downsample_factor = max(1, len(t) // 1000)  # Max 1000 time bins for full width
    t_ds = t[::downsample_factor]
    Sxx_db_ds = Sxx_db[:, ::downsample_factor]

    print(f"\nGenerating plot (downsampled {len(t)} → {len(t_ds)} time bins)...")

    # Improve dynamic range for better visibility of spectral lines
    # Clip to percentile range to avoid outliers compressing the scale
    vmin = np.percentile(Sxx_db_ds, 5)  # 5th percentile
    vmax = np.percentile(Sxx_db_ds, 99.5)  # 99.5th percentile

    # Create full-width figure with spectrogram on top
    fig = plt.figure(figsize=(16, 10))
    gs = GridSpec(4, 1, figure=fig, hspace=0.25, height_ratios=[3, 1, 1, 0.8])

    # Main spectrogram - FULL WIDTH with time horizontal
    ax1 = fig.add_subplot(gs[0, 0])
    # Use 'turbo' colormap for better visibility of spectral lines
    im = ax1.pcolormesh(t_ds, f / 1e6, Sxx_db_ds, shading='nearest',
                        cmap='turbo', vmin=vmin, vmax=vmax, rasterized=True)
    ax1.set_ylabel('Frequency offset (MHz)', fontsize=11)
    ax1.set_xlabel('Time (s)', fontsize=11)
    ax1.set_title(f'GPS L1 Spectrogram - Jamming Detection (Resolution: {f[1]-f[0]:.1f} Hz/bin)',
                  fontsize=13, fontweight='bold')
    cbar = plt.colorbar(im, ax=ax1, label='Power (dB)')
    cbar.set_label('Power (dB)', fontsize=10)

    # Detection indicators - top left corner
    detections_text = []
    for name, result in results.items():
        if result['detected']:
            detections_text.append(f"{name.upper()}: {result['confidence']*100:.0f}%")

    if detections_text:
        ax1.text(0.01, 0.99, '\n'.join(detections_text),
                transform=ax1.transAxes, fontsize=11,
                verticalalignment='top',
                bbox=dict(boxstyle='round', facecolor='red', alpha=0.8),
                color='white', fontweight='bold')

    # Average spectrum - FULL WIDTH below spectrogram
    ax2 = fig.add_subplot(gs[1, 0])
    avg_spectrum = np.mean(Sxx_db, axis=1)
    ax2.plot(f / 1e6, avg_spectrum, 'b-', linewidth=0.8)
    ax2.set_ylabel('Power (dB)', fontsize=10)
    ax2.set_xlabel('Frequency offset (MHz)', fontsize=10)
    ax2.set_title('Average Spectrum (time-averaged)', fontsize=11)
    ax2.grid(True, alpha=0.3)
    ax2.set_xlim(f[0] / 1e6, f[-1] / 1e6)

    # Time-domain power - FULL WIDTH
    ax3 = fig.add_subplot(gs[2, 0])
    time_power = np.mean(Sxx_db, axis=0)
    ax3.plot(t, time_power, 'r-', linewidth=0.8)
    ax3.set_ylabel('Power (dB)', fontsize=10)
    ax3.set_xlabel('Time (s)', fontsize=10)
    ax3.set_title('Average Power vs Time (frequency-averaged)', fontsize=11)
    ax3.grid(True, alpha=0.3)
    ax3.set_xlim(t[0], t[-1])

    # Detection metrics - compact summary
    ax4 = fig.add_subplot(gs[3, 0])
    ax4.axis('off')

    # Create compact one-line summary for each detection
    metrics_lines = []
    for name, result in results.items():
        if result['detected']:
            line = f"{name.upper()}: "
            if name == 'sweep' and 'sweep_rate_hz_per_sec' in result:
                line += f"{result['sweep_rate_hz_per_sec']/1e3:.1f} kHz/s"
            elif name == 'pulse' and 'pulse_rate_hz' in result:
                line += f"{result['pulse_rate_hz']:.1f} Hz, {result.get('duty_cycle', 0)*100:.0f}% duty"
            elif name == 'noise' and 'bandwidth_hz' in result:
                line += f"{result['bandwidth_hz']/1e6:.2f} MHz BW"
            elif name == 'meaconing' and 'signal_power_dbm' in result:
                line += f"{result['signal_power_dbm']:.1f} dBm"
            metrics_lines.append(line)

    if metrics_lines:
        metrics_text = "DETECTED THREATS: " + " | ".join(metrics_lines)
    else:
        metrics_text = "No jamming detected - Clean GPS signal"

    ax4.text(0.5, 0.5, metrics_text,
            transform=ax4.transAxes, fontsize=10,
            verticalalignment='center', horizontalalignment='center',
            bbox=dict(boxstyle='round', facecolor='yellow' if metrics_lines else 'lightgreen', alpha=0.7),
            fontweight='bold')

    plt.savefig(output_path, dpi=200, bbox_inches='tight')
    plt.close()


if __name__ == '__main__':
    main()
