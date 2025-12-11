#!/usr/bin/env python3
"""
Test WebSocket status messages
"""

import asyncio
import websockets
import json
from datetime import datetime

async def send_test_status():
    """Send a test status message to the WebSocket"""
    try:
        async with websockets.connect('ws://localhost:8766', ping_interval=None) as websocket:
            # Send status update
            status_msg = {
                'type': 'status',
                'collecting': True,
                'streaming': True,
                'satellites_visible': 8,
                'message': 'GPS data collection active - test message',
                'timestamp': int(datetime.now().timestamp() * 1000)
            }
            await websocket.send(json.dumps(status_msg))
            print(f"✅ Sent status: {status_msg['message']}")

            # Send progress update
            progress_msg = {
                'type': 'progress',
                'phase': 'streaming',
                'progress': 75,
                'elapsed': 120,
                'total': 0,
                'message': 'Streaming GPS data... (test)',
                'timestamp': int(datetime.now().timestamp() * 1000)
            }
            await websocket.send(json.dumps(progress_msg))
            print(f"✅ Sent progress: {progress_msg['message']}")

            print("\nMessages sent successfully!")
            print("Check if UI shows:")
            print("  1. Collection status as active")
            print("  2. Progress bar at 75%")
            print("  3. Status message about GPS data collection")

    except Exception as e:
        print(f"❌ Error: {e}")
        print("\nMake sure:")
        print("  1. WebSocket bridge is running (ws://localhost:8766)")
        print("  2. UI is connected in GNSS-SDR mode")

if __name__ == '__main__':
    asyncio.run(send_test_status())