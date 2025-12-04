#!/bin/bash

################################################################################
# Complete GNSS-SDR System - ONE SCRIPT
#
# This script starts EVERYTHING you need:
# 1. WebSocket bridge on port 8766 (for web UI)
# 2. Continuous recording and processing loop
#
# Usage: ./start_gnss.sh
# Stop: Press Ctrl+C
################################################################################

set -e

echo "========================================================================"
echo "Complete GNSS-SDR System Startup"
echo "========================================================================"
echo ""

# Set environment variables
export DYLD_LIBRARY_PATH="/usr/local/lib:$DYLD_LIBRARY_PATH"
export PYTHONPATH="/opt/homebrew/lib/python3.14/site-packages:$PYTHONPATH"

# Cleanup function
cleanup() {
    echo ""
    echo "🛑 Shutting down..."
    # Kill bridge
    if [ ! -z "$BRIDGE_PID" ]; then
        kill $BRIDGE_PID 2>/dev/null || true
        wait $BRIDGE_PID 2>/dev/null || true
    fi
    # Kill GNSS-SDR
    pkill -9 -f "gnss-sdr" 2>/dev/null || true
    # Kill log parser
    pkill -9 -f "parse_gnss_logs" 2>/dev/null || true
    # Kill recorder
    pkill -9 -f "record_iq" 2>/dev/null || true
    echo "✓ Shutdown complete"
    exit 0
}

trap cleanup SIGINT SIGTERM

# Initial cleanup
echo "🧹 Cleaning up previous processes..."
pkill -9 -f "python.*sdrplay" 2>/dev/null || true
pkill -9 -f "gnss-sdr" 2>/dev/null || true
pkill -9 -f "gnss_sdr_bridge" 2>/dev/null || true
pkill -9 -f "parse_gnss_logs" 2>/dev/null || true
pkill -9 -f "record_iq" 2>/dev/null || true
sleep 2
echo "✓ Cleanup complete"
echo ""

# Check SDRPlay
echo "🔍 Checking SDRPlay connection..."
if ! python3 -c "import SoapySDR; devices = SoapySDR.Device.enumerate('driver=sdrplay'); exit(0 if devices else 1)" 2>/dev/null; then
    echo "❌ ERROR: SDRPlay not found!"
    echo "   Please check:"
    echo "   • SDRPlay is connected via USB"
    echo "   • SDRPlay API is installed"
    exit 1
fi
echo "✓ SDRPlay found"
echo ""

echo "⚠️  IMPORTANT: Make sure your GPS antenna has a CLEAR SKY VIEW!"
echo ""

# Start WebSocket bridge in background
echo "========================================================================"
echo "Step 1: Starting WebSocket Bridge"
echo "========================================================================"
echo ""
echo "🌐 Starting bridge on ws://localhost:8766..."

python3 gnss_sdr_bridge.py --config gnss_sdr_file.conf --no-auto-start 2>&1 | while IFS= read -r line; do
    echo "[BRIDGE] $line"
done &

BRIDGE_PID=$!
sleep 3

# Check if bridge started successfully
if ! kill -0 $BRIDGE_PID 2>/dev/null; then
    echo "❌ ERROR: Bridge failed to start"
    exit 1
fi

echo "✓ Bridge started (PID: $BRIDGE_PID)"
echo "✓ WebSocket ready on ws://localhost:8766"
echo ""
echo "👉 You can now connect your web UI to ws://localhost:8766"
echo ""

# Start continuous recording and processing loop
echo "========================================================================"
echo "Step 2: Starting Continuous Recording & Processing"
echo "========================================================================"
echo ""
echo "Starting continuous loop..."
echo ""

