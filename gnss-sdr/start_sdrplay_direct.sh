#!/bin/bash
#
# Start SDRplay with direct API access
#
# This script uses the direct Python bindings to SDRplay API
# instead of going through SoapySDR/gr-osmosdr.
#
# Usage:
#   ./start_sdrplay_direct.sh              # Default GPS L1 settings
#   ./start_sdrplay_direct.sh --gain 30    # Custom gain
#

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUTPUT_FILE="/tmp/gps_iq_samples.dat"

echo "========================================================================"
echo "SDRplay Direct API Streamer"
echo "========================================================================"
echo ""
echo "This uses direct SDRplay API access (no SoapySDR/gr-osmosdr)"
echo ""
echo "Output: $OUTPUT_FILE"
echo "Format: complex64 (gr_complex)"
echo "Sample rate: 2.048 MSPS"
echo "Frequency: 1575.42 MHz (GPS L1)"
echo ""
echo "Press Ctrl+C to stop"
echo "========================================================================"
echo ""

# Check if SDRplay API is available
if ! python3 "$SCRIPT_DIR/test_sdrplay_api.py" > /dev/null 2>&1; then
    echo "❌ SDRplay API not available or not working"
    echo ""
    echo "Please check:"
    echo "  1. SDRplay API is installed"
    echo "  2. SDRplay service is running"
    echo "  3. Device is connected via USB"
    echo ""
    exit 1
fi

echo "✓ SDRplay API is ready"
echo ""

# Run the streamer
exec python3 "$SCRIPT_DIR/sdrplay_streamer.py" \
    --output "$OUTPUT_FILE" \
    "$@"
