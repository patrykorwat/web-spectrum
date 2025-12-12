#!/bin/bash
# Test GPS recording processing with GNSS-SDR

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

export DYLD_LIBRARY_PATH="/usr/local/lib:$DYLD_LIBRARY_PATH"

CONFIG_FILE="recordings/aggressive_acq.conf"
LOG_FILE="recordings/gnss_processing.log"

echo "========================================================================"
echo "Testing GNSS-SDR Processing"
echo "========================================================================"
echo ""
echo "Config: $CONFIG_FILE"
echo "Log: $LOG_FILE"
echo ""
echo "This will run for 2-3 minutes to see if satellites are acquired..."
echo "Press Ctrl+C to stop"
echo ""

# Run GNSS-SDR and capture output
gnss-sdr --config_file="$CONFIG_FILE" 2>&1 | tee "$LOG_FILE"
