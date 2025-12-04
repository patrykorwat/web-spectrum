#!/usr/bin/env python3
"""Test sending satellite data to WebSocket clients"""
import asyncio
import websockets
import json
from datetime import datetime

async def send_test_message():
    """Send a test GNSS message to all connected clients"""
    uri = "ws://localhost:8766"

    # Test message with satellite data
    message = {
        'protocol': 'GNSS_GPS_L1',
        'satellites': [
            {'prn': 12, 'cn0': 42.0, 'snr': 12.0, 'dopplerHz': 0, 'state': 'TRACKING',
             'carrierPhase': 0, 'codePhase': 0, 'carrierLock': True, 'bitSync': False, 'subframeSync': False},
            {'prn': 15, 'cn0': 38.5, 'snr': 8.5, 'dopplerHz': 0, 'state': 'TRACKING',
             'carrierPhase': 0, 'codePhase': 0, 'carrierLock': True, 'bitSync': False, 'subframeSync': False},
            {'prn': 6, 'cn0': 45.2, 'snr': 15.2, 'dopplerHz': 0, 'state': 'TRACKING',
             'carrierPhase': 0, 'codePhase': 0, 'carrierLock': True, 'bitSync': False, 'subframeSync': False},
        ],
        'jamming': {
            'isJammed': False,
            'jammingType': 'NONE',
            'noiseFloorDb': -140,
            'avgCN0': 41.9,
            'minCN0': 38.5,
            'maxCN0': 45.2,
            'numTracking': 3
        },
        'timestamp': int(datetime.now().timestamp() * 1000)
    }

    try:
        async with websockets.connect(uri) as websocket:
            print(f"✓ Connected to {uri}")
            await websocket.send(json.dumps(message))
            print(f"✓ Sent test message with {len(message['satellites'])} satellites")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == '__main__':
    asyncio.run(send_test_message())
