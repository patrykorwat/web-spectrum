#!/bin/bash
# Continuous monitoring: record and process in a loop
# Records 1 second at 10 MSPS, processes with full 8 MHz bandwidth

set -e
cd "$(dirname "$0")"

COUNT=1
INTERVAL=5  # seconds between captures

echo "Starting continuous GPS monitoring..."
echo "Press Ctrl+C to stop"
echo ""

while true; do
    TIMESTAMP=$(date +%Y%m%d_%H%M%S)
    echo "[$COUNT] $(date '+%Y-%m-%d %H:%M:%S') - Recording..."

    # Record 10 seconds
    python3 simple_record.py 10.0 > /dev/null 2>&1

    # Get the latest recording
    LATEST=$(ls -t recordings/gps_recording_*_10msps.dat 2>/dev/null | head -1)

    if [ -n "$LATEST" ]; then
        echo "    Processing: $LATEST"

        # Process with full 8 MHz bandwidth using fast method
        python3 << EOPLOT
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from scipy import signal, fft

FILE = "$LATEST"
PLOT = FILE.replace('.dat', '_monitor.jpeg')

samples = np.fromfile(FILE, dtype=np.complex64)
fs = 8e6  # 8 MSPS - full bandwidth

# Fast parameters
nperseg = 256
noverlap = 64

f, t, Sxx = signal.spectrogram(samples, fs=fs, nperseg=nperseg, noverlap=noverlap,
                                return_onesided=False, mode='magnitude')
Sxx_db = 20 * np.log10(Sxx + 1e-12)
f = fft.fftshift(f)
Sxx_db = fft.fftshift(Sxx_db, axes=0)

# Interpolate over DC spike (center frequency bin that gets nulled by hardware DC correction)
# Find center frequency bin (should be at 0 Hz)
center_idx = len(f) // 2
# Interpolate using adjacent bins (±2 bins around center)
Sxx_db[center_idx, :] = (Sxx_db[center_idx-2, :] + Sxx_db[center_idx+2, :]) / 2
Sxx_db[center_idx-1, :] = (Sxx_db[center_idx-2, :] * 0.75 + Sxx_db[center_idx+2, :] * 0.25)
Sxx_db[center_idx+1, :] = (Sxx_db[center_idx-2, :] * 0.25 + Sxx_db[center_idx+2, :] * 0.75)

fig, ax = plt.subplots(figsize=(20, 10), dpi=100)
fig.patch.set_facecolor('#0a0a0a')
ax.set_facecolor('#1a1a1a')

vmin, vmax = np.percentile(Sxx_db, [5, 99.5])
extent = [t[0]*1000, t[-1]*1000, f[0]/1e6, f[-1]/1e6]

im = ax.imshow(Sxx_db, aspect='auto', origin='lower', extent=extent,
               cmap='viridis', vmin=vmin, vmax=vmax, interpolation='bilinear')

ax.set_ylabel('Frequency Offset (MHz)', fontsize=16, color='white', fontweight='bold')
ax.set_xlabel('Time (ms)', fontsize=16, color='white', fontweight='bold')
ax.set_title('RSPduo @ 6 MSPS - 5 MHz BW - Capture #$COUNT - $(date "+%H:%M:%S")',
             fontsize=18, color='yellow', fontweight='bold')
ax.tick_params(colors='white', labelsize=12)
ax.grid(True, alpha=0.2, color='white', linewidth=0.5)
for spine in ax.spines.values():
    spine.set_color('white')
    spine.set_linewidth(1.5)

cbar = plt.colorbar(im, ax=ax)
cbar.set_label('Power (dB)', color='white', fontsize=14)
cbar.ax.tick_params(colors='white', labelsize=10)

plt.tight_layout()
plt.savefig(PLOT, bbox_inches='tight', facecolor='#0a0a0a', dpi=100)
print(f'✓ {PLOT}')
EOPLOT

        echo "    ✓ Complete"
    else
        echo "    ✗ No recording found"
    fi

    COUNT=$((COUNT + 1))
    echo "    Waiting ${INTERVAL}s..."
    echo ""
    sleep $INTERVAL
done
