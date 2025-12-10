#!/bin/bash
# Start SDRplay to GNSS-SDR pipeline via FIFO

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# FIFO path
FIFO_PATH="/tmp/gnss_fifo"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}Starting SDRplay to GNSS-SDR FIFO pipeline...${NC}"

# Check if SDRplay API is accessible
if ! DYLD_LIBRARY_PATH="/usr/local/lib:$DYLD_LIBRARY_PATH" SoapySDRUtil --find="driver=sdrplay" >/dev/null 2>&1; then
    echo -e "${RED}ERROR: SDRplay device not found!${NC}"
    echo "Please ensure SDRplay API service is running and device is connected."
    exit 1
fi

# Clean up any existing FIFO
if [ -p "$FIFO_PATH" ]; then
    echo "Removing existing FIFO..."
    rm -f "$FIFO_PATH"
fi

# Function to cleanup on exit
cleanup() {
    echo -e "\n${YELLOW}Stopping pipeline...${NC}"

    # Kill the SDRplay streamer
    if [ ! -z "$STREAMER_PID" ] && kill -0 "$STREAMER_PID" 2>/dev/null; then
        echo "Stopping SDRplay streamer..."
        kill "$STREAMER_PID" 2>/dev/null || true
    fi

    # Kill GNSS-SDR
    if [ ! -z "$GNSS_PID" ] && kill -0 "$GNSS_PID" 2>/dev/null; then
        echo "Stopping GNSS-SDR..."
        kill "$GNSS_PID" 2>/dev/null || true
    fi

    # Clean up FIFO
    if [ -p "$FIFO_PATH" ]; then
        rm -f "$FIFO_PATH"
    fi

    echo -e "${GREEN}Pipeline stopped.${NC}"
    exit 0
}

trap cleanup EXIT INT TERM

# Start SDRplay to FIFO streamer in background
echo -e "${GREEN}Starting SDRplay streamer...${NC}"
DYLD_LIBRARY_PATH="/usr/local/lib:$DYLD_LIBRARY_PATH" \
PYTHONPATH="/opt/homebrew/lib/python3.14/site-packages:$PYTHONPATH" \
python3 sdrplay_to_fifo.py "$FIFO_PATH" &
STREAMER_PID=$!

# Wait a moment for FIFO to be created
sleep 2

if [ ! -p "$FIFO_PATH" ]; then
    echo -e "${RED}ERROR: FIFO was not created!${NC}"
    exit 1
fi

echo -e "${GREEN}FIFO created at $FIFO_PATH${NC}"

# Start GNSS-SDR (it will connect to the FIFO)
echo -e "${GREEN}Starting GNSS-SDR...${NC}"
echo "GNSS-SDR will connect to the FIFO and start processing..."

DYLD_LIBRARY_PATH="/usr/local/lib:$DYLD_LIBRARY_PATH" \
gnss-sdr --config_file=gnss_fifo.conf &
GNSS_PID=$!

echo -e "${GREEN}Pipeline running!${NC}"
echo ""
echo "SDRplay Streamer PID: $STREAMER_PID"
echo "GNSS-SDR PID: $GNSS_PID"
echo ""
echo "The SDRplay is streaming GPS L1 data to GNSS-SDR via FIFO."
echo "Monitor GNSS-SDR output above for satellite acquisition and tracking."
echo ""
echo "Press Ctrl+C to stop the pipeline."

# Wait for either process to exit
wait -n

# If we get here, one of the processes died
echo -e "${RED}One of the processes terminated unexpectedly!${NC}"

# Check which one died
if ! kill -0 "$STREAMER_PID" 2>/dev/null; then
    echo "SDRplay streamer stopped unexpectedly"
fi

if ! kill -0 "$GNSS_PID" 2>/dev/null; then
    echo "GNSS-SDR stopped unexpectedly"
fi

# Cleanup will be called by trap