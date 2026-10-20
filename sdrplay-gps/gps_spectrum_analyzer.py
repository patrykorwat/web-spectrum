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

Author: GPS Spectrum Analyzer for GNSS jamming detection
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

    def __init__(self, sample_rate=2048000):  # Default to 2.048 MSPS for GPS L1 main lobe
        self.sample_rate = sample_rate
        self.center_freq = 1575.42e6  # GPS L1
        self.gps_bandwidth = 2.046e6  # GPS L1 C/A main lobe (±1.023 MHz from center)

    def load_samples(self, filename, max_samples=None, skip_seconds=0.3):
        """Load complex64 IQ samples from file"""
        print(f"Loading samples from: {filename}")

        # Calculate samples to skip (default: skip first 300ms for SDR settling)
        skip_samples = int(skip_seconds * self.sample_rate)

        # Read as complex64 (8 bytes per sample: 2x float32)
        # Skip initial samples by offsetting file pointer
        read_count = -1  # -1 means read all samples
        if max_samples is not None:
            read_count = max_samples + skip_samples  # Read extra to account for skip

        samples = np.fromfile(filename, dtype=np.complex64, count=read_count)

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

    def compute_spectrogram(self, samples, nperseg=2048, noverlap=None, n_jobs=-1):
        """Compute spectrogram for time-frequency analysis with multi-core support

        Args:
            samples: IQ samples
            nperseg: FFT size
            noverlap: Overlap samples
            n_jobs: Number of parallel jobs (-1 = all cores, 1 = sequential)
        """
        if noverlap is None:
            noverlap = nperseg // 2

        print(f"\nComputing spectrogram...")
        print(f"  FFT size: {nperseg}")
        print(f"  Overlap: {noverlap}")

        # Enable numpy multithreading for FFT operations
        import os
        if n_jobs == -1:
            n_cores = os.cpu_count() or 1
        else:
            n_cores = max(1, n_jobs)

        # Set environment variables for numpy/scipy BLAS threading
        os.environ['OMP_NUM_THREADS'] = str(n_cores)
        os.environ['OPENBLAS_NUM_THREADS'] = str(n_cores)
        os.environ['MKL_NUM_THREADS'] = str(n_cores)
        os.environ['NUMEXPR_NUM_THREADS'] = str(n_cores)

        print(f"  Using {n_cores} CPU cores for parallel processing")

        if SCIPY_AVAILABLE:
            import time
            start_time = time.time()

            f, t, Sxx = signal.spectrogram(
                samples,
                fs=self.sample_rate,
                nperseg=nperseg,
                noverlap=noverlap,
                window='boxcar',  # Rectangular window for best narrow-line resolution
                return_onesided=False
            )

            elapsed = time.time() - start_time
            print(f"  Spectrogram computed in {elapsed:.1f} seconds")

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
                    spectrum = np.abs(np.fft.fft(windowed)) ** 2
                    Sxx[:, i] = np.fft.fftshift(spectrum)

            f = np.fft.fftshift(np.fft.fftfreq(nperseg, 1/self.sample_rate))

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
        """Detect linear frequency sweep (diagonal line in the spectrogram).

        The previous version triggered on the variance of a single frequency
        bin across time. With a boxcar window every bin is a single-look
        chi-square estimate, so its dB-space variance is ~31 dB^2 even on
        clean noise - the old 15 dB^2 threshold fired on EVERY recording
        (saved JSONs show "sweep detected" with invented sweep rates).
        This version requires a COHERENT diagonal track: the per-frame peak
        frequency must follow a straight line with small residuals.
        """
        print("\n[1/4] Detecting SWEEP JAMMER...")

        detected = False
        sweep_rate = 0.0
        confidence = 0.0
        residual_hz = 0.0

        if len(t) >= 10:
            # Strongest frequency bin in each time frame
            peak_bins = np.argmax(Sxx_db, axis=0)
            peak_freqs = f[peak_bins]

            # Linear fit through the peak track
            coeffs = np.polyfit(t, peak_freqs, 1)
            sweep_rate = float(coeffs[0])
            residual_hz = float(np.std(peak_freqs - np.polyval(coeffs, t)))
            bin_hz = float(abs(f[1] - f[0])) if len(f) > 1 else self.sample_rate

            # Real sweep: the track hugs the line (within a few bins) and moves
            # > 10 kHz/s. Random peak jumps produce huge residuals; a stationary
            # CW tone gives a flat track (slope ~ 0).
            if abs(sweep_rate) > 10e3 and residual_hz < 5 * bin_hz:
                detected = True
                confidence = float(min(max(1.0 - residual_hz / (10 * bin_hz), 0.1), 1.0))
                print("  \u2713 SWEEP DETECTED")
                print(f"    Confidence: {confidence * 100:.1f}%")
                print(f"    Sweep rate: {sweep_rate / 1e6:.3f} MHz/s (track residual {residual_hz / 1e3:.1f} kHz)")
            else:
                print(f"  \u2717 No sweep pattern detected (rate {sweep_rate / 1e3:.1f} kHz/s, track residual {residual_hz / 1e3:.1f} kHz)")
        else:
            print("  \u2717 No sweep pattern detected (too few time frames)")

        return {
            'detected': bool(detected),
            'confidence': float(confidence),
            'sweep_rate_hz_per_sec': float(sweep_rate),
            'track_residual_hz': float(residual_hz),
            'type': 'LINEAR_SWEEP'
        }

    def detect_pulse_jammer(self, samples, verbose=True, time_series=None):
        """Detect pulsed jamming (on/off pattern) with periodicity validation.

        The previous version flagged the top 1% of power transitions as
        "pulses", which fires even on clean Gaussian noise (it always finds
        ~1% of samples above the 99th percentile). This version requires
        actual PERIODICITY: the envelope is thresholded at a fixed level
        above its median and autocorrelated. A real pulsed jammer produces
        a strong autocorrelation peak at the pulse period; random noise
        does not.

        If time_series is a list, per-0.5s-segment (noise floor, p90, ACF
        peak) rows are appended for charting (e.g. YouTube video plots).
        """
        # Envelope: non-overlapping 200 us boxcar average of instantaneous
        # power (O(n), no aliasing issues for on/off envelopes <= ~1 kHz)
        power = np.abs(samples) ** 2
        win = max(1, int(self.sample_rate * 0.0002))  # 200 us boxcar
        nwin = (len(power) // win) * win
        env_rate = self.sample_rate / win  # ~5 kHz envelope rate
        if nwin == 0:
            if time_series is not None:
                time_series.append({'t': 0.0, 'nf': float('nan'), 'p90': float('nan'), 'acf': 0.0, 'rate': 0.0})
            return {'detected': False, 'confidence': 0.0, 'pulse_rate_hz': 0.0,
                    'duty_cycle': 0.0, 'num_pulses': 0, 'acf_peak': 0.0, 'type': 'PULSE_JAMMER'}
        env = power[:nwin].reshape(-1, win).mean(axis=1)
        env_db = 10.0 * np.log10(env + 1e-12)

        detected = False
        pulse_rate = 0.0
        duty_cycle = 0.0
        confidence = 0.0
        num_pulses = 0
        acf_peak = 0.0

        # Noise-floor / ACF time series (one row per 0.5 s, 50% overlap)
        if time_series is not None:
            seg_env = max(1, int(0.5 * env_rate))
            hop_env = seg_env // 2
            for i in range(0, max(1, len(env_db) - seg_env + 1), hop_env):
                chunk = env_db[i:i + seg_env]
                if len(chunk) < seg_env // 2:
                    break
                t_s = (i * win) / self.sample_rate
                time_series.append({
                    't': t_s,
                    'nf': float(np.median(chunk)),
                    'p90': float(np.percentile(chunk, 90)),
                    'acf': 0.0,
                    'rate': 0.0,
                })

        # On/off waveform: 6 dB above the median envelope level
        thresh = np.median(env_db) + 6.0
        onoff = (env_db > thresh).astype(np.float64)

        if 0.02 < onoff.mean() < 0.98:
            # Autocorrelation via FFT (O(n log n))
            x = onoff - onoff.mean()
            spec = np.fft.rfft(x, 2 * len(x))
            acf = np.fft.irfft(spec * np.conj(spec), 2 * len(x))[:len(x)]
            acf /= (acf[0] + 1e-12)
            # Skip the first 1 ms (trivially high correlation), search
            # periods down to 20 Hz
            min_lag = max(2, int(0.001 * env_rate))
            max_lag = min(len(acf) - 1, max(min_lag + 1, int(env_rate / 20)))
            seg = acf[min_lag:max_lag]
            k = int(np.argmax(seg)) + min_lag
            acf_peak = float(acf[k])
            # ACF peaks repeat at every multiple of the true period; take the
            # FIRST lag within 10% of the best peak so the fundamental period
            # wins over 2T/3T harmonics (argmax alone can pick 2T).
            for cand in range(min_lag, k + 1):
                if acf[cand] >= 0.9 * acf_peak:
                    k = cand
                    acf_peak = float(acf[k])
                    break
            if acf_peak > 0.5:
                detected = True
                pulse_rate = float(env_rate / k)
                duty_cycle = float(onoff.mean())
                period_s = k / env_rate
                num_pulses = int(round((len(env) / env_rate) / period_s))
                # Confidence: ACF contrast vs its own noise floor
                ref = float(np.median(seg))
                confidence = float(min(max((acf_peak - ref) / max(1.0 - ref, 1e-6), 0.0), 1.0))
                if time_series is not None:
                    # Annotate the series with the global pulse metrics
                    for row in time_series:
                        row['acf'] = acf_peak
                        row['rate'] = pulse_rate

        if verbose:
            if detected:
                print(f"  ✓ PULSE JAMMING DETECTED (periodic)")
                print(f"    Confidence: {confidence * 100:.1f}%")
                print(f"    Pulse rate: {pulse_rate:.1f} Hz (ACF peak {acf_peak:.2f})")
                print(f"    Duty cycle: {duty_cycle * 100:.1f}%")
                print(f"    Total pulses: ~{num_pulses}")
            else:
                print(f"  ✗ No periodic pulse pattern detected (ACF peak {acf_peak:.2f})")

        return {
            'detected': bool(detected),
            'confidence': float(confidence),
            'pulse_rate_hz': float(pulse_rate),
            'duty_cycle': float(duty_cycle),
            'num_pulses': int(num_pulses),
            'acf_peak': float(acf_peak),
            'type': 'PULSE_JAMMER'
        }

    def detect_noise_jammer(self, samples, baseline_file=None, verbose=True):
        """Detect broadband noise jamming.

        Improvements over the previous version:
        - Flatness is measured over the central 1.5 MHz only (filter roll-off
          at the band edges used to inflate std and mask real jammers).
        - Narrow spectral lines (>10 dB above the local median) are excluded
          before the statistics: GPS satellites and CW tones are spikes, not
          noise, and they used to hide a flat, elevated noise floor.
        - Optional baseline recording: reports the delta of the noise floor
          vs the reference - the reliable, calibration-free jamming metric.
        """
        print("\n[3/4] Detecting NOISE JAMMER...")

        def band_stats(iq):
            if SCIPY_AVAILABLE:
                fb, psd = signal.welch(iq, fs=self.sample_rate, nperseg=4096)
            else:
                # Manual Welch: average several periodograms. A single 4096-point
                # periodogram has chi-square fluctuation (std ~5.6 dB after the
                # log), which would swamp the flatness test.
                nseg_fb = max(1, min(64, len(iq) // 4096))
                segs = iq[:nseg_fb * 4096].reshape(nseg_fb, 4096)
                spec = np.abs(np.fft.fft(segs, axis=1)) ** 2
                psd = np.fft.fftshift(spec.mean(axis=0) / 4096.0)
                fb = np.fft.fftshift(np.fft.fftfreq(4096, 1/self.sample_rate))
            pdb = 10 * np.log10(psd + 1e-12)
            center = (fb >= -0.75e6) & (fb <= 0.75e6)
            band = pdb[center] if center.any() else pdb
            local_med = float(np.median(band))
            flat = band[band < local_med + 10.0]  # exclude narrow spectral lines
            if flat.size < 10:
                flat = band
            floor = float(np.median(flat))
            variation = float(np.std(flat))
            bw = float(np.sum(band > (floor - 3.0)) * (self.sample_rate / len(pdb)))
            return floor, variation, bw

        noise_floor, psd_variation, bandwidth_hz = band_stats(samples)

        detected = False
        confidence = 0.0
        delta_db = None
        baseline_flatness = None

        if baseline_file and os.path.exists(baseline_file):
            try:
                base_samples = self.load_samples(baseline_file, max_samples=len(samples))
                base_floor, base_var, _ = band_stats(base_samples)
                delta_db = noise_floor - base_floor
                baseline_flatness = base_var
                # A real broadband jammer lifts the floor across the WHOLE band
                # while the spectrum stays flat. +5 dB delta with low flatness
                # is a strong, calibration-free indicator.
                if delta_db >= 5.0 and psd_variation < 3.0:
                    detected = True
                    confidence = float(min((delta_db - 5.0) / 15.0 + 0.3, 1.0))
                if verbose:
                    print(f"    Baseline floor: {base_floor:.1f} dBFS (flatness {base_var:.2f} dB)")
                    print(f"    Delta vs baseline: {delta_db:+.1f} dB")
            except Exception as exc:
                if verbose:
                    print(f"    Baseline analysis failed: {exc}")

        # Without a baseline a flat band alone is NOT evidence of jamming:
        # thermal noise is flat too. Require the delta-vs-baseline evidence;
        # otherwise report metrics only (no false alarms on clean recordings).
        note = None
        if not detected and not baseline_file:
            note = ('flat band is not evidence of jamming by itself; '
                    'record a quiet reference and rerun with --baseline')
            if verbose:
                print(f"  ~ Flat spectrum ({psd_variation:.2f} dB) but no baseline - not flagged")
                print(f"    ({note})")

        if verbose:
            if detected:
                print("  \u2713 NOISE JAMMING DETECTED")
                print(f"    Confidence: {confidence * 100:.1f}%")
                print(f"    Noise floor: {noise_floor:.1f} dBFS")
                print(f"    Bandwidth: {bandwidth_hz / 1e6:.3f} MHz")
                print(f"    Spectrum flatness: {psd_variation:.2f} dB")
            else:
                print("  \u2717 No broadband noise detected")

        return {
            'detected': bool(detected),
            'confidence': float(confidence),
            'noise_floor_db': float(noise_floor),
            'bandwidth_hz': float(bandwidth_hz),
            'spectrum_flatness_db': float(psd_variation),
            'delta_vs_baseline_db': (float(delta_db) if delta_db is not None else None),
            'baseline_flatness_db': (float(baseline_flatness) if baseline_flatness is not None else None),
            'note': note,
            'type': 'BROADBAND_NOISE'
        }

    def detect_narrowband_signals(self, f, t, Sxx_db):
        """Detect narrow-band continuous wave (CW) signals (50-500 Hz wide)"""
        print("\n[4/5] Detecting NARROW-BAND SIGNALS...")

        # Use MAXIMUM spectrum across time to catch intermittent narrow-band features
        # This prevents time-averaging from washing out narrow lines
        avg_spectrum = np.max(Sxx_db, axis=1)

        print(f"  Using MAX across {len(t)} time bins (catches intermittent lines)")

        # Calculate noise floor from average spectrum (not max)
        mean_spectrum = np.mean(Sxx_db, axis=1)
        noise_floor = np.percentile(mean_spectrum, 25)

        # Find peaks above noise floor - LOWERED threshold for weak lines
        threshold = noise_floor + 6  # 6 dB above noise floor (was 10 dB)

        # Detect peaks using simple derivative method
        peaks = []
        for i in range(1, len(avg_spectrum) - 1):
            if avg_spectrum[i] > threshold:
                # Check if it's a local maximum
                if avg_spectrum[i] > avg_spectrum[i-1] and avg_spectrum[i] > avg_spectrum[i+1]:
                    # Estimate bandwidth by finding -3dB points
                    peak_power = avg_spectrum[i]
                    bw_threshold = peak_power - 3

                    # Find left edge
                    left_idx = i
                    while left_idx > 0 and avg_spectrum[left_idx] > bw_threshold:
                        left_idx -= 1

                    # Find right edge
                    right_idx = i
                    while right_idx < len(avg_spectrum) - 1 and avg_spectrum[right_idx] > bw_threshold:
                        right_idx += 1

                    # Calculate bandwidth
                    freq_res = f[1] - f[0]
                    bandwidth_hz = (right_idx - left_idx) * freq_res

                    # Only consider narrow-band signals (30 Hz to 2 kHz)
                    # Accept very narrow lines down to 30 Hz (captures 50 Hz wide lines)
                    if 30 < bandwidth_hz < 2000:
                        peaks.append({
                            'freq_hz': float(f[i]),
                            'freq_mhz': float(f[i] / 1e6),
                            'power_db': float(avg_spectrum[i]),
                            'bandwidth_hz': float(bandwidth_hz),
                            'snr_db': float(avg_spectrum[i] - noise_floor)
                        })

        # Sort by power
        peaks.sort(key=lambda x: x['power_db'], reverse=True)

        # Keep top 50 strongest peaks (increased to capture more narrow lines)
        peaks = peaks[:50]

        detected = len(peaks) > 0
        confidence = min(len(peaks) / 10.0, 1.0) if detected else 0.0

        if detected:
            print(f"  ✓ NARROW-BAND SIGNALS DETECTED: {len(peaks)} lines")
            print(f"    Confidence: {confidence * 100:.1f}%")
            for i, peak in enumerate(peaks[:5], 1):  # Show top 5
                print(f"    #{i}: {peak['freq_mhz']:+.6f} MHz, "
                      f"BW={peak['bandwidth_hz']:.0f} Hz, "
                      f"SNR={peak['snr_db']:.1f} dB")
            if len(peaks) > 5:
                print(f"    ... and {len(peaks) - 5} more")
        else:
            print(f"  ✗ No narrow-band signals detected")

        return {
            'detected': bool(detected),
            'confidence': float(confidence),
            'num_signals': len(peaks),
            'peaks': peaks,
            'type': 'NARROWBAND_CW'
        }

    def detect_meaconing(self, samples, f, t, Sxx_db):
        """Detect meaconing (GPS signal spoofing)"""
        print("\n[5/5] Detecting MEACONING/SPOOFING...")

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

    def generate_report(self, results, output_path, time_series=None, baseline_file=None):
        """Generate JSON report"""
        analysis = {
            'sample_rate': self.sample_rate,
            'center_frequency': self.center_freq,
        }
        if baseline_file:
            analysis['baseline'] = os.path.basename(baseline_file)
        report = {
            'timestamp': datetime.now().isoformat(),
            'analysis': analysis,
            'detections': results,
            'summary': {
                'jamming_detected': any(r['detected'] for r in results.values()),
                'primary_threat': max(results.keys(), key=lambda k: results[k]['confidence']),
                'max_confidence': max(r['confidence'] for r in results.values())
            }
        }
        if time_series:
            report['time_series'] = time_series

        with open(output_path, 'w') as fh:
            json.dump(report, fh, indent=2)

        print(f"\n\u2713 Report saved: {output_path}")
        return report



def main():
    parser = argparse.ArgumentParser(
        description='GPS Spectrum Analyzer for Jamming Detection',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Using suffix (auto-finds file in recordings/)
  python3 gps_spectrum_analyzer.py --suffix 20251213_231434 --duration 10 --plot out.png

  # Using full file path
  python3 gps_spectrum_analyzer.py recording.dat --duration 10

  # Quick analysis with suffix
  python3 gps_spectrum_analyzer.py -s 20251213_231434 -d 10 -p output.png

Detection capabilities:
  ✓ Sweep jammers (Russian R-934BMV)
  ✓ Pulse jammers (explains tracking loss)
  ✓ Noise jammers (broadband)
  ✓ Meaconing (GPS spoofing)
        """
    )

    parser.add_argument('input_file', nargs='?', help='GPS IQ recording file (.dat)')
    parser.add_argument('-s', '--suffix', type=str, help='Suffix for .dat file in recordings/ directory (e.g., "20251213_231434" for gps_recording_20251213_231434.dat)')
    parser.add_argument('-d', '--duration', type=float, help='Analyze first N seconds')
    parser.add_argument('-p', '--plot', type=str, help='Save spectrum plot to file')
    parser.add_argument('-o', '--output', type=str, help='JSON report output path')
    parser.add_argument('--sample-rate', type=float, default=2.048e6, help='Sample rate (default: 2.048 MSPS for GPS L1 main lobe)')
    parser.add_argument('-b', '--baseline', type=str, help='Baseline (reference) IQ recording of the SAME site/antenna for delta noise-floor measurement')

    args = parser.parse_args()

    # Determine input file path
    if args.suffix:
        # Construct path from suffix
        script_dir = os.path.dirname(os.path.abspath(__file__))
        input_file = os.path.join(script_dir, 'recordings', f'gps_recording_{args.suffix}.dat')
    elif args.input_file:
        input_file = args.input_file
    else:
        parser.error("Either input_file or --suffix must be provided")

    if not os.path.exists(input_file):
        print(f"Error: File not found: {input_file}")
        sys.exit(1)

    print("=" * 70)
    print("GPS SPECTRUM ANALYZER - JAMMING DETECTION")
    print("=" * 70)
    print(f"\nInput: {input_file}")
    print("")

    # Initialize analyzer
    analyzer = GPSSpectrumAnalyzer(sample_rate=args.sample_rate)

    # Load samples
    max_samples = None
    if args.duration:
        max_samples = int(args.duration * args.sample_rate)

    samples = analyzer.load_samples(input_file, max_samples)

    # Optional baseline (reference) recording for delta measurement
    baseline_file = None
    if args.baseline:
        if os.path.exists(args.baseline):
            baseline_file = args.baseline
        else:
            print(f"Warning: baseline file not found: {args.baseline} - continuing without it")

    # Compute spectrogram optimized for 10 MSPS data with multi-core processing
    # MEMORY-OPTIMIZED SETTINGS for 60-second recordings:
    # nperseg=2048 gives ~4.88 kHz bins (10 MHz / 2048) - adequate frequency resolution
    # noverlap=1024 (50% overlap) gives smooth time resolution with LOW memory usage
    # Hop size = 1024 samples = 0.1ms time steps - fast processing, good quality
    # 60 seconds = 600M samples ÷ 1024 hop × 2048 FFT = ~117 MB (vs 960 MB with old settings!)
    # Multi-core FFT processing enabled (uses all CPU cores)
    print(f"\n{'='*70}")
    print(f"STARTING PARALLEL SPECTROGRAM COMPUTATION (MEMORY-OPTIMIZED)")
    print(f"{'='*70}")
    f, t, Sxx_db = analyzer.compute_spectrogram(samples, nperseg=2048, noverlap=1024, n_jobs=-1)

    # Run all detections
    time_series = []  # per-0.5s noise floor / envelope rows for charting
    results = {}
    results['sweep'] = analyzer.detect_sweep_jammer(f, t, Sxx_db)
    results['pulse'] = analyzer.detect_pulse_jammer(samples, time_series=time_series)
    results['noise'] = analyzer.detect_noise_jammer(samples, baseline_file=baseline_file)
    results['narrowband'] = analyzer.detect_narrowband_signals(f, t, Sxx_db)
    results['meaconing'] = analyzer.detect_meaconing(samples, f, t, Sxx_db)

    # Generate report
    # Generate report
    output_path = args.output or input_file.replace('.dat', '_spectrum_analysis.json')
    report = analyzer.generate_report(results, output_path, time_series=time_series, baseline_file=baseline_file)

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

    # Generate plots if requested
    if args.plot and PLOTTING_AVAILABLE:
        try:
            print(f"\nGenerating GPS main lobe spectrum plot (skip full spectrum for speed)...")

            # Generate ONLY main lobe zoom plot using existing spectrogram
            # Show GPS L1 C/A main lobe: ±1.023 MHz (2.046 MHz total bandwidth)
            # This includes: spectrogram + average spectrum + average power vs time (3-panel view)

            # Generate main lobe plot: ±1.023 MHz centered at DC (no offset), show all time
            plot_narrowband_zoom(f, t, Sxx_db, args.plot,
                               zoom_bw=2.046e6, freq_offset=0, time_duration=None)
            print(f"✓ GPS main lobe plot saved: {args.plot}")
            print(f"  (Skipped full spectrum plot for faster processing)")
        except Exception as e:
            print(f"✗ ERROR generating plot: {e}")
            import traceback
            traceback.print_exc()

    print("\n" + "=" * 70)


def plot_narrowband_zoom(f, t, Sxx_db, output_path, zoom_bw=200e3, time_duration=None, freq_offset=0):
    """Generate narrowband zoom plot (like SDRconnect zoomed view)"""
    print(f"\nGenerating narrowband zoom plot (±{zoom_bw/2e3:.0f} kHz, offset: {freq_offset/1e3:.0f} kHz)...")

    # Find frequency indices for zoom region (center + offset ±zoom_bw/2)
    center_idx = len(f) // 2
    # Apply frequency offset
    offset_bins = int(freq_offset / (f[1] - f[0]))
    center_idx += offset_bins

    bw_bins = int(zoom_bw / (f[1] - f[0]))
    start_idx = max(0, center_idx - bw_bins // 2)
    end_idx = min(len(f), center_idx + bw_bins // 2)

    # Crop to narrowband region
    f_zoom = f[start_idx:end_idx]
    Sxx_zoom = Sxx_db[start_idx:end_idx, :]

    # Optionally crop time axis to specific duration
    if time_duration is not None and len(t) > 0:
        max_time = min(time_duration, t[-1])
        time_mask = t <= max_time
        t_zoom = t[time_mask]
        Sxx_zoom = Sxx_zoom[:, time_mask]
        print(f"  Time cropped to {max_time:.1f} seconds ({len(t_zoom)} bins)")
    else:
        t_zoom = t

    # Decimate time axis if too many bins (speeds up plotting dramatically!)
    # Matplotlib struggles with >10k time bins - downsample to ~2000 bins max
    max_plot_bins = 2000
    if len(t_zoom) > max_plot_bins:
        decimate_factor = len(t_zoom) // max_plot_bins
        t_zoom = t_zoom[::decimate_factor]
        Sxx_zoom = Sxx_zoom[:, ::decimate_factor]
        print(f"  Decimated time axis by {decimate_factor}× to {len(t_zoom)} bins for faster plotting")

    # Enhanced contrast for subtle line visibility
    # Narrow dynamic range to emphasize weak spectral lines
    vmin = np.percentile(Sxx_zoom, 60)  # Higher floor to suppress noise
    vmax = vmin + 8  # Very narrow 8 dB range to highlight subtle features

    print(f"  Zoomed region: {f_zoom[0]/1e3:.1f} to {f_zoom[-1]/1e3:.1f} kHz")
    print(f"  Frequency bins: {len(f_zoom)}")
    print(f"  Time bins: {len(t_zoom)}")
    print(f"  Time span: {t_zoom[-1] if len(t_zoom) > 0 else 0:.1f} seconds")
    print(f"  Dynamic range: {vmin:.1f} to {vmax:.1f} dB")
    print(f"  Frequency resolution: {f[1]-f[0]:.1f} Hz/bin")

    # Create multi-panel plot like comprehensive view
    fig = plt.figure(figsize=(20, 14), dpi=150)
    from matplotlib.gridspec import GridSpec
    gs = GridSpec(3, 1, figure=fig, hspace=0.3, height_ratios=[6, 1, 1])

    # Dark background for better contrast with colorful spectrum
    fig.patch.set_facecolor('#0a0a0a')

    # Main spectrogram panel
    ax1 = fig.add_subplot(gs[0, 0])
    ax1.set_facecolor('#1a1a1a')

    # Use 'gouraud' shading for smooth, anti-aliased appearance (no pixelation)
    # This interpolates between data points for a continuous look
    # Use 'viridis' colormap - gentle, perceptually uniform, great for subtle features
    # Dark blue background shows noise floor, bright yellow highlights lines
    im = ax1.pcolormesh(t_zoom, f_zoom / 1e3, Sxx_zoom, shading='gouraud',
                       cmap='viridis', vmin=vmin, vmax=vmax, rasterized=False)

    ax1.set_ylabel('Frequency offset (kHz)', fontsize=14, fontweight='bold', color='white')
    ax1.set_xlabel('Time (s)', fontsize=14, fontweight='bold', color='white')
    time_duration_str = f"{t_zoom[-1]:.1f}s" if len(t_zoom) > 0 else "N/A"
    offset_str = f"+{freq_offset/1e3:.0f} kHz " if freq_offset != 0 else ""
    ax1.set_title(f'Narrowband Zoom: {offset_str}±{zoom_bw/2e3:.0f} kHz | {time_duration_str} | Resolution: {f[1]-f[0]:.1f} Hz/bin | {len(t_zoom)} time bins',
                 fontsize=16, fontweight='bold', color='white')

    # Style axes for dark theme
    ax1.tick_params(colors='white', which='both')
    ax1.spines['bottom'].set_color('white')
    ax1.spines['top'].set_color('white')
    ax1.spines['left'].set_color('white')
    ax1.spines['right'].set_color('white')

    # Add grid for easier line tracking
    ax1.grid(True, alpha=0.3, color='white', linestyle='--', linewidth=0.5)

    cbar = plt.colorbar(im, ax=ax1, label='Power (dB)')
    cbar.set_label('Power (dB)', fontsize=12, fontweight='bold', color='white')
    cbar.ax.tick_params(colors='white')
    cbar.outline.set_edgecolor('white')

    # Average spectrum panel
    ax2 = fig.add_subplot(gs[1, 0])
    ax2.set_facecolor('#1a1a1a')
    avg_spectrum = np.mean(Sxx_zoom, axis=1)
    ax2.plot(f_zoom / 1e3, avg_spectrum, 'cyan', linewidth=1.0, label='Average spectrum')
    ax2.set_ylabel('Power (dB)', fontsize=10, color='white')
    ax2.set_xlabel('Frequency offset (kHz)', fontsize=10, color='white')
    ax2.set_title('Average Spectrum (time-averaged)', fontsize=11, color='white')
    ax2.grid(True, alpha=0.3, color='white')
    ax2.set_xlim(f_zoom[0] / 1e3, f_zoom[-1] / 1e3)
    ax2.tick_params(colors='white', which='both')
    ax2.spines['bottom'].set_color('white')
    ax2.spines['top'].set_color('white')
    ax2.spines['left'].set_color('white')
    ax2.spines['right'].set_color('white')
    legend = ax2.legend(fontsize=8, loc='upper right')
    legend.get_frame().set_facecolor('#1a1a1a')
    legend.get_frame().set_edgecolor('white')
    for text in legend.get_texts():
        text.set_color('white')

    # Time-domain power panel
    ax3 = fig.add_subplot(gs[2, 0])
    ax3.set_facecolor('#1a1a1a')
    time_power = np.mean(Sxx_zoom, axis=0)
    ax3.plot(t_zoom, time_power, 'yellow', linewidth=1.0)
    ax3.set_ylabel('Power (dB)', fontsize=10, color='white')
    ax3.set_xlabel('Time (s)', fontsize=10, color='white')
    ax3.set_title('Average Power vs Time (frequency-averaged)', fontsize=11, color='white')
    ax3.grid(True, alpha=0.3, color='white')
    ax3.set_xlim(t_zoom[0], t_zoom[-1])
    ax3.tick_params(colors='white', which='both')
    ax3.spines['bottom'].set_color('white')
    ax3.spines['top'].set_color('white')
    ax3.spines['left'].set_color('white')
    ax3.spines['right'].set_color('white')

    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"  Saved narrowband plot with {len(f_zoom)} freq bins × {len(t_zoom)} time bins (3-panel view)")


def plot_spectrum(f, t, Sxx_db, results, output_path, sample_rate=2048000):
    """Generate comprehensive spectrum analysis plot"""
    # NO downsampling - preserve all spectral detail!
    # High resolution is crucial for seeing ~300 Hz wide spectral lines
    print(f"\nGenerating plot with FULL resolution: {len(t)} time bins × {len(f)} frequency bins...")

    # Use same gentle dynamic range as narrowband for consistency
    # Narrow 8 dB range to emphasize subtle spectral lines
    noise_floor = np.percentile(Sxx_db, 25)  # 25th percentile = noise floor
    signal_peak = np.percentile(Sxx_db, 99.9)  # 99.9th percentile = peak signals

    # Gentle dynamic range matching narrowband view
    vmin = np.percentile(Sxx_db, 60)  # Higher floor to suppress noise
    vmax = vmin + 8  # Very narrow 8 dB range to highlight subtle features

    print(f"  Dynamic range: {vmin:.1f} to {vmax:.1f} dB ({vmax-vmin:.1f} dB span)")
    print(f"  Noise floor (25th percentile): {noise_floor:.1f} dB")
    print(f"  Peak signal (99.9th percentile): {signal_peak:.1f} dB")

    # Create EXTRA large figure for maximum detail
    # Large DPI ensures all frequency bins are visible
    fig = plt.figure(figsize=(24, 16), dpi=300)
    gs = GridSpec(4, 1, figure=fig, hspace=0.25, height_ratios=[6, 1, 1, 0.5])

    # Dark theme background matching narrowband
    fig.patch.set_facecolor('#0a0a0a')

    # Main spectrogram - FULL WIDTH with time horizontal
    ax1 = fig.add_subplot(gs[0, 0])
    ax1.set_facecolor('#1a1a1a')

    # Use 'viridis' colormap - same gentle colors as narrowband
    # Auto shading for speed (rasterized for large datasets)
    im = ax1.pcolormesh(t, f / 1e6, Sxx_db, shading='auto',
                        cmap='viridis', vmin=vmin, vmax=vmax, rasterized=True)
    ax1.set_ylabel('Frequency offset (MHz)', fontsize=11, color='white')
    ax1.set_xlabel('Time (s)', fontsize=11, color='white')
    ax1.set_title(f'GPS L1 Spectrogram - Jamming Detection (Resolution: {f[1]-f[0]:.1f} Hz/bin)',
                  fontsize=13, fontweight='bold', color='white')

    # Style axes for dark theme
    ax1.tick_params(colors='white', which='both')
    ax1.spines['bottom'].set_color('white')
    ax1.spines['top'].set_color('white')
    ax1.spines['left'].set_color('white')
    ax1.spines['right'].set_color('white')

    cbar = plt.colorbar(im, ax=ax1, label='Power (dB)')
    cbar.set_label('Power (dB)', fontsize=10, color='white')
    cbar.ax.tick_params(colors='white')
    cbar.outline.set_edgecolor('white')

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
    ax2.set_facecolor('#1a1a1a')
    avg_spectrum = np.mean(Sxx_db, axis=1)
    ax2.plot(f / 1e6, avg_spectrum, 'cyan', linewidth=0.8, label='Average spectrum')

    # Highlight narrow-band signals if detected
    if 'narrowband' in results and results['narrowband']['detected']:
        peaks = results['narrowband']['peaks']
        for peak in peaks[:10]:  # Show top 10 on plot
            freq_mhz = peak['freq_mhz']
            # Draw vertical line at peak frequency
            ax2.axvline(freq_mhz, color='yellow', linestyle='--', linewidth=1, alpha=0.6)
            # Annotate with bandwidth
            ax2.text(freq_mhz, ax2.get_ylim()[1], f"{peak['bandwidth_hz']:.0f}Hz",
                    rotation=90, fontsize=7, color='yellow', alpha=0.8,
                    verticalalignment='top', horizontalalignment='right')

    ax2.set_ylabel('Power (dB)', fontsize=10, color='white')
    ax2.set_xlabel('Frequency offset (MHz)', fontsize=10, color='white')
    ax2.set_title('Average Spectrum (time-averaged) - Yellow lines: narrow-band signals', fontsize=11, color='white')
    ax2.grid(True, alpha=0.3, color='white')
    ax2.set_xlim(f[0] / 1e6, f[-1] / 1e6)
    ax2.tick_params(colors='white', which='both')
    ax2.spines['bottom'].set_color('white')
    ax2.spines['top'].set_color('white')
    ax2.spines['left'].set_color('white')
    ax2.spines['right'].set_color('white')
    legend = ax2.legend(fontsize=8, loc='upper right')
    legend.get_frame().set_facecolor('#1a1a1a')
    legend.get_frame().set_edgecolor('white')
    for text in legend.get_texts():
        text.set_color('white')

    # Time-domain power - FULL WIDTH
    ax3 = fig.add_subplot(gs[2, 0])
    ax3.set_facecolor('#1a1a1a')
    time_power = np.mean(Sxx_db, axis=0)
    ax3.plot(t, time_power, 'yellow', linewidth=0.8)
    ax3.set_ylabel('Power (dB)', fontsize=10, color='white')
    ax3.set_xlabel('Time (s)', fontsize=10, color='white')
    ax3.set_title('Average Power vs Time (frequency-averaged)', fontsize=11, color='white')
    ax3.grid(True, alpha=0.3, color='white')
    ax3.set_xlim(t[0], t[-1])
    ax3.tick_params(colors='white', which='both')
    ax3.spines['bottom'].set_color('white')
    ax3.spines['top'].set_color('white')
    ax3.spines['left'].set_color('white')
    ax3.spines['right'].set_color('white')

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

    # Save at 300 DPI to match figure DPI - preserves all detail
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"Saved high-resolution plot: {output_path}")


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(f"\n{'='*70}")
        print(f"FATAL ERROR")
        print(f"{'='*70}")
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        import sys
        sys.exit(1)
