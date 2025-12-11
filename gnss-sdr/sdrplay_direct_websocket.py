#!/usr/bin/env python3
"""
SDRplay Direct API → WebSocket Streamer (ZERO blocking operations)
Streams IQ samples directly to WebSocket clients with no FIFO, no files, pure async
"""

import asyncio
import websockets
import numpy as np
import json
import time
import signal
import sys
import os
from collections import deque
from datetime import datetime

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sdrplay_direct import SDRplayDevice

class AsyncSDRplayWebSocketStreamer:
    def __init__(self, websocket_port=8765):
        self.websocket_port = websocket_port
        self.sdr = None
        self.sample_queue = deque(maxlen=1000)  # Ring buffer, auto-drops old data
        self.running = False
        self.clients = set()
        self.samples_received = 0
        self.samples_sent = 0
        self.last_report = time.time()

    def data_callback(self, samples):
        """Called by SDRplay (runs in separate thread) - NEVER blocks"""
        if self.running:
            self.samples_received += len(samples)
            # Just append to queue - if full, oldest data is auto-dropped
            self.sample_queue.append(samples.copy())

    async def websocket_handler(self, websocket, path):
        """Handle WebSocket client connections"""
        self.clients.add(websocket)
        client_addr = websocket.remote_address
        print(f"[WebSocket] Client connected: {client_addr}")

        try:
            # Send initial status
            await websocket.send(json.dumps({
                'protocol': 'GNSS_GPS_L1',
                'status': 'streaming',
                'sampleRate': 2048000,
                'centerFrequency': 1575420000,
                'timestamp': int(time.time() * 1000)
            }))

            # Keep connection alive and handle client messages
            async for message in websocket:
                # Echo back or handle commands if needed
                pass

        except websockets.exceptions.ConnectionClosed:
            print(f"[WebSocket] Client disconnected: {client_addr}")
        finally:
            self.clients.discard(websocket)

    async def stream_samples(self):
        """Continuously send samples to all connected clients (ZERO blocking)"""
        batch_size = 16384  # ~8ms of data at 2.048 MSPS

        while self.running:
            try:
                # Check if we have data and clients
                if self.sample_queue and self.clients:
                    # Gather samples from queue (non-blocking)
                    samples_to_send = []
                    while len(samples_to_send) < batch_size and self.sample_queue:
                        samples_to_send.append(self.sample_queue.popleft())

                    if samples_to_send:
                        # Concatenate all samples
                        combined_samples = np.concatenate(samples_to_send)

                        # Convert to bytes (complex64 = IQ interleaved)
                        sample_bytes = combined_samples.astype(np.complex64).tobytes()

                        # Send to all clients (non-blocking broadcast)
                        if self.clients:
                            await asyncio.gather(
                                *[client.send(sample_bytes) for client in self.clients],
                                return_exceptions=True
                            )
                            self.samples_sent += len(combined_samples)

                        # Status report every 2 seconds
                        if time.time() - self.last_report > 2.0:
                            queue_size = len(self.sample_queue)
                            print(f"[Stream] RX: {self.samples_received/1e6:.1f}M, "
                                  f"TX: {self.samples_sent/1e6:.1f}M, "
                                  f"Queue: {queue_size}/1000, "
                                  f"Clients: {len(self.clients)}")
                            self.last_report = time.time()
                            self.samples_received = 0
                            self.samples_sent = 0

                # Yield control (non-blocking sleep)
                await asyncio.sleep(0.001)  # 1ms sleep = max 1ms latency

            except Exception as e:
                print(f"[Stream] Error: {e}")
                await asyncio.sleep(0.1)

    async def run(self):
        """Main async run loop"""
        print("=" * 70)
        print("🛰️  SDRplay Direct API → WebSocket Streamer (ZERO Blocking)")
        print("=" * 70)
        print()
        print("Features:")
        print("  • Pure async/await (no blocking operations)")
        print("  • Direct WebSocket streaming (no FIFO, no files)")
        print("  • Ring buffer (auto-drops old data if clients slow)")
        print("  • Multi-client support")
        print()

        # Initialize SDRplay
        try:
            print("[SDRplay] Initializing device...")
            self.sdr = SDRplayDevice()
            print(f"[SDRplay] ✓ Ready: 2.048 MHz @ 1575.42 MHz (GPS L1)")
            print()
        except Exception as e:
            print(f"[SDRplay] ❌ Failed to initialize: {e}")
            return

        # Start WebSocket server
        print(f"[WebSocket] Starting server on port {self.websocket_port}...")
        server = await websockets.serve(
            self.websocket_handler,
            'localhost',
            self.websocket_port,
            ping_interval=None,  # Disable ping/pong
            max_size=None  # No message size limit
        )
        print(f"[WebSocket] ✓ Server listening on ws://localhost:{self.websocket_port}")
        print()

        # Start SDRplay streaming (runs in separate thread)
        print("[SDRplay] Starting streaming...")
        self.running = True
        self.sdr.start_streaming(self.data_callback)
        print("[SDRplay] ✓ Streaming active")
        print()

        print("=" * 70)
        print("🚀 STREAMING ACTIVE")
        print("=" * 70)
        print()
        print("Connect your client to: ws://localhost:8765")
        print("Press Ctrl+C to stop")
        print("-" * 70)
        print()

        # Start sample streaming task
        stream_task = asyncio.create_task(self.stream_samples())

        try:
            # Run forever
            await asyncio.Future()  # Run until cancelled
        except asyncio.CancelledError:
            print("\n[Main] Shutting down...")
        finally:
            self.running = False
            stream_task.cancel()

            # Stop SDRplay
            if self.sdr:
                try:
                    self.sdr.stop_streaming()
                    print("[SDRplay] ✓ Stopped")
                except:
                    pass

            # Close WebSocket server
            server.close()
            await server.wait_closed()
            print("[WebSocket] ✓ Server closed")
            print("\n👋 Goodbye!")

async def main():
    streamer = AsyncSDRplayWebSocketStreamer(websocket_port=8765)

    # Setup signal handlers for graceful shutdown
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, lambda: asyncio.create_task(shutdown()))

    async def shutdown():
        tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
        for task in tasks:
            task.cancel()

    await streamer.run()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n🛑 Interrupted by user")
        sys.exit(0)
