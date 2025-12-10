#!/bin/bash

################################################################################
# GNSS-SDR Real-Time FIFO Mode
#
# This script uses a FIFO (named pipe) for real-time streaming:
#   SDRPlay recorder → FIFO → GNSS-SDR (continuous processing)
#
# This allows real-time ephemeris decoding without file replay speed issues!
#
# Usage: ./start_gnss_realtime.sh
# Stop: Press Ctrl+C
################################################################################

set -e

echo "========================================================================"
echo "GNSS-SDR Real-Time FIFO Mode"
echo "========================================================================"
echo ""

# Set environment variables
export DYLD_LIBRARY_PATH="/usr/local/lib:$DYLD_LIBRARY_PATH"
export PYTHONPATH="/opt/homebrew/lib/python3.14/site-packages:$PYTHONPATH"

# Cleanup function
cleanup() {
    echo ""
    echo "🛑 Shutting down real-time processing..."
    pkill -9 -f "record_iq_samples" 2>/dev/null || true
    pkill -9 -f "gnss-sdr" 2>/dev/null || true
    pkill -9 -f "parse_gnss_logs" 2>/dev/null || true
    rm -f /tmp/gps_fifo 2>/dev/null || true
    echo "✓ Shutdown complete"
    exit 0
}

trap cleanup SIGINT SIGTERM

# Initial cleanup
echo "🧹 Cleaning up previous processes..."
pkill -9 -f "record_iq_samples" 2>/dev/null || true
pkill -9 -f "gnss-sdr" 2>/dev/null || true
pkill -9 -f "parse_gnss_logs" 2>/dev/null || true
rm -f /tmp/gps_fifo 2>/dev/null || true
sleep 2
echo "✓ Cleanup complete"
echo ""

echo "⚠️  IMPORTANT: Make sure your GPS antenna has a CLEAR SKY VIEW!"
echo "   Position fix requires 30-60 seconds of continuous satellite tracking"
echo ""

# Create FIFO (named pipe)
echo "Creating FIFO for real-time streaming..."
mkfifo /tmp/gps_fifo
echo "✓ FIFO created at /tmp/gps_fifo"
echo ""

# Send initial progress message
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python3 "$SCRIPT_DIR/send_progress.py" "recording" 0 0 0 "Starting real-time GNSS processing..." || true

echo "========================================================================"
echo "Starting Real-Time GPS Processing"
echo "========================================================================"
echo ""
echo "📡 Starting SDRPlay recorder → FIFO stream..."

# Start continuous IQ recorder writing to FIFO (in background)
python3 record_iq_samples.py /tmp/gps_fifo 0 &  # 0 = infinite duration
RECORDER_PID=$!
echo "✓ Recorder started (PID: $RECORDER_PID)"

# Give recorder time to start
sleep 3

echo ""
echo "🛰️  Starting GNSS-SDR reading from FIFO..."
echo "   • Satellite acquisition: ~10-30 seconds"
echo "   • Ephemeris decoding: ~30-60 seconds per satellite"
echo "   • Position fix: ~1-3 minutes total"
echo ""
echo "Watch the UI for real-time updates!"
echo ""

# Start GNSS-SDR reading from FIFO with log parser
DYLD_LIBRARY_PATH="/usr/local/lib:$DYLD_LIBRARY_PATH" \
    gnss-sdr --config_file=gnss_sdr_fifo.conf 2>&1 | python3 parse_gnss_logs.py | tee /tmp/gnss_sdr_output.log

echo ""
echo "✅ GNSS-SDR stopped"
cleanup
