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
import glob
from datetime import datetime
from collections import defaultdict

# Force unbuffered output
sys.stdout = sys.__stdout__
sys.stderr = sys.__stderr__
import os
os.environ['PYTHONUNBUFFERED'] = '1'

# Track currently tracked satellites
tracked_satellites = {}
last_update_time = None

log_message_queue = []
log_file_position = 0

async def tail_log_file():
    """Tail the GNSS-SDR log file for Loss of lock messages"""
    global log_file_position

    while True:
        try:
            # Find the latest gnss-sdr.log file
            log_files = glob.glob('/var/folders/*/*/T/gnss-sdr.log')
            if not log_files:
                log_files = glob.glob('/tmp/gnss-sdr.log')

            if log_files:
                log_file = log_files[0]
                with open(log_file, 'r') as f:
                    # Seek to last position
                    f.seek(log_file_position)
                    new_lines = f.readlines()
                    log_file_position = f.tell()

                    # Parse new lines for Loss of lock
                    for line in new_lines:
                        if 'Loss of lock in channel' in line:
                            match = re.search(r'Loss of lock in channel (\d+)', line)
                            if match:
                                channel = int(match.group(1))
                                # Find which PRN was on this channel
                                for prn, info in list(tracked_satellites.items()):
                                    if info.get('channel') == channel:
                                        del tracked_satellites[prn]
                                        log_message_queue.append({
                                            'type': 'gnss_log',
                                            'level': 'warning',
                                            'message': f'⚠️ Lost lock on GPS PRN {prn} (channel {channel})',
                                            'timestamp': int(datetime.now().timestamp() * 1000)
                                        })
                                        break
                                else:
                                    # PRN unknown, just report channel
                                    log_message_queue.append({
                                        'type': 'gnss_log',
                                        'level': 'warning',
                                        'message': f'⚠️ Lost lock on channel {channel}',
                                        'timestamp': int(datetime.now().timestamp() * 1000)
                                    })
        except Exception as e:
            pass  # Ignore errors, just retry

        await asyncio.sleep(0.5)  # Check every 500ms

async def send_satellite_data(websocket_url='ws://localhost:8766'):
    """Connect to bridge WebSocket and send satellite updates"""
    last_sat_count = 0
    last_send_time = 0

    while True:
        try:
            current_time = datetime.now().timestamp()
            sat_count = len(tracked_satellites)

            # Send log messages if any
            if log_message_queue:
                async with websockets.connect(websocket_url, ping_interval=None) as websocket:
                    while log_message_queue:
                        log_msg = log_message_queue.pop(0)
                        await websocket.send(json.dumps(log_msg))

            # Send if: satellites changed OR 30 seconds passed OR we have satellites
            should_send = (
                sat_count != last_sat_count or  # Satellite count changed
                (current_time - last_send_time) >= 30 or  # 30 seconds elapsed
                (sat_count > 0 and (current_time - last_send_time) >= 1)  # Have satellites, send every 1s
            )

            if should_send and tracked_satellites:
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

                last_send_time = current_time
                last_sat_count = sat_count

            await asyncio.sleep(1)  # Check every second

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
        print(f"🛰️  Tracking PRN {prn} on channel {channel} (total: {len(tracked_satellites)})", flush=True)
        sys.stdout.flush()

        # Send log message to UI
        log_message_queue.append({
            'type': 'gnss_log',
            'level': 'info',
            'message': f'🛰️ Started tracking GPS PRN {prn} on channel {channel}',
            'timestamp': int(datetime.now().timestamp() * 1000)
        })
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

                # Send log message to UI
                log_message_queue.append({
                    'type': 'gnss_log',
                    'level': 'warning',
                    'message': f'⚠️ Lost lock on GPS PRN {prn} (channel {channel})',
                    'timestamp': int(datetime.now().timestamp() * 1000)
                })
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

    # Start WebSocket sender and log file tailer in background
    asyncio.create_task(send_satellite_data())
    asyncio.create_task(tail_log_file())

    # Send startup message
    log_message_queue.append({
        'type': 'gnss_log',
        'level': 'info',
        'message': '🚀 GNSS-SDR log parser started - monitoring for satellite tracking events',
        'timestamp': int(datetime.now().timestamp() * 1000)
    })

    # Read from stdin (piped from GNSS-SDR)
    print("📖 Reading GNSS-SDR output from stdin...")
    print("")

    try:
        while True:
            line = await asyncio.get_event_loop().run_in_executor(None, sys.stdin.readline)
            if not line:
                break  # EOF

            # Print the line (pass-through) with immediate flush
            print(line, end='', flush=True)
            sys.stdout.flush()

            # Parse for satellite tracking info
            parse_log_line(line.strip())

    except KeyboardInterrupt:
        print("\n\n🛑 Stopped by user")

if __name__ == '__main__':
    asyncio.run(main())
