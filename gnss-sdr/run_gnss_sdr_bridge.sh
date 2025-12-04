#!/bin/bash

################################################################################
# GNSS-SDR Bridge Runner (with Continuous Recording)
#
# This script starts the GNSS-SDR → Web-Spectrum bridge with continuous IQ recording
#
# Usage:
#   ./run_gnss_sdr_bridge.sh              # Auto-start everything (recommended)
#   ./run_gnss_sdr_bridge.sh --no-auto-start  # Manual mode
#
# This will:
#   1. Kill any previous instances
#   2. Start continuous IQ recorder (SDRPlay → /tmp/gps_iq_samples.dat)
#   3. Start GNSS-SDR reading from the file
#   4. Start Python bridge (receives GNSS-SDR data, serves WebSocket)
#   5. Forward professional GNSS results to web UI
#
# ONE TERMINAL OPERATION - No more juggling terminals!
#
################################################################################

echo "Cleaning up previous instances..."
pkill -9 -f "python.*sdrplay" 2>/dev/null
pkill -9 -f "gnss-sdr" 2>/dev/null
pkill -9 -f "gnss_sdr_bridge.py" 2>/dev/null
pkill -9 -f "rebuild_gnss" 2>/dev/null
pkill -9 -f "record_iq" 2>/dev/null
sleep 2
echo "✓ Cleanup complete"
echo ""

# Check Python installation
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python 3 not found!"
    echo "Install with: brew install python3"
    exit 1
fi

# Check dependencies
echo "Checking Python dependencies..."
python3 -c "import websockets" 2>/dev/null || {
    echo "Installing websockets..."
    pip3 install websockets
}

python3 -c "import numpy" 2>/dev/null || {
    echo "Installing numpy..."
    pip3 install numpy
}

# Check if GNSS-SDR is installed
if ! command -v gnss-sdr &> /dev/null; then
    echo ""
    echo "WARNING: gnss-sdr not found in PATH!"
    echo ""
    echo "Install GNSS-SDR first:"
    echo "  ./install_gnss_sdr.sh"
    echo ""
    echo "Or if already installed, add to PATH:"
    echo "  export PATH=\"/usr/local/bin:\$PATH\""
    echo ""
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Check if config file exists
if [ ! -f "gnss_sdr_file_continuous.conf" ]; then
    echo "ERROR: gnss_sdr_file_continuous.conf not found!"
    echo "Make sure you're running this from the gnss-sdr directory."
    exit 1
fi

echo ""
echo "============================================================"
echo "GNSS-SDR Bridge Starting (Continuous Mode)..."
echo "============================================================"
echo ""
echo "This bridge will:"
echo "  1. Start continuous IQ recorder (SDRPlay → /tmp/gps_iq_samples.dat)"
echo "  2. Start GNSS-SDR reading from file"
echo "  3. Listen for GNSS-SDR monitor data (UDP port 1234)"
echo "  4. Serve WebSocket on port 8766"
echo "  5. Send professional GNSS results to web UI"
echo ""
echo "Connect your web UI to: ws://localhost:8766"
echo ""
echo "============================================================"
echo ""

# Activate virtual environment if it exists (needed for SoapySDR Python bindings)
if [ -d "venv" ]; then
    echo "Activating virtual environment..."
    source venv/bin/activate
fi

# Set library path for SDRPlay API (macOS)
export DYLD_LIBRARY_PATH="/usr/local/lib:$DYLD_LIBRARY_PATH"

# Set Python path for SoapySDR Python bindings
export PYTHONPATH="/opt/homebrew/lib/python3.14/site-packages:$PYTHONPATH"

# Run bridge (passes all arguments through)
python3 gnss_sdr_bridge.py "$@"
