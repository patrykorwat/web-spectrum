#!/bin/bash

################################################################################
# SDRPlay to GNSS-SDR Streamer
#
# This script streams IQ samples from SDRPlay to GNSS-SDR via UDP
#
# Usage:
#   ./run_sdrplay_to_gnss.sh
#
# This will:
#   1. Capture IQ samples from SDRPlay RSPduo (Tuner 2, GPS L1)
#   2. Stream via UDP to GNSS-SDR (port 5555)
#   3. Enable bias-T for active antenna
#
# Make sure GNSS-SDR bridge is running first!
################################################################################

# Default settings for GPS L1
FREQ="1575.42e6"  # GPS L1 frequency
RATE="2.048e6"    # 2.048 MSPS (matches GNSS-SDR config)
GAIN="40"         # 40 dB gain
TUNER="2"         # Tuner 2 (has bias-T)
BIAS_TEE="--bias-tee"  # Enable bias-T for active antenna

echo ""
echo "============================================================"
echo "SDRPlay to GNSS-SDR IQ Streamer"
echo "============================================================"
echo ""
echo "Configuration:"
echo "  • Frequency: 1575.42 MHz (GPS L1)"
echo "  • Sample rate: 2.048 MSPS"
echo "  • Gain: 40 dB"
echo "  • Tuner: 2 (with bias-T enabled)"
echo "  • Target: UDP localhost:5555 → GNSS-SDR"
echo ""
echo "Make sure:"
echo "  1. GNSS-SDR bridge is running: ./run_gnss_sdr_bridge.sh"
echo "  2. SDRPlay is connected"
echo "  3. GPS antenna connected to Tuner 2 (active antenna)"
echo ""
echo "Press Enter to start streaming..."
read

# Activate virtual environment if it exists (needed for SoapySDR Python bindings)
if [ -d "venv" ]; then
    echo "Activating virtual environment..."
    source venv/bin/activate
fi

# Set library path for SDRPlay API (macOS)
export DYLD_LIBRARY_PATH="/usr/local/lib:$DYLD_LIBRARY_PATH"

# Set Python path for SoapySDR Python bindings
export PYTHONPATH="/opt/homebrew/lib/python3.14/site-packages:$PYTHONPATH"

# Run the streamer
python3 sdrplay_to_gnss_sdr.py \
    --freq ${FREQ} \
    --rate ${RATE} \
    --gain ${GAIN} \
    --tuner ${TUNER} \
    ${BIAS_TEE}
