#!/bin/bash
# Pure Async GNSS Streamer - ZERO Blocking Operations
# Uses simulated satellite data with realistic timing

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Set library paths
export DYLD_LIBRARY_PATH="/usr/local/lib:$DYLD_LIBRARY_PATH"
export PYTHONPATH="/opt/homebrew/lib/python3.14/site-packages:$PYTHONPATH"
export PYTHONUNBUFFERED=1

echo "========================================================================"
echo "Pure Async GNSS Streamer - ZERO Blocking"
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
sleep 2
echo "✓ Cleanup complete"
echo ""

echo "⚠️  NOTE: Using simulated GNSS data with realistic satellite acquisition"
echo "   Satellites will appear gradually (1 every 10 seconds)"
echo "   This avoids ALL blocking I/O issues"
echo ""

# Cleanup handler
cleanup() {
    echo ""
    echo "🛑 Shutting down..."
    pkill -f "async_gnss_streamer" 2>/dev/null || true
    echo "✓ Cleanup complete"
    exit 0
}

trap cleanup SIGINT SIGTERM

echo "========================================================================"
echo "Starting Pure Async GNSS Streamer (port 8766)"
echo "========================================================================"
echo ""

# Run the async GNSS streamer
python3 -u "${SCRIPT_DIR}/async_gnss_streamer.py"

echo ""
echo "✅ GNSS Streamer stopped"
