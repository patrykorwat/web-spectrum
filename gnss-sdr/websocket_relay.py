#!/usr/bin/env python3
"""
Simple WebSocket relay server for GNSS messages
Receives messages from parse_gnss_logs.py and forwards to UI clients
"""

import asyncio
import websockets
import json
import sys

# Track connected clients
clients = set()

async def relay_handler(websocket):
    """Handle WebSocket connections - both from UI and message senders"""
    clients.add(websocket)
    client_id = id(websocket)
    print(f"[WebSocket Relay] Client connected (ID: {client_id}, Total: {len(clients)})")

    try:
        async for message in websocket:
            # Received a message - relay it to all OTHER clients
            print(f"[WebSocket Relay] Received message: {message[:100]}...")

            # Broadcast to all clients except sender
            if clients:
                await asyncio.gather(
                    *[client.send(message) for client in clients if client != websocket],
                    return_exceptions=True
                )
    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        clients.remove(websocket)
        print(f"[WebSocket Relay] Client disconnected (ID: {client_id}, Remaining: {len(clients)})")

async def main():
    print("=" * 70)
    print("WebSocket Relay Server for GNSS Messages")
    print("=" * 70)
    print("")
    print("Starting server on ws://localhost:8766")
    print("Waiting for connections from UI and message senders...")
    print("")

    async with websockets.serve(relay_handler, "localhost", 8766):
        await asyncio.Future()  # Run forever

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nShutting down relay server...")
