#!/bin/bash

################################################################################
# GNSS-SDR File-Based Mode
#
# This script records IQ samples to a file, then processes with GNSS-SDR
#
# Usage: ./start_gnss_file.sh
# Stop: Press Ctrl+C
################################################################################

set -e

echo "========================================================================"
echo "GNSS-SDR File-Based Mode"
echo "========================================================================"
echo ""

# Set environment variables
export DYLD_LIBRARY_PATH="/usr/local/lib:$DYLD_LIBRARY_PATH"
export PYTHONPATH="/opt/homebrew/lib/python3.14/site-packages:$PYTHONPATH"

# Cleanup function
cleanup() {
    echo ""
    echo "🛑 Shutting down GPS processing..."
    pkill -9 -f "record_iq_samples" 2>/dev/null || true
    pkill -9 -f "gnss-sdr" 2>/dev/null || true
    pkill -9 -f "parse_gnss_logs" 2>/dev/null || true
    echo "✓ Shutdown complete"
    exit 0
}

trap cleanup SIGINT SIGTERM

# Initial cleanup
echo "🧹 Cleaning up previous processes..."
pkill -9 -f "record_iq_samples" 2>/dev/null || true
pkill -9 -f "gnss-sdr" 2>/dev/null || true
pkill -9 -f "parse_gnss_logs" 2>/dev/null || true
sleep 2
echo "✓ Cleanup complete"
echo ""

echo "⚠️  IMPORTANT: Make sure your GPS antenna has a CLEAR SKY VIEW!"
echo "   Position fix requires 30-60 seconds of continuous satellite tracking"
echo ""

# Send initial progress message
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python3 "$SCRIPT_DIR/send_progress.py" "recording" 0 0 0 "Recording GPS samples..." || true

echo "========================================================================"
echo "Step 1: Recording GPS Samples"
echo "========================================================================"
echo ""
echo "📡 Recording 60 seconds of GPS data..."

# Record GPS data to file
OUTPUT_FILE="/tmp/gps_iq_samples.dat"
rm -f "$OUTPUT_FILE" 2>/dev/null || true

DYLD_LIBRARY_PATH="/usr/local/lib:$DYLD_LIBRARY_PATH" \
    PYTHONPATH="/opt/homebrew/lib/python3.14/site-packages:$PYTHONPATH" \
    python3 "$SCRIPT_DIR/record_iq_samples.py" "$OUTPUT_FILE" 60
RECORDER_EXIT=$?

if [ $RECORDER_EXIT -ne 0 ]; then
    echo "❌ Recording failed with exit code $RECORDER_EXIT"
    python3 "$SCRIPT_DIR/send_progress.py" "error" 0 0 0 "Recording failed - check SDRPlay connection" || true
    exit 1
fi

# Check if file was created and has data
if [ ! -f "$OUTPUT_FILE" ]; then
    echo "❌ Recording file not created"
    python3 "$SCRIPT_DIR/send_progress.py" "error" 0 0 0 "Recording file not created" || true
    exit 1
fi

FILE_SIZE=$(stat -f%z "$OUTPUT_FILE" 2>/dev/null || stat -c%s "$OUTPUT_FILE" 2>/dev/null)
if [ "$FILE_SIZE" -lt 1000000 ]; then
    echo "❌ Recording file too small ($FILE_SIZE bytes)"
    python3 "$SCRIPT_DIR/send_progress.py" "error" 0 0 0 "Recording failed - file too small" || true
    exit 1
fi

echo "✓ Recording complete: $FILE_SIZE bytes"
echo ""

python3 "$SCRIPT_DIR/send_progress.py" "processing" 0 0 0 "Processing GPS samples with GNSS-SDR..." || true

echo "========================================================================"
echo "Step 2: Processing with GNSS-SDR"
echo "========================================================================"
echo ""
echo "🛰️  Processing GPS data..."
echo "   • Satellite acquisition: ~10-30 seconds"
echo "   • Ephemeris decoding: ~30-60 seconds per satellite"
echo "   • Position fix: ~1-3 minutes total"
echo ""
echo "Watch the UI for real-time updates!"
echo ""

# Process with GNSS-SDR
DYLD_LIBRARY_PATH="/usr/local/lib:$DYLD_LIBRARY_PATH" \
    gnss-sdr --config_file=gnss_sdr_file.conf 2>&1 | python3 parse_gnss_logs.py | tee /tmp/gnss_sdr_output.log

echo ""
echo "✅ GNSS-SDR processing complete"
cleanup
