#!/usr/bin/env python3
"""
Send recording progress updates to WebSocket clients
"""
import asyncio
import websockets
import json
import sys
from datetime import datetime

async def send_progress(phase, progress_percent=0, elapsed_time=0, total_time=0, message=""):
    """
    Send progress update to WebSocket bridge

    Args:
        phase: 'recording' | 'processing' | 'waiting'
        progress_percent: 0-100
        elapsed_time: seconds elapsed
        total_time: total expected seconds
        message: status message
    """
    try:
        async with websockets.connect('ws://localhost:8766', ping_interval=None, timeout=2) as websocket:
            status_message = {
                'type': 'progress',
                'phase': phase,
                'progress': progress_percent,
                'elapsed': elapsed_time,
                'total': total_time,
                'message': message,
                'timestamp': int(datetime.now().timestamp() * 1000)
            }
            await websocket.send(json.dumps(status_message))
    except Exception as e:
        # Silently fail if bridge not ready
        pass

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python3 send_progress.py <phase> [progress] [elapsed] [total] [message]")
        sys.exit(1)

    phase = sys.argv[1]
    progress = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    elapsed = int(sys.argv[3]) if len(sys.argv) > 3 else 0
    total = int(sys.argv[4]) if len(sys.argv) > 4 else 0
    message = sys.argv[5] if len(sys.argv) > 5 else ""

    asyncio.run(send_progress(phase, progress, elapsed, total, message))
