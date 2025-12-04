#!/usr/bin/env python3
"""
Parse GNSS-SDR log output and send satellite tracking info to WebSocket clients
This allows UI to show satellites BEFORE PVT monitor data is available
"""

import re
import json
import asyncio
import websockets
import sys
from datetime import datetime
from collections import defaultdict

# Track currently tracked satellites
tracked_satellites = {}
last_update_time = None

async def send_satellite_data(websocket_url='ws://localhost:8766'):
    """Connect to bridge WebSocket and send satellite updates"""
    while True:
        try:
            if tracked_satellites:
                # Build message in GNSS protocol format
                satellites_list = []
                for prn, info in tracked_satellites.items():
                    satellites_list.append({
                        'prn': prn,
                        'cn0': info.get('cn0', 35.0),  # Default estimate
                        'snr': info.get('cn0', 35.0) - 30,
                        'dopplerHz': 0,  # Not available from logs
                        'state': 'TRACKING',
                        'carrierPhase': 0,
                        'codePhase': 0,
                        'carrierLock': True,
                        'bitSync': False,
                        'subframeSync': False
                    })

                message = {
                    'protocol': 'GNSS_GPS_L1',
                    'satellites': satellites_list,
                    'jamming': {
                        'isJammed': False,
                        'jammingType': 'NONE',
                        'noiseFloorDb': -140,
                        'avgCN0': sum(s['cn0'] for s in satellites_list) / len(satellites_list) if satellites_list else 0,
                        'minCN0': min(s['cn0'] for s in satellites_list) if satellites_list else 0,
                        'maxCN0': max(s['cn0'] for s in satellites_list) if satellites_list else 0,
                        'numTracking': len(satellites_list)
                    },
                    'timestamp': int(datetime.now().timestamp() * 1000)
                }

                # Send with a fresh connection each time (same as test_satellite_message.py)
                async with websockets.connect(websocket_url, ping_interval=None) as websocket:
                    await websocket.send(json.dumps(message))
                    print(f"📡 Sent update: {len(satellites_list)} satellites")

            await asyncio.sleep(1)  # Send updates every second

        except Exception as e:
            print(f"⚠️  WebSocket error: {e}")
            await asyncio.sleep(1)  # Retry quickly

def parse_log_line(line):
    """Parse GNSS-SDR log line for satellite tracking info"""
    # Match: "Tracking of GPS L1 C/A signal started on channel X for satellite GPS PRN YY"
    tracking_match = re.search(r'Tracking of GPS L1 C/A signal started on channel (\d+) for satellite GPS PRN (\d+)', line)
    if tracking_match:
        channel = int(tracking_match.group(1))
        prn = int(tracking_match.group(2))
        tracked_satellites[prn] = {
            'channel': channel,
            'start_time': datetime.now(),
            'cn0': 35.0 + (prn % 15)  # Fake C/N0 based on PRN
        }
        print(f"🛰️  Tracking PRN {prn} on channel {channel} (total: {len(tracked_satellites)})")
        return True

    # Match: "Loss of lock in channel X"
    loss_match = re.search(r'Loss of lock in channel (\d+)', line)
    if loss_match:
        channel = int(loss_match.group(1))
        # Remove satellite from this channel
        for prn, info in list(tracked_satellites.items()):
            if info.get('channel') == channel:
                del tracked_satellites[prn]
                print(f"⚠️  Lost lock on PRN {prn} channel {channel} (remaining: {len(tracked_satellites)})")
                return True

    return False

async def main():
    """Main function"""
    print("=" * 70)
    print("GNSS-SDR Log Parser → WebSocket Bridge")
    print("=" * 70)
    print("")
    print("This script:")
    print("  1. Parses GNSS-SDR stdout for 'Tracking' messages")
    print("  2. Sends satellite data to WebSocket clients")
    print("  3. Shows satellites in UI BEFORE monitor data available")
    print("")
    print("Usage: gnss-sdr ... | python3 parse_gnss_logs.py")
    print("")

    # Start WebSocket sender in background
    asyncio.create_task(send_satellite_data())

    # Read from stdin (piped from GNSS-SDR)
    print("📖 Reading GNSS-SDR output from stdin...")
    print("")

    try:
        while True:
            line = await asyncio.get_event_loop().run_in_executor(None, sys.stdin.readline)
            if not line:
                break  # EOF

            # Print the line (pass-through)
            print(line, end='')

            # Parse for satellite tracking info
            parse_log_line(line.strip())

    except KeyboardInterrupt:
        print("\n\n🛑 Stopped by user")

if __name__ == '__main__':
    asyncio.run(main())
