#!/usr/bin/env python3
"""
Send continuous progress updates to WebSocket for UI
This runs alongside the GNSS pipeline to keep the UI informed
"""

import asyncio
import websockets
import json
import sys
import time
import subprocess
from datetime import datetime

async def send_continuous_updates():
    """Send progress updates every second"""
    start_time = time.time()

    while True:
        try:
            # Check if GNSS-SDR is running
            gnss_running = False
            streamer_running = False

            try:
                result = subprocess.run(['pgrep', '-f', 'gnss-sdr'],
                                      capture_output=True, text=True, timeout=1)
                gnss_running = (result.returncode == 0)
            except:
                pass

            try:
                result = subprocess.run(['pgrep', '-f', 'sdrplay_fifo'],
                                      capture_output=True, text=True, timeout=1)
                streamer_running = (result.returncode == 0)
            except:
                pass

            if gnss_running and streamer_running:
                elapsed = int(time.time() - start_time)

                # Send progress update
                async with websockets.connect('ws://localhost:8766', ping_interval=None) as websocket:
                    # Send progress message
                    progress_msg = {
                        'type': 'progress',
                        'phase': 'streaming',  # 'recording' or 'streaming' or 'processing'
                        'progress': 0,  # No percentage for continuous streaming
                        'elapsed': elapsed,
                        'total': 0,  # 0 means continuous
                        'message': f'Streaming GPS L1 data continuously',
                        'timestamp': int(datetime.now().timestamp() * 1000)
                    }
                    await websocket.send(json.dumps(progress_msg))

                    # Also send status update
                    status_msg = {
                        'type': 'status',
                        'collecting': True,
                        'streaming': True,
                        'satellites_visible': 0,  # Will be updated by parse_gnss_logs
                        'message': 'GPS data collection in progress',
                        'timestamp': int(datetime.now().timestamp() * 1000)
                    }
                    await websocket.send(json.dumps(status_msg))

            await asyncio.sleep(1)  # Send updates every second

        except Exception as e:
            print(f"Error sending progress: {e}", file=sys.stderr)
            await asyncio.sleep(5)  # Wait longer on error

async def main():
    """Main function"""
    print("Starting continuous progress reporter...")
    print("Sending updates to ws://localhost:8766")

    try:
        await send_continuous_updates()
    except KeyboardInterrupt:
        print("\nStopped by user")

if __name__ == '__main__':
    asyncio.run(main())