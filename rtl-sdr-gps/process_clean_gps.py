#!/usr/bin/env python3
"""
Process clean GPS data from GNSS-SDR reference dataset
Generates test videos for baseline reference (no jamming)

Input format (from GNSS-SDR):
- Sample format: 16-bit signed integers (int16)
- Two values per sample: I and Q interleaved
- Value range: -32768 to +32767
- Sample rate: 4.0 MSPS (4,000,000 samples/second)
- Center frequency: 1575.42 MHz (GPS L1)

Output:
- Spectrum video showing clean GPS signal baseline
- JSON analysis report
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
    import matplotlib.animation as animation
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


class CleanGPSProcessor:
    """Process clean GPS reference data"""

    def __init__(self, sample_rate=4000000):
        self.sample_rate = sample_rate
        self.center_freq = 1575.42e6  # GPS L1
        self.gps_bandwidth = 2.046e6  # GPS L1 C/A main lobe

    def load_samples(self, filename, max_samples=None, skip_seconds=0.0):
        """Load GNSS-SDR 16-bit IQ samples from file

        GNSS-SDR format:
        - Interleaved IQ: [I0, Q0, I1, Q1, I2, Q2, ...]
        - 16-bit signed integers (int16)
        - Range: -32768 to +32767
        - Conversion: value / 32768.0 → range [-1.0, +1.0]
        """
        print(f"Loading GNSS-SDR samples from: {filename}")

        # Calculate samples to skip
        skip_samples = int(skip_seconds * self.sample_rate)
        skip_values = skip_samples * 2  # 2 values per IQ sample

        # Calculate how many values to read (2 per sample)
        read_count = -1  # -1 means read all
        if max_samples is not None:
            read_count = (max_samples + skip_samples) * 2

        # Read as int16 array
        raw_data = np.fromfile(filename, dtype=np.int16, count=read_count)

        print(f"  Raw values read: {len(raw_data):,}")

        # Skip initial values
        if len(raw_data) > skip_values:
            raw_data = raw_data[skip_values:]
            print(f"  Skipped first {skip_seconds * 1000:.0f} ms ({skip_values:,} values)")

        # Ensure even number of values (IQ pairs)
        if len(raw_data) % 2 != 0:
            raw_data = raw_data[:-1]

        # Convert to complex samples
        num_samples = len(raw_data) // 2

        # Extract I and Q components
        I = raw_data[0::2].astype(np.float32)  # Even indices: I
        Q = raw_data[1::2].astype(np.float32)  # Odd indices: Q

        # Normalize: (-32768 to +32767) → (-1.0 to +1.0)
        I = I / 32768.0
        Q = Q / 32768.0

        # Create complex samples
        samples = I + 1j * Q

        file_size = os.path.getsize(filename)
        duration = len(samples) / self.sample_rate

        print(f"  File size: {file_size / 1e9:.2f} GB ({file_size / 1e6:.1f} MB)")
        print(f"  Samples loaded: {len(samples):,}")
        print(f"  Duration: {duration:.1f} seconds")
        print(f"  Sample rate: {self.sample_rate / 1e6:.3f} MSPS")
        print(f"  Format: GNSS-SDR 16-bit IQ (int16 → complex float)")

        return samples

    def compute_spectrogram(self, samples, nperseg=2048, noverlap=None):
        """Compute spectrogram for time-frequency analysis"""
        if noverlap is None:
            noverlap = nperseg // 2

        print(f"\nComputing spectrogram...")
        print(f"  FFT size: {nperseg}")
        print(f"  Overlap: {noverlap}")

        if SCIPY_AVAILABLE:
            import time
            start_time = time.time()

            f, t, Sxx = signal.spectrogram(
                samples,
                fs=self.sample_rate,
                nperseg=nperseg,
                noverlap=noverlap,
                window='boxcar',
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
                    windowed = frame * np.hanning(nperseg)
                    spectrum = np.abs(fft(windowed)) ** 2
                    Sxx[:, i] = fftshift(spectrum)

            f = fftshift(fftfreq(nperseg, 1/self.sample_rate))

        # Convert to dB
        Sxx_db = 10 * np.log10(Sxx + 1e-12)

        print(f"  Time bins: {len(t)}")
        print(f"  Frequency bins: {len(f)}")
        print(f"  Frequency resolution: {f[1]-f[0]:.1f} Hz/bin")

        return f, t, Sxx_db

    def generate_analysis_report(self, samples, f, t, Sxx_db, output_path):
        """Generate analysis report for clean GPS data"""

        # Basic statistics
        avg_power = np.mean(np.abs(samples) ** 2)
        peak_power = np.max(np.abs(samples) ** 2)

        # Spectrum statistics
        avg_spectrum = np.mean(Sxx_db, axis=1)
        noise_floor = np.percentile(avg_spectrum, 25)

        report = {
            'timestamp': datetime.now().isoformat(),
            'file_type': 'CLEAN_GPS_REFERENCE',
            'source': 'GNSS-SDR CTTC Spain 2013-04-04',
            'signal_properties': {
                'sample_rate_hz': float(self.sample_rate),
                'center_frequency_hz': float(self.center_freq),
                'duration_seconds': float(len(samples) / self.sample_rate),
                'num_samples': int(len(samples)),
                'format': '16-bit signed IQ (int16)'
            },
            'power_statistics': {
                'average_power_dbfs': float(10 * np.log10(avg_power + 1e-12)),
                'peak_power_dbfs': float(10 * np.log10(peak_power + 1e-12)),
                'noise_floor_db': float(noise_floor)
            },
            'spectrum_info': {
                'frequency_resolution_hz': float(f[1] - f[0]),
                'time_bins': int(len(t)),
                'frequency_bins': int(len(f))
            },
            'notes': 'Clean GPS L1 C/A reference signal with no jamming'
        }

        with open(output_path, 'w') as fp:
            json.dump(report, fp, indent=2)

        print(f"\n✓ Analysis report saved: {output_path}")
        return report

    def generate_video(self, f, t, Sxx_db, output_path, fps=10, duration_seconds=None):
        """Generate spectrum animation video"""
        if not PLOTTING_AVAILABLE:
            print("Cannot generate video: matplotlib not available")
            return

        print(f"\nGenerating spectrum video...")

        # Determine time range
        if duration_seconds is not None:
            max_frames = int(duration_seconds * fps)
        else:
            max_frames = len(t)

        # Sample frames from spectrogram
        frame_indices = np.linspace(0, len(t)-1, min(max_frames, len(t)), dtype=int)

        print(f"  Total frames: {len(frame_indices)}")
        print(f"  Frame rate: {fps} fps")
        print(f"  Video duration: {len(frame_indices) / fps:.1f} seconds")

        # Focus on GPS L1 main lobe: ±1.023 MHz
        zoom_bw = 2.5e6  # 2.5 MHz for full main lobe visibility
        center_idx = len(f) // 2
        bw_bins = int(zoom_bw / (f[1] - f[0]))
        start_idx = max(0, center_idx - bw_bins // 2)
        end_idx = min(len(f), center_idx + bw_bins // 2)

        f_zoom = f[start_idx:end_idx]
        Sxx_zoom = Sxx_db[start_idx:end_idx, :]

        # Set up figure
        fig = plt.figure(figsize=(16, 10), dpi=100)
        gs = GridSpec(2, 1, figure=fig, hspace=0.3, height_ratios=[4, 1])

        fig.patch.set_facecolor('#0a0a0a')

        # Spectrogram panel
        ax1 = fig.add_subplot(gs[0, 0])
        ax1.set_facecolor('#1a1a1a')

        # Average spectrum panel
        ax2 = fig.add_subplot(gs[1, 0])
        ax2.set_facecolor('#1a1a1a')

        # Dynamic range
        vmin = np.percentile(Sxx_zoom, 60)
        vmax = vmin + 10

        # Setup axes styling first
        ax1.set_ylabel('Frequency offset (kHz)', fontsize=12, color='white')
        ax1.set_xlabel('Time (s)', fontsize=12, color='white')
        ax1.set_title('Clean GPS L1 Reference Signal', fontsize=14, fontweight='bold', color='white')

        # Style
        for ax in [ax1, ax2]:
            ax.tick_params(colors='white', which='both')
            for spine in ax.spines.values():
                spine.set_color('white')
            ax.grid(True, alpha=0.3, color='white')

        # Setup spectrum panel
        line, = ax2.plot([], [], 'cyan', linewidth=1.5)
        ax2.set_ylabel('Power (dB)', fontsize=10, color='white')
        ax2.set_xlabel('Frequency offset (kHz)', fontsize=10, color='white')
        ax2.set_title('Instantaneous Spectrum', fontsize=11, color='white')
        ax2.set_xlim(f_zoom[0] / 1e3, f_zoom[-1] / 1e3)
        ax2.set_ylim(vmin - 5, vmax + 5)

        # Will hold the current plot objects
        plot_objects = {'im': None, 'cbar': None}

        def init():
            line.set_data([], [])
            return [line]

        def animate(frame_num):
            nonlocal plot_objects

            idx = frame_indices[frame_num]
            current_time = t[idx]

            # Update spectrogram (show last 2 seconds)
            lookback_bins = int(2.0 / (t[1] - t[0]) if len(t) > 1 else 1)
            start_t = max(0, idx - lookback_bins)

            t_window = t[start_t:idx+1]
            Sxx_window = Sxx_zoom[:, start_t:idx+1]

            # Clear and update spectrogram
            ax1.clear()
            ax1.set_facecolor('#1a1a1a')

            # Create mesh plot
            im = ax1.pcolormesh(t_window, f_zoom / 1e3, Sxx_window,
                               shading='auto', cmap='viridis', vmin=vmin, vmax=vmax)

            # Restore styling
            ax1.set_ylabel('Frequency offset (kHz)', fontsize=12, color='white')
            ax1.set_xlabel('Time (s)', fontsize=12, color='white')
            ax1.set_title(f'Clean GPS L1 Reference Signal - t={current_time:.2f}s',
                         fontsize=14, fontweight='bold', color='white')
            ax1.tick_params(colors='white', which='both')
            for spine in ax1.spines.values():
                spine.set_color('white')
            ax1.grid(True, alpha=0.3, color='white')

            # Add colorbar on first frame only
            if plot_objects['cbar'] is None:
                plot_objects['cbar'] = plt.colorbar(im, ax=ax1, label='Power (dB)')
                plot_objects['cbar'].set_label('Power (dB)', fontsize=10, color='white')
                plot_objects['cbar'].ax.tick_params(colors='white')
                plot_objects['cbar'].outline.set_edgecolor('white')

            # Update spectrum
            spectrum = Sxx_zoom[:, idx]
            line.set_data(f_zoom / 1e3, spectrum)

            return [im, line]

        # Create animation
        anim = animation.FuncAnimation(
            fig, animate, init_func=init,
            frames=len(frame_indices), interval=1000/fps, blit=False
        )

        # Save video/GIF
        print(f"  Saving to {output_path}...")

        # Determine output format based on extension
        if output_path.endswith('.gif'):
            # Save as GIF using Pillow
            try:
                from PIL import Image
                anim.save(output_path, writer='pillow', fps=fps, dpi=100)
                print(f"✓ GIF saved: {output_path}")
            except Exception as e:
                print(f"Error saving GIF: {e}")
                print("Try installing Pillow: pip install pillow")
                raise
        else:
            # Try ffmpeg for mp4/other formats
            try:
                Writer = animation.writers['ffmpeg']
                writer = Writer(fps=fps, bitrate=2000, codec='libx264')
                anim.save(output_path, writer=writer, dpi=100)
                print(f"✓ Video saved: {output_path}")
            except RuntimeError:
                # Fallback to GIF if ffmpeg not available
                gif_path = output_path.rsplit('.', 1)[0] + '.gif'
                print(f"  ffmpeg not available, saving as GIF instead: {gif_path}")
                from PIL import Image
                anim.save(gif_path, writer='pillow', fps=fps, dpi=100)
                print(f"✓ GIF saved: {gif_path}")
                output_path = gif_path

        plt.close()
        print(f"  Duration: {len(frame_indices) / fps:.1f}s at {fps} fps")


def generate_static_plot(f, t, Sxx_db, output_path, time_range=None):
    """Generate static spectrogram plot (much faster than video)"""
    if not PLOTTING_AVAILABLE:
        print("Cannot generate plot: matplotlib not available")
        return

    print(f"\nGenerating static plot...")

    # Optionally limit time range
    if time_range is not None:
        time_mask = t <= time_range
        t = t[time_mask]
        Sxx_db = Sxx_db[:, time_mask]
        print(f"  Limited to first {time_range}s")

    # Focus on GPS L1 main lobe: ±1.25 MHz
    zoom_bw = 2.5e6
    center_idx = len(f) // 2
    bw_bins = int(zoom_bw / (f[1] - f[0]))
    start_idx = max(0, center_idx - bw_bins // 2)
    end_idx = min(len(f), center_idx + bw_bins // 2)

    f_zoom = f[start_idx:end_idx]
    Sxx_zoom = Sxx_db[start_idx:end_idx, :]

    # Dynamic range
    vmin = np.percentile(Sxx_zoom, 60)
    vmax = vmin + 10

    # Create figure
    fig = plt.figure(figsize=(20, 12), dpi=150)
    gs = GridSpec(3, 1, figure=fig, hspace=0.3, height_ratios=[6, 1, 1])
    fig.patch.set_facecolor('#0a0a0a')

    # Spectrogram
    ax1 = fig.add_subplot(gs[0, 0])
    ax1.set_facecolor('#1a1a1a')
    im = ax1.pcolormesh(t, f_zoom / 1e3, Sxx_zoom,
                       shading='auto', cmap='viridis', vmin=vmin, vmax=vmax)
    ax1.set_ylabel('Frequency offset (kHz)', fontsize=14, color='white')
    ax1.set_xlabel('Time (s)', fontsize=14, color='white')
    ax1.set_title(f'Clean GPS L1 Reference Signal (GNSS-SDR CTTC Spain 2013)',
                 fontsize=16, fontweight='bold', color='white')
    ax1.tick_params(colors='white', which='both')
    for spine in ax1.spines.values():
        spine.set_color('white')
    ax1.grid(True, alpha=0.3, color='white')

    cbar = plt.colorbar(im, ax=ax1, label='Power (dB)')
    cbar.set_label('Power (dB)', fontsize=12, color='white')
    cbar.ax.tick_params(colors='white')
    cbar.outline.set_edgecolor('white')

    # Average spectrum
    ax2 = fig.add_subplot(gs[1, 0])
    ax2.set_facecolor('#1a1a1a')
    avg_spectrum = np.mean(Sxx_zoom, axis=1)
    ax2.plot(f_zoom / 1e3, avg_spectrum, 'cyan', linewidth=1.5)
    ax2.set_ylabel('Power (dB)', fontsize=11, color='white')
    ax2.set_xlabel('Frequency offset (kHz)', fontsize=11, color='white')
    ax2.set_title('Average Spectrum', fontsize=12, color='white')
    ax2.grid(True, alpha=0.3, color='white')
    ax2.set_xlim(f_zoom[0] / 1e3, f_zoom[-1] / 1e3)
    ax2.tick_params(colors='white', which='both')
    for spine in ax2.spines.values():
        spine.set_color('white')

    # Time-domain power
    ax3 = fig.add_subplot(gs[2, 0])
    ax3.set_facecolor('#1a1a1a')
    time_power = np.mean(Sxx_zoom, axis=0)
    ax3.plot(t, time_power, 'yellow', linewidth=1.5)
    ax3.set_ylabel('Power (dB)', fontsize=11, color='white')
    ax3.set_xlabel('Time (s)', fontsize=11, color='white')
    ax3.set_title('Average Power vs Time', fontsize=12, color='white')
    ax3.grid(True, alpha=0.3, color='white')
    ax3.set_xlim(t[0], t[-1])
    ax3.tick_params(colors='white', which='both')
    for spine in ax3.spines.values():
        spine.set_color('white')

    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()

    print(f"✓ Static plot saved: {output_path}")
    print(f"  Time span: {t[-1]:.1f}s")
    print(f"  Frequency range: ±{zoom_bw/2e6:.2f} MHz")


def main():
    parser = argparse.ArgumentParser(
        description='Process clean GPS reference data from GNSS-SDR',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument('input_file', help='GPS IQ recording file (.dat)')
    parser.add_argument('-d', '--duration', type=float, help='Process first N seconds')
    parser.add_argument('-p', '--plot', type=str, help='Output static plot file (.png)')
    parser.add_argument('-v', '--video', type=str, help='Output video file (.mp4/.gif)')
    parser.add_argument('-o', '--output', type=str, help='JSON report output path')
    parser.add_argument('--sample-rate', type=float, default=4.0e6,
                       help='Sample rate (default: 4.0 MSPS)')
    parser.add_argument('--fps', type=int, default=10, help='Video frame rate (default: 10)')
    parser.add_argument('--video-duration', type=float, help='Video duration in seconds')

    args = parser.parse_args()

    if not os.path.exists(args.input_file):
        print(f"Error: File not found: {args.input_file}")
        sys.exit(1)

    print("=" * 70)
    print("CLEAN GPS REFERENCE DATA PROCESSOR")
    print("=" * 70)
    print(f"\nInput: {args.input_file}")
    print("")

    # Initialize processor
    processor = CleanGPSProcessor(sample_rate=args.sample_rate)

    # Load samples
    max_samples = None
    if args.duration:
        max_samples = int(args.duration * args.sample_rate)

    samples = processor.load_samples(args.input_file, max_samples)

    # Compute spectrogram
    f, t, Sxx_db = processor.compute_spectrogram(samples, nperseg=2048, noverlap=1024)

    # Generate report
    output_path = args.output or args.input_file.replace('.dat', '_clean_analysis.json')
    report = processor.generate_analysis_report(samples, f, t, Sxx_db, output_path)

    # Generate static plot if requested (faster than video)
    if args.plot:
        generate_static_plot(f, t, Sxx_db, args.plot)

    # Generate video if requested
    if args.video:
        processor.generate_video(f, t, Sxx_db, args.video,
                               fps=args.fps, duration_seconds=args.video_duration)

    print("\n" + "=" * 70)
    print("PROCESSING COMPLETE")
    print("=" * 70)
    print(f"\nDuration: {report['signal_properties']['duration_seconds']:.1f} seconds")
    print(f"Noise floor: {report['power_statistics']['noise_floor_db']:.1f} dB")
    print(f"Average power: {report['power_statistics']['average_power_dbfs']:.1f} dBFS")
    print("\n✓ Clean GPS reference data processed successfully")


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
        sys.exit(1)
