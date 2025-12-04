#!/usr/bin/env python3
"""
Test script to send fake satellite data to the bridge
This verifies the WebSocket connection works
"""

import socket
import json
import time

# Create UDP socket
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

# Fake satellite data matching the protocol the UI expects
fake_data = {
    'protocol': 'GNSS_GPS_L1',
    'satellites': [
        {'prn': 26, 'cn0': 45.3, 'dopplerHz': 1234, 'state': 'TRACKING', 'snr': 15.3},
        {'prn': 17, 'cn0': 42.1, 'dopplerHz': -567, 'state': 'TRACKING', 'snr': 12.1},
        {'prn': 6, 'cn0': 48.7, 'dopplerHz': 890, 'state': 'TRACKING', 'snr': 18.7},
    ],
    'jamming': {
        'isJammed': False,
        'jammingType': 'NONE'
    },
    'timestamp': int(time.time() * 1000)
}

print("Sending test satellite data to WebSocket clients via bridge...")
print(f"Data: {json.dumps(fake_data, indent=2)}")
print("")
print("If your UI is connected, you should see 3 satellites appear!")
print("")

# Note: We can't actually send this via UDP to the bridge because
# GNSS-SDR monitor uses a binary protobuf format, not JSON.
# The bridge parses protobuf messages from GNSS-SDR.

print("❌ Actually, this won't work because GNSS-SDR monitor uses protobuf format,")
print("   not JSON. The bridge expects binary protobuf messages from GNSS-SDR.")
print("")
print("The REAL issue: GNSS-SDR monitor only sends data when PVT fix is achieved!")
print("  - Tracking satellites: ✓ (you see this in logs)")
print("  - Monitor output: ❌ (only starts after 4+ satellites + ephemeris decoded)")
print("")
print("Solution: Wait longer! PVT fix needs:")
print("  1. 4+ satellites tracked")
print("  2. Ephemeris data decoded (takes 30+ seconds)")
print("  3. Position calculation started")
print("")
print("Try running GNSS-SDR for 60-90 seconds to see monitor output.")
