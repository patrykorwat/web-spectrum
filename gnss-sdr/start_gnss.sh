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
    echo "🛑 Shutting down data collection..."
    # NOTE: Bridge cleanup is handled by start_all.sh
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

# Check SDRPlay - DISABLED because SoapySDR enumeration hangs
# The recording script will fail if device is not available anyway
echo "⚠️  Note: SDRPlay device check disabled (SoapySDR hangs)"
echo "   If recording fails, check that SDRPlay is connected via USB"
echo ""

echo "⚠️  IMPORTANT: Make sure your GPS antenna has a CLEAR SKY VIEW!"
echo ""

# NOTE: WebSocket bridge is managed by start_all.sh
# This script only handles the recording and processing loop

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

    # NOTE: Bridge monitoring is handled by start_all.sh

    # Step 1: Record
    echo "📡 Recording 15 minutes (for stable tracking) of GPS samples..."
    echo "   Output: /tmp/gps_iq_samples.dat"
    echo ""

    rm -f /tmp/gps_iq_samples.dat

    # Start recording in background
    python3 record_iq_samples.py /tmp/gps_iq_samples.dat 900 &
    RECORD_PID=$!

    # Start progress reporter in background (independent of recording)
    (
        RECORD_DURATION=900
        START_TIME=$(date +%s)
        while true; do
            ELAPSED=$(($(date +%s) - START_TIME))

            # Stop if elapsed time exceeds duration
            if [ $ELAPSED -ge $RECORD_DURATION ]; then
                break
            fi

            # Check if recording process is still alive
            if ! kill -0 $RECORD_PID 2>/dev/null; then
                break
            fi

            PROGRESS=$((ELAPSED * 100 / RECORD_DURATION))
            REMAINING=$((RECORD_DURATION - ELAPSED))
            python3 send_progress.py "recording" "$PROGRESS" "$ELAPSED" "$RECORD_DURATION" "Recording GPS samples: ${REMAINING}s remaining" 2>/dev/null || true

            # Show progress in terminal every 30 seconds
            if [ $((ELAPSED % 30)) -eq 0 ] && [ $ELAPSED -gt 0 ]; then
                echo "   [${ELAPSED}s] Recording... ($REMAINING seconds remaining)"
            fi

            sleep 10
        done
    ) &
    PROGRESS_PID=$!

    # Wait for recording to finish (with timeout)
    WAIT_COUNT=0
    while kill -0 $RECORD_PID 2>/dev/null && [ $WAIT_COUNT -lt 920 ]; do
        sleep 1
        WAIT_COUNT=$((WAIT_COUNT + 1))
    done

    # Kill progress reporter
    kill $PROGRESS_PID 2>/dev/null || true

    # Check if recording finished normally or timed out
    if kill -0 $RECORD_PID 2>/dev/null; then
        echo "⚠️  Recording timed out, killing process..."
        kill -9 $RECORD_PID 2>/dev/null
        RECORD_EXIT=1
    else
        wait $RECORD_PID 2>/dev/null
        RECORD_EXIT=$?
    fi

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
