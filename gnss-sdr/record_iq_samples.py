#!/usr/bin/env python3
"""
Wrapper script that redirects to the Direct API recorder
This maintains compatibility with existing scripts expecting record_iq_samples.py
"""
import sys
import subprocess
import os

# Get the directory where this script is located
script_dir = os.path.dirname(os.path.abspath(__file__))
direct_recorder = os.path.join(script_dir, 'record_iq_samples_sdrplay_direct.py')

# Pass all arguments to the Direct API recorder
sys.exit(subprocess.call([sys.executable, direct_recorder] + sys.argv[1:]))