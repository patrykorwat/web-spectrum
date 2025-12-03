#!/bin/bash
# Wrapper script to run SDRPlay bridge with correct Python paths

# Add SoapySDR Python bindings to PYTHONPATH (from Homebrew installation)
export PYTHONPATH="/opt/homebrew/Cellar/soapysdr/0.8.1_1/lib/python3.14/site-packages:$PYTHONPATH"

# Add SDRPlay API library path for SoapySDRPlay3
export DYLD_LIBRARY_PATH="/usr/local/lib:$DYLD_LIBRARY_PATH"

# Activate virtual environment
source venv/bin/activate

# Run the bridge with all arguments passed through
python sdrplay_bridge.py "$@"
