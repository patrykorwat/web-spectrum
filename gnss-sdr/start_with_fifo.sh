#!/bin/bash
#
# Start GNSS-SDR with FIFO-based streaming from SDRplay
# This avoids both the Osmosdr crash and the file EOF problem
#

set -e

FIFO_PATH="/tmp/gps_iq_fifo"

echo "======================================"
echo "GNSS-SDR with FIFO Streaming"
echo "======================================"
echo

# Clean up old FIFO if exists
if [ -p "$FIFO_PATH" ]; then
    echo "Removing old FIFO..."
    rm -f "$FIFO_PATH"
fi

# Create FIFO
echo "Creating FIFO at $FIFO_PATH..."
mkfifo "$FIFO_PATH"
echo "✓ FIFO created"
echo

# Start streamer in background (writes to FIFO)
echo "Starting SDRplay streamer (writes to FIFO)..."
python3 -u sdrplay_soapy_streamer.py \
    --output "$FIFO_PATH" \
    --frequency 1575.42e6 \
    --sample-rate 2.048e6 \
    --gain 40 \
    --bandwidth 1536000 \
    > /tmp/sdrplay_fifo_streamer.log 2>&1 &

STREAMER_PID=$!
echo "✓ Streamer started (PID $STREAMER_PID)"
echo

# Wait a moment for streamer to initialize
sleep 2

# Start GNSS-SDR (reads from FIFO)
echo "Starting GNSS-SDR (reads from FIFO)..."
echo "This will run continuously..."
echo

DYLD_LIBRARY_PATH="/usr/local/lib:$DYLD_LIBRARY_PATH" \
    gnss-sdr --config_file=gnss_sdr_fifo.conf

# Cleanup on exit
echo
echo "Cleaning up..."
kill $STREAMER_PID 2>/dev/null || true
rm -f "$FIFO_PATH"
echo "Done"
