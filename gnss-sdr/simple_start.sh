#!/bin/bash

################################################################################
# Simple GNSS-SDR Start Script (File-Based Mode)
#
# This is the PROVEN working approach:
# 1. Record 2 minutes of IQ samples to file
# 2. Process with GNSS-SDR
# 3. Bridge forwards results to Web UI
#
# Usage: ./simple_start.sh
################################################################################

set -e  # Exit on error

echo "========================================================================"
echo "GNSS-SDR Simple Start (File-Based Mode)"
echo "========================================================================"
echo ""

# Clean up any previous processes
echo "🧹 Cleaning up previous processes..."
pkill -9 -f "python.*sdrplay" 2>/dev/null || true
pkill -9 -f "gnss-sdr" 2>/dev/null || true
pkill -9 -f "gnss_sdr_bridge" 2>/dev/null || true
pkill -9 -f "record_iq" 2>/dev/null || true
sleep 2
echo "✓ Cleanup complete"
echo ""

# Set environment variables
export DYLD_LIBRARY_PATH="/usr/local/lib:$DYLD_LIBRARY_PATH"
export PYTHONPATH="/opt/homebrew/lib/python3.14/site-packages:$PYTHONPATH"

# Check if SDRPlay is connected
echo "🔍 Checking SDRPlay connection..."
if ! python3 -c "import SoapySDR; devices = SoapySDR.Device.enumerate('driver=sdrplay'); exit(0 if devices else 1)" 2>/dev/null; then
    echo "❌ ERROR: SDRPlay not found!"
    echo "   Please check:"
    echo "   • SDRPlay is connected via USB"
    echo "   • SDRPlay API is installed"
    echo "   • No other program is using the SDRPlay"
    exit 1
fi
echo "✓ SDRPlay found"
echo ""

# Step 1: Record IQ samples
echo "========================================================================"
echo "Step 1: Recording IQ Samples"
echo "========================================================================"
echo ""
echo "⚠️  IMPORTANT: Make sure your GPS antenna has a CLEAR SKY VIEW!"
echo ""
echo "Recording 2 minutes of GPS L1 samples..."
echo "Output: /tmp/gps_iq_samples.dat"
echo ""
echo "This will take 2 minutes. Please wait..."
echo ""

rm -f /tmp/gps_iq_samples.dat

if ! python3 record_iq_samples.py /tmp/gps_iq_samples.dat 120; then
    echo ""
    echo "❌ ERROR: Recording failed!"
    echo "   Check that SDRPlay is connected and not in use."
    exit 1
fi

echo ""
echo "✅ Recording complete!"
echo ""

# Check file size
FILE_SIZE=$(ls -lh /tmp/gps_iq_samples.dat | awk '{print $5}')
echo "   File: /tmp/gps_iq_samples.dat"
echo "   Size: $FILE_SIZE"
echo ""

# Step 2: Start GNSS-SDR and Bridge
echo "========================================================================"
echo "Step 2: Starting GNSS-SDR + Bridge"
echo "========================================================================"
echo ""
echo "Starting bridge with file-based processing..."
echo "This will:"
echo "  1. Start GNSS-SDR to process the recorded file"
echo "  2. Start WebSocket bridge on port 8766"
echo "  3. Forward satellite data to your web UI"
echo ""
echo "Connect your browser to: ws://localhost:8766"
echo ""
echo "Press Ctrl+C to stop"
echo "========================================================================"
echo ""

# Start bridge with file config
exec python3 gnss_sdr_bridge.py --config gnss_sdr_file.conf
