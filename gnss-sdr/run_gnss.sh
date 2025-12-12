#!/bin/bash
# REAL GNSS-SDR Pipeline with SDRplay via SoapySDR
# NO FIFO - Direct GNU Radio connection!

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Set library paths (CRITICAL for SoapySDR to find libsdrplay_api.so.3)
export DYLD_LIBRARY_PATH="/usr/local/lib:$DYLD_LIBRARY_PATH"
export PYTHONPATH="/opt/homebrew/lib/python3.14/site-packages:$PYTHONPATH"
export PYTHONUNBUFFERED=1

echo "========================================================================"
echo "GNSS-SDR with SDRplay via SoapySDR (NO FIFO!)"
echo "========================================================================"
echo ""

# Kill any existing GNSS processes first
echo "🧹 Cleaning up any existing processes..."
pkill -f "gnss-sdr" 2>/dev/null || true
pkill -f "sdrplay_fifo" 2>/dev/null || true
pkill -f "parse_gnss_logs" 2>/dev/null || true
pkill -f "run_gnss_continuous" 2>/dev/null || true
pkill -f "async_gnss_streamer" 2>/dev/null || true
rm -f /tmp/gnss_fifo 2>/dev/null || true
rm -f /tmp/gnss_continuous.conf 2>/dev/null || true
sleep 2
echo "✓ Cleanup complete"
echo ""

echo "📡 Processing REAL GPS signals from SDRplay device"
echo "   • SDRplay → SoapySDR → GNU Radio → GNSS-SDR"
echo "   • NO FIFO (direct connection, no blocking!)"
echo "   • Sample rate: 2.048 MSPS"
echo "   • Frequency: 1575.42 MHz (GPS L1)"
echo "   • Gain: 29 dB"
echo ""

# Cleanup handler
cleanup() {
    echo ""
    echo "🛑 Shutting down..."
    pkill -f "gnss-sdr" 2>/dev/null || true
    pkill -f "sdrplay_fifo" 2>/dev/null || true
    pkill -f "run_gnss_continuous" 2>/dev/null || true
    pkill -f "parse_gnss_logs" 2>/dev/null || true
    rm -f /tmp/gnss_fifo 2>/dev/null || true
    rm -f /tmp/gnss_continuous.conf 2>/dev/null || true
    echo "✓ Cleanup complete"
    exit 0
}

trap cleanup SIGINT SIGTERM

echo "========================================================================"
echo "Starting REAL GNSS-SDR Processing"
echo "========================================================================"
echo ""

# Run the continuous GNSS pipeline with REAL SDRplay data
python3 -u "${SCRIPT_DIR}/run_gnss_continuous.py"

echo ""
echo "✅ GNSS Streamer stopped"
