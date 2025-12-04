#!/bin/bash

################################################################################
# Continuous GNSS-SDR Script (Looping Record + Process)
#
# This script runs FOREVER in a loop:
# 1. Record 2 minutes of GPS IQ samples
# 2. Process with GNSS-SDR + Bridge
# 3. Repeat from step 1
#
# This gives you continuous operation with fresh data every cycle.
#
# Usage: ./continuous_start.sh
# Stop: Press Ctrl+C
################################################################################

set -e  # Exit on error

echo "========================================================================"
echo "GNSS-SDR Continuous Looping Mode"
echo "========================================================================"
echo ""
echo "This script will run FOREVER in a loop:"
echo "  1. Record 2 minutes of GPS samples"
echo "  2. Process with GNSS-SDR"
echo "  3. Repeat"
echo ""
echo "Press Ctrl+C to stop at any time"
echo ""

# Set environment variables
export DYLD_LIBRARY_PATH="/usr/local/lib:$DYLD_LIBRARY_PATH"
export PYTHONPATH="/opt/homebrew/lib/python3.14/site-packages:$PYTHONPATH"

# Cleanup function
cleanup() {
    echo ""
    echo "🛑 Stopping..."
    pkill -9 -f "gnss-sdr" 2>/dev/null || true
    pkill -9 -f "gnss_sdr_bridge" 2>/dev/null || true
    pkill -9 -f "record_iq" 2>/dev/null || true
    echo "✓ Cleanup complete"
    exit 0
}

# Trap Ctrl+C
trap cleanup SIGINT SIGTERM

# Initial cleanup
echo "🧹 Cleaning up previous processes..."
pkill -9 -f "python.*sdrplay" 2>/dev/null || true
pkill -9 -f "gnss-sdr" 2>/dev/null || true
pkill -9 -f "gnss_sdr_bridge" 2>/dev/null || true
pkill -9 -f "record_iq" 2>/dev/null || true
sleep 2
echo "✓ Cleanup complete"
echo ""

# Check SDRPlay once
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
echo "Starting continuous loop..."
echo ""

# Loop forever
CYCLE=1
while true; do
    echo "========================================================================"
    echo "CYCLE #$CYCLE - $(date '+%Y-%m-%d %H:%M:%S')"
    echo "========================================================================"
    echo ""

    # Step 1: Record
    echo "📡 Recording 2 minutes of GPS samples..."
    echo "   Output: /tmp/gps_iq_samples.dat"
    echo ""

    rm -f /tmp/gps_iq_samples.dat

    if ! python3 record_iq_samples.py /tmp/gps_iq_samples.dat 120; then
        echo ""
        echo "⚠️  Recording failed! Retrying in 10 seconds..."
        sleep 10
        continue
    fi

    echo ""
    FILE_SIZE=$(ls -lh /tmp/gps_iq_samples.dat 2>/dev/null | awk '{print $5}')
    echo "✅ Recording complete! Size: $FILE_SIZE"
    echo ""

    # Step 2: Process with GNSS-SDR
    echo "🛰️  Processing with GNSS-SDR..."
    echo "   Config: gnss_sdr_file.conf"
    echo "   This will take ~60 seconds (file processing time)"
    echo ""

    # Start GNSS-SDR in background
    DYLD_LIBRARY_PATH="/usr/local/lib:$DYLD_LIBRARY_PATH" \
        gnss-sdr --config_file=gnss_sdr_file.conf > /tmp/gnss_sdr_output.log 2>&1 &
    GNSS_PID=$!

    # Wait for GNSS-SDR to finish (or timeout after 120 seconds)
    WAIT_TIME=0
    while kill -0 $GNSS_PID 2>/dev/null; do
        sleep 5
        WAIT_TIME=$((WAIT_TIME + 5))

        # Show progress every 15 seconds
        if [ $((WAIT_TIME % 15)) -eq 0 ]; then
            # Check for satellite tracking
            SAT_COUNT=$(grep -c "Tracking of GPS L1 C/A signal started" /tmp/gnss_sdr_output.log 2>/dev/null || echo "0")
            echo "   [${WAIT_TIME}s] Processing... ($SAT_COUNT satellites tracked so far)"
        fi

        # Timeout after 120 seconds
        if [ $WAIT_TIME -ge 120 ]; then
            echo "   ⚠️  Timeout reached, stopping GNSS-SDR..."
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

    # Check for position fix
    if grep -q "Position" /tmp/gnss_sdr_output.log 2>/dev/null; then
        echo "   ✅ Position fix achieved!"
        grep "Position" /tmp/gnss_sdr_output.log 2>/dev/null | tail -1 | sed 's/^/     /'
        echo ""
    fi

    echo "Waiting 5 seconds before next cycle..."
    sleep 5
    echo ""

    CYCLE=$((CYCLE + 1))
done
