#!/bin/bash

################################################################################
# GNSS-SDR Live Streaming Mode
#
# This script runs GNSS-SDR in REAL-TIME mode with direct SDRPlay streaming
# This allows ephemeris decoding and position fixes!
#
# Usage: ./start_gnss_live.sh
# Stop: Press Ctrl+C
################################################################################

set -e

echo "========================================================================"
echo "GNSS-SDR Live Streaming Mode"
echo "========================================================================"
echo ""

# Set environment variables
export DYLD_LIBRARY_PATH="/usr/local/lib:$DYLD_LIBRARY_PATH"
export PYTHONPATH="/opt/homebrew/lib/python3.14/site-packages:$PYTHONPATH"

# Cleanup function
cleanup() {
    echo ""
    echo "🛑 Shutting down GNSS-SDR..."
    pkill -9 -f "gnss-sdr" 2>/dev/null || true
    pkill -9 -f "parse_gnss_logs" 2>/dev/null || true
    echo "✓ Shutdown complete"
    exit 0
}

trap cleanup SIGINT SIGTERM

# Initial cleanup
echo "🧹 Cleaning up previous processes..."
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
python3 "$SCRIPT_DIR/send_progress.py" "recording" 0 0 0 "Starting live GNSS-SDR processing..." || true

echo "========================================================================"
echo "Starting GNSS-SDR in LIVE MODE"
echo "========================================================================"
echo ""
echo "🛰️  Processing live GPS signals from SDRPlay..."
echo "   • Satellite acquisition: ~10-30 seconds"
echo "   • Ephemeris decoding: ~30-60 seconds per satellite"
echo "   • Position fix: ~1-3 minutes total"
echo ""
echo "Watch the UI for real-time updates!"
echo ""

# Start GNSS-SDR with live SDRPlay input and log parser
DYLD_LIBRARY_PATH="/usr/local/lib:$DYLD_LIBRARY_PATH" \
    gnss-sdr --config_file=gnss_sdr_sdrplay_direct.conf 2>&1 | python3 parse_gnss_logs.py | tee /tmp/gnss_sdr_output.log

echo ""
echo "✅ GNSS-SDR stopped"
