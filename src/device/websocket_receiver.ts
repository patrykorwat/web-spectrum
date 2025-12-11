/*!
meshuga/web-spectrum
Copyright (C) 2024 Patryk Orwat

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
*/

import { SampleReceiver } from './sample_receiver';

/**
 * WebSocket Sample Receiver
 *
 * Receives IQ samples from a WebSocket server (e.g., SDRPlay bridge)
 * Compatible with RTL-SDR sample format (interleaved IQ uint8)
 */
export interface ProgressMessage {
  type: 'progress';
  phase: string;
  progress: number;
  elapsed: number;
  total: number;
  message: string;
  timestamp: number;
}

export class WebSocketReceiver {
  private ws: WebSocket | null = null;
  private receiver: SampleReceiver;
  private url: string;
  private connected: boolean = false;
  private reconnectTimer: number | null = null;
  private reconnectDelay: number = 2000; // 2 seconds
  private progressCallback: ((progress: ProgressMessage) => void) | null = null;

  // Statistics
  private bytesReceived: number = 0;
  private lastStatsTime: number = Date.now();
  private connectionTime: number = 0;

  constructor(url: string, receiver: SampleReceiver, progressCallback?: (progress: ProgressMessage) => void) {
    this.url = url;
    this.receiver = receiver;
    this.progressCallback = progressCallback || null;
  }

  /**
   * Connect to WebSocket server
   */
  connect(): Promise<void> {
    return new Promise((resolve, reject) => {
      console.log(`[WebSocket] Connecting to ${this.url}...`);

      try {
        this.ws = new WebSocket(this.url);
        this.ws.binaryType = 'arraybuffer';

        this.ws.onopen = () => {
          this.connected = true;
          this.connectionTime = Date.now();
          this.bytesReceived = 0;
          this.lastStatsTime = Date.now();
          console.log('[WebSocket] Connected successfully!');
          resolve();
        };

        this.ws.onmessage = (event) => {
          // Check if data is binary (IQ samples) or text (JSON)
          if (event.data instanceof ArrayBuffer) {
            this.handleData(event.data);
          } else if (typeof event.data === 'string') {
            this.handleJsonMessage(event.data);
          }
        };

        this.ws.onerror = (error) => {
          console.error('[WebSocket] Error:', error);
          if (!this.connected) {
            reject(new Error('Failed to connect to WebSocket server'));
          }
        };

        this.ws.onclose = () => {
          console.log('[WebSocket] Connection closed');
          this.connected = false;
          this.scheduleReconnect();
        };

      } catch (error) {
        console.error('[WebSocket] Connection error:', error);
        reject(error);
      }
    });
  }

  /**
   * Disconnect from WebSocket server
   */
  disconnect(): void {
    console.log('[WebSocket] Disconnecting...');

    // Cancel reconnection attempts
    if (this.reconnectTimer !== null) {
      window.clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }

    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }

    this.connected = false;
    console.log('[WebSocket] Disconnected');
  }

  /**
   * Handle incoming binary data
   */
  private handleData(data: ArrayBuffer): void {
    // Update statistics
    this.bytesReceived += data.byteLength;

    // Log throughput every second
    const now = Date.now();
    if (now - this.lastStatsTime >= 1000) {
      const mbps = (this.bytesReceived * 8) / 1e6;
      const uptime = ((now - this.connectionTime) / 1000).toFixed(0);
      console.log(`[WebSocket] Received: ${mbps.toFixed(2)} Mbps, Uptime: ${uptime}s`);
      this.bytesReceived = 0;
      this.lastStatsTime = now;
    }

    // Forward samples to receiver
    // Data is in RTL-SDR format: interleaved IQ uint8
    // Note: frequency parameter isn't used by GNSS receiver, pass 0
    this.receiver.receiveSamples(0, data);
  }

  /**
   * Handle incoming JSON message (GNSS data from parse_gnss_logs.py or progress updates)
   */
  private handleJsonMessage(jsonString: string): void {
    try {
      const message = JSON.parse(jsonString);

      // Log GNSS data or progress messages
      if (message.protocol === 'GNSS_GPS_L1' && message.satellites) {
        console.log(`[WebSocket] ✅ GNSS data received: ${message.satellites.length} satellites`, message);
        console.log('[WebSocket] Forwarding to receiver.receiveSamples()...');
        // Forward to receiver as a special JSON message type
        this.receiver.receiveSamples(0, message);
        console.log('[WebSocket] ✅ Forwarded to receiver');
      } else if (message.type === 'progress') {
        console.log(`[WebSocket] Progress: ${message.phase} - ${message.progress}% - ${message.message}`);
        // Forward progress to UI callback
        if (this.progressCallback) {
          this.progressCallback(message as ProgressMessage);
        }
      } else if (message.type === 'status') {
        console.log(`[WebSocket] Status: ${message.message} (collecting: ${message.collecting}, streaming: ${message.streaming})`);
        // Status messages are informational - they confirm the collection is active
        // The UI already polls the control API for status, so we can just log these
      } else if (message.type === 'gnss_log') {
        console.log(`[WebSocket] GNSS Log [${message.level}]: ${message.message}`);
        // Forward GNSS log messages to the receiver for display in decoded table
        this.receiver.receiveSamples(0, message);
      } else {
        console.log('[WebSocket] Received unknown message type:', message);
      }
    } catch (e) {
      console.error('[WebSocket] Failed to parse JSON message:', e);
    }
  }

  /**
   * Schedule reconnection attempt
   */
  private scheduleReconnect(): void {
    if (this.reconnectTimer !== null) {
      return; // Already scheduled
    }

    console.log(`[WebSocket] Reconnecting in ${this.reconnectDelay / 1000}s...`);

    this.reconnectTimer = window.setTimeout(() => {
      this.reconnectTimer = null;

      console.log('[WebSocket] Attempting to reconnect...');
      this.connect().catch((error) => {
        console.error('[WebSocket] Reconnection failed:', error);
        // Will auto-schedule another attempt via onclose
      });
    }, this.reconnectDelay);
  }

  /**
   * Check if connected
   */
  isConnected(): boolean {
    return this.connected && this.ws !== null && this.ws.readyState === WebSocket.OPEN;
  }

  /**
   * Get connection statistics
   */
  getStats(): { connected: boolean; uptime: number; url: string } {
    const uptime = this.connected ? (Date.now() - this.connectionTime) / 1000 : 0;
    return {
      connected: this.connected,
      uptime: Math.floor(uptime),
      url: this.url
    };
  }
}
