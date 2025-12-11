#!/usr/bin/env python3
"""
Pure Async GNSS Streamer - ZERO blocking operations
Simulates satellite acquisition and streams via WebSocket
"""

import asyncio
import websockets
import json
import time
import random
import numpy as np
from datetime import datetime

class AsyncGNSSStreamer:
    def __init__(self, websocket_port=8766):
        self.websocket_port = websocket_port
        self.clients = set()
        self.running = False

        # Simulated satellite state
        self.satellites = {}
        self.acquisition_time = time.time()

    async def websocket_handler(self, websocket):
        """Handle WebSocket client connections"""
        self.clients.add(websocket)
        client_addr = websocket.remote_address
        print(f"[WebSocket] Client connected: {client_addr} (total: {len(self.clients)})")

        try:
            async for message in websocket:
                # Handle messages if needed
                pass
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            self.clients.discard(websocket)
            print(f"[WebSocket] Client disconnected: {client_addr} (remaining: {len(self.clients)})")

    async def simulate_gnss(self):
        """Simulate GNSS satellite acquisition and tracking - PURE ASYNC"""
        # Simulate realistic satellite acquisition over time
        prns = [3, 6, 7, 9, 11, 14, 16, 18, 21, 22, 26, 28]

        while self.running:
            elapsed = time.time() - self.acquisition_time

            # Gradually acquire satellites (realistic timing)
            num_sats_acquired = min(len(prns), int(elapsed / 10) + 1)  # 1 sat every 10 sec

            # Build satellite list
            satellites_list = []
            for i in range(num_sats_acquired):
                prn = prns[i]

                # Simulate realistic C/N0 with variation
                base_cn0 = 42 + random.uniform(-3, 3)
                cn0 = base_cn0 + np.sin(elapsed / 20.0 + prn) * 2.0  # Slow variation

                # Simulate doppler
                doppler = random.uniform(-3000, 3000) + np.sin(elapsed / 30.0 + prn) * 500

                satellites_list.append({
                    'prn': prn,
                    'cn0': cn0,
                    'snr': cn0 - 30,
                    'dopplerHz': doppler,
                    'state': 'TRACKING',
                    'carrierPhase': random.uniform(0, 2*np.pi),
                    'codePhase': random.uniform(0, 1023),
                    'carrierLock': True,
                    'bitSync': elapsed > 30 + i * 10,  # Bit sync after 30s
                    'subframeSync': elapsed > 60 + i * 10  # Subframe after 60s
                })

            if satellites_list:
                # Calculate jamming metrics
                cn0_values = [s['cn0'] for s in satellites_list]
                avg_cn0 = np.mean(cn0_values)
                cn0_std = np.std(cn0_values)

                # Detect anomalies
                is_jammed = False
                jamming_type = 'NONE'

                if cn0_std < 1.0 and len(cn0_values) > 4:
                    is_jammed = True
                    jamming_type = 'POSSIBLE_SPOOFING'
                elif avg_cn0 < 35:
                    is_jammed = True
                    jamming_type = 'BROADBAND_JAMMING'

                # Build message
                message = {
                    'protocol': 'GNSS_GPS_L1',
                    'satellites': satellites_list,
                    'jamming': {
                        'isJammed': is_jammed,
                        'jammingType': jamming_type,
                        'noiseFloorDb': -140,
                        'avgCN0': avg_cn0,
                        'minCN0': min(cn0_values),
                        'maxCN0': max(cn0_values),
                        'numTracking': len(satellites_list),
                        'cn0StdDev': cn0_std,
                        'cn0Variation': cn0_std,
                        'jammingSeverity': 'LOW' if is_jammed else 'NONE',
                        'jammerConfidence': 0.3 if is_jammed else 0.0,
                        'detectionMethod': 'CN0_CORRELATION' if is_jammed else 'NONE',
                        'jammingToSignalRatio': 0.1 if is_jammed else 0.0,
                        'dopplerVariation': 1500.0,
                        'cn0Correlation': 0.2 if is_jammed else 0.1
                    },
                    'timestamp': int(time.time() * 1000)
                }

                # Send to all clients (ASYNC broadcast)
                if self.clients:
                    await asyncio.gather(
                        *[client.send(json.dumps(message)) for client in self.clients],
                        return_exceptions=True
                    )

                    print(f"[GNSS] Tracking {len(satellites_list)} satellites, "
                          f"Avg C/N0: {avg_cn0:.1f} dB-Hz, "
                          f"Clients: {len(self.clients)}")

            # Send update every 1 second (realistic)
            await asyncio.sleep(1.0)

    async def send_log_messages(self):
        """Send informational log messages to UI"""
        messages = [
            "🚀 GNSS-SDR simulation started - monitoring for satellite tracking events",
            "📡 Searching for GPS satellites on L1 band (1575.42 MHz)...",
            "🛰️ Signal acquisition in progress...",
        ]

        for msg in messages:
            if self.clients:
                log_msg = {
                    'type': 'gnss_log',
                    'level': 'info',
                    'message': msg,
                    'timestamp': int(time.time() * 1000)
                }
                await asyncio.gather(
                    *[client.send(json.dumps(log_msg)) for client in self.clients],
                    return_exceptions=True
                )
            await asyncio.sleep(2.0)

    async def run(self):
        """Main async run loop - ZERO blocking"""
        print("=" * 70)
        print("🛰️  Pure Async GNSS Streamer (ZERO Blocking)")
        print("=" * 70)
        print()
        print("Features:")
        print("  • Pure async/await (NO blocking operations)")
        print("  • Simulated satellite acquisition")
        print("  • WebSocket streaming")
        print("  • Realistic timing and metrics")
        print()

        # Start WebSocket server
        print(f"[WebSocket] Starting server on port {self.websocket_port}...")
        server = await websockets.serve(
            self.websocket_handler,
            'localhost',
            self.websocket_port,
            ping_interval=None,
            max_size=None
        )
        print(f"[WebSocket] ✓ Server listening on ws://localhost:{self.websocket_port}")
        print()

        self.running = True
        self.acquisition_time = time.time()

        print("=" * 70)
        print("🚀 STREAMING ACTIVE")
        print("=" * 70)
        print()
        print("Simulating GNSS satellite acquisition...")
        print("Satellites will appear gradually (1 every 10 seconds)")
        print("Press Ctrl+C to stop")
        print("-" * 70)
        print()

        # Start tasks
        gnss_task = asyncio.create_task(self.simulate_gnss())
        log_task = asyncio.create_task(self.send_log_messages())

        try:
            await asyncio.Future()  # Run forever
        except asyncio.CancelledError:
            print("\n[Main] Shutting down...")
        finally:
            self.running = False
            gnss_task.cancel()
            log_task.cancel()

            server.close()
            await server.wait_closed()
            print("[WebSocket] ✓ Server closed")
            print("\n👋 Goodbye!")

async def main():
    streamer = AsyncGNSSStreamer(websocket_port=8766)

    loop = asyncio.get_running_loop()
    import signal

    def shutdown():
        tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
        for task in tasks:
            task.cancel()

    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, shutdown)

    await streamer.run()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n🛑 Interrupted by user")
