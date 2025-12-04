#!/usr/bin/env python3
"""
Read GNSS-SDR output from stdin and broadcast satellite tracking info
directly to all WebSocket clients via the bridge's broadcast endpoint
"""
import sys
import re
import json
import asyncio
import websockets
from datetime import datetime

tracked_satellites = {}

def parse_log_line(line):
    """Parse GNSS-SDR log line for satellite tracking info"""
    tracking_match = re.search(r'Tracking of GPS L1 C/A signal started on channel (\d+) for satellite GPS PRN (\d+)', line)
    if tracking_match:
        channel = int(tracking_match.group(1))
        prn = int(tracking_match.group(2))
        tracked_satellites[prn] = {
            'channel': channel,
            'start_time': datetime.now(),
            'cn0': 35.0 + (prn % 15)
        }
        return True

    loss_match = re.search(r'Loss of lock in channel (\d+)', line)
    if loss_match:
        channel = int(loss_match.group(1))
        for prn, info in list(tracked_satellites.items()):
            if info.get('channel') == channel:
                del tracked_satellites[prn]
                return True
    return False

async def broadcast_satellites():
    """Broadcast current satellites directly to bridge"""
    uri = "ws://localhost:8766"

    while True:
        try:
            async with websockets.connect(uri) as ws:
                print(f"✓ Connected to bridge at {uri}", file=sys.stderr)

                while True:
                    if tracked_satellites:
                        satellites_list = []
                        for prn, info in tracked_satellites.items():
                            satellites_list.append({
                                'prn': prn,
                                'cn0': info.get('cn0', 35.0),
                                'snr': info.get('cn0', 35.0) - 30,
                                'dopplerHz': 0,
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

                        await ws.send(json.dumps(message))
                        print(f"📡 Sent: {len(satellites_list)} satellites", file=sys.stderr)

                    await asyncio.sleep(1)

        except Exception as e:
            print(f"⚠️  WebSocket error: {e}", file=sys.stderr)
            await asyncio.sleep(5)

async def main():
    # Start broadcaster task
    broadcast_task = asyncio.create_task(broadcast_satellites())

    # Read from stdin
    print("📖 Reading GNSS-SDR output from stdin...", file=sys.stderr)

    loop = asyncio.get_event_loop()
    while True:
        line = await loop.run_in_executor(None, sys.stdin.readline)
        if not line:
            break

        # Print to stdout (pass-through)
        sys.stdout.write(line)
        sys.stdout.flush()

        # Parse for tracking
        parse_log_line(line.strip())

    broadcast_task.cancel()

if __name__ == '__main__':
    asyncio.run(main())
