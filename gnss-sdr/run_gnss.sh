#!/bin/bash
# Wrapper script to run GNSS pipeline with proper library paths

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Set library paths for SDRplay
export DYLD_LIBRARY_PATH="/usr/local/lib:$DYLD_LIBRARY_PATH"
export PYTHONPATH="/opt/homebrew/lib/python3.14/site-packages:$PYTHONPATH"

# Run the simple pipeline using direct SDRplay API (more reliable)
exec python3 run_gnss_simple.py "$@"