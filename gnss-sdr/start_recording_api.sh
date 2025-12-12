#!/bin/bash
# Start GPS Recording API Server

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Set library paths
export DYLD_LIBRARY_PATH="/usr/local/lib:$DYLD_LIBRARY_PATH"
export PYTHONUNBUFFERED=1

echo "Starting GPS Recording API Server..."
echo "Press Ctrl+C to stop"
echo ""

python3 -u recording_api_simple.py
