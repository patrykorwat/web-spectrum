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

// Client for the GNSS demodulation Web Worker. Same call pattern as
// GNSSDemodulator, except processSamples() never blocks: it ships the IQ
// chunk to the worker and results come back asynchronously via onResult().
// Falls back to inline (blocking) processing if Worker creation fails.

import { Protocol } from '../protocol';
import { GNSSDemodulator, GNSSDemodulatorResult } from './demodulator';

export type GnssResultListener = (result: GNSSDemodulatorResult) => void;

export class GnssDemodulatorClient {
  private worker: Worker | null = null;
  private fallback: GNSSDemodulator | null = null;
  private listener: GnssResultListener | null = null;
  private lastProtocol: Protocol | null = null;

  constructor() {
    try {
      this.worker = new Worker(new URL('./gnssWorker.ts', import.meta.url));
      this.worker.onmessage = (e: MessageEvent) => {
        const data = e.data as { type: string; result?: GNSSDemodulatorResult };
        if (data && data.type === 'result' && data.result && this.listener) {
          this.listener(data.result);
        }
      };
      this.worker.onerror = (e) => {
        console.error('[GNSS worker] error, falling back to inline processing:', e.message);
        this.useFallback();
      };
    } catch (err) {
      console.warn('[GNSS worker] unavailable, using inline processing:', err);
      this.useFallback();
    }
  }

  private useFallback() {
    if (this.fallback) return;
    if (this.worker) {
      this.worker.terminate();
      this.worker = null;
    }
    this.fallback = new GNSSDemodulator();
    if (this.lastProtocol !== null) {
      this.fallback.setProtocol(this.lastProtocol);
    }
  }

  /** Register the (single) result listener; replaces any previous one. */
  onResult(listener: GnssResultListener) {
    this.listener = listener;
  }

  setProtocol(protocol: Protocol) {
    this.lastProtocol = protocol;
    if (this.worker) this.worker.postMessage({ type: 'setProtocol', protocol });
    else if (this.fallback) this.fallback.setProtocol(protocol);
  }

  /** Feed an IQ chunk (interleaved float32 IQ in an ArrayBuffer).
   *  Returns a result only in inline-fallback mode; null when the worker owns it. */
  processSamples(buffer: ArrayBuffer): GNSSDemodulatorResult | null {
    if (this.worker) {
      this.worker.postMessage({ type: 'samples', buffer });
      return null;
    }
    else if (this.fallback) {
      const result = this.fallback.processSamples(buffer);
      if (result && this.listener) this.listener(result);
    }
    return null;
  }

  terminate() {
    if (this.worker) {
      this.worker.terminate();
      this.worker = null;
    }
    this.fallback = null;
    this.listener = null;
  }
}