CYCLE=1
while true; do
    echo "========================================================================"
    echo "CYCLE #$CYCLE - $(date '+%Y-%m-%d %H:%M:%S')"
    echo "========================================================================"
    echo ""

    # Check if bridge is still running
    if ! kill -0 $BRIDGE_PID 2>/dev/null; then
        echo "❌ ERROR: Bridge died! Restarting..."
        python3 gnss_sdr_bridge.py --config gnss_sdr_file.conf --no-auto-start 2>&1 | while IFS= read -r line; do
            echo "[BRIDGE] $line"
        done &
        BRIDGE_PID=$!
        sleep 3
    fi

    # Step 1: Record
    echo "📡 Recording 5 minutes (longer for PVT fix) of GPS samples..."
    echo "   Output: /tmp/gps_iq_samples.dat"
    echo ""

    rm -f /tmp/gps_iq_samples.dat

    # Start recording in background
    python3 record_iq_samples.py /tmp/gps_iq_samples.dat 300 &
    RECORD_PID=$!

    # Send progress updates while recording
    RECORD_DURATION=300
    for ((i=0; i<=RECORD_DURATION; i+=10)); do
        if ! kill -0 $RECORD_PID 2>/dev/null; then
            # Recording finished or failed
            break
        fi

        PROGRESS=$((i * 100 / RECORD_DURATION))
        REMAINING=$((RECORD_DURATION - i))
        python3 send_progress.py "recording" "$PROGRESS" "$i" "$RECORD_DURATION" "Recording GPS samples: ${REMAINING}s remaining" 2>/dev/null || true

        # Show progress in terminal every 30 seconds
        if [ $((i % 30)) -eq 0 ] && [ $i -gt 0 ]; then
            echo "   [${i}s] Recording... ($REMAINING seconds remaining)"
        fi

        sleep 10
    done

    # Wait for recording to finish
    wait $RECORD_PID
    RECORD_EXIT=$?

    if [ $RECORD_EXIT -ne 0 ]; then
        echo ""
        echo "⚠️  Recording failed! Retrying in 10 seconds..."
        python3 send_progress.py "error" 0 0 0 "Recording failed - retrying" 2>/dev/null || true
        sleep 10
        continue
    fi

    echo ""

    # Verify file exists and get size
    if [ ! -f /tmp/gps_iq_samples.dat ]; then
        echo "❌ ERROR: Recording file not found!"
        sleep 10
        continue
    fi

    FILE_SIZE=$(ls -lh /tmp/gps_iq_samples.dat 2>/dev/null | awk '{print $5}')
    echo "✅ Recording complete! Size: $FILE_SIZE"
    python3 send_progress.py "recording" 100 300 300 "Recording complete" 2>/dev/null || true

    # Small delay to ensure file is fully written and closed
    sleep 1
    echo ""

    # Step 2: Process with GNSS-SDR
    echo "🛰️  Processing with GNSS-SDR..."
    echo "   This will take ~60 seconds"
    echo "   Satellites will appear in UI immediately when tracked!"
    echo ""

    python3 send_progress.py "processing" 0 0 120 "Starting GNSS-SDR processing" 2>/dev/null || true

    # Start GNSS-SDR with log parser to show satellites in UI immediately
    DYLD_LIBRARY_PATH="/usr/local/lib:$DYLD_LIBRARY_PATH" \
        gnss-sdr --config_file=gnss_sdr_file.conf 2>&1 | python3 parse_gnss_logs.py | tee /tmp/gnss_sdr_output.log &
    GNSS_PID=$!

    # Wait for GNSS-SDR to finish
    WAIT_TIME=0
    while kill -0 $GNSS_PID 2>/dev/null; do
        sleep 5
        WAIT_TIME=$((WAIT_TIME + 5))

        # Send progress update
        PROGRESS=$((WAIT_TIME * 100 / 120))
        [ $PROGRESS -gt 100 ] && PROGRESS=100
        SAT_COUNT=$(grep -c "Tracking of GPS L1 C/A signal started" /tmp/gnss_sdr_output.log 2>/dev/null || echo "0")
        python3 send_progress.py "processing" "$PROGRESS" "$WAIT_TIME" "120" "Processing: $SAT_COUNT satellites tracked" 2>/dev/null || true

        # Show progress
        if [ $((WAIT_TIME % 15)) -eq 0 ]; then
            echo "   [${WAIT_TIME}s] Processing... ($SAT_COUNT satellites tracked so far)"
        fi

        # Timeout after 120 seconds
        if [ $WAIT_TIME -ge 120 ]; then
            echo "   ⚠️  Timeout reached, stopping GNSS-SDR..."
            python3 send_progress.py "processing" 100 120 120 "Processing complete (timeout)" 2>/dev/null || true
            kill -9 $GNSS_PID 2>/dev/null || true
            break
        fi
    done

    echo ""
    echo "✅ Processing complete!"

    # Show results
    SAT_COUNT=$(grep -c "Tracking of GPS L1 C/A signal started" /tmp/gnss_sdr_output.log 2>/dev/null || echo "0")
    if [ "$SAT_COUNT" -gt 0 ]; then
        echo "   🛰️  Tracked $SAT_COUNT satellites:"
        grep "Tracking of GPS L1 C/A signal started" /tmp/gnss_sdr_output.log 2>/dev/null | \
            sed 's/.*PRN /     • PRN /' | head -8
    else
        echo "   ⚠️  No satellites tracked (antenna may need better sky view)"
    fi
    echo ""

    echo "Waiting 5 seconds before next cycle..."
    sleep 5
    echo ""

    CYCLE=$((CYCLE + 1))
done
