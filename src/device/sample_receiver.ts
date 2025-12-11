// Copyright 2024 Jacobo Tarrio Barreiro. All rights reserved.
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//     http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

import { Demodulator as AdsBDemodulator } from '../protocol/ads-b/demodulator.js'
import { Demodulator as IsmDemodulator } from '../protocol/ism/demodulator.ts'
import { Protocol, isGNSS } from '../protocol/protocol.ts'

/** Interface for classes that get samples from a Radio class. */
export interface SampleReceiver {
  /** Sets the sample rate. */
  setSampleRate(sampleRate: number): void;

  /** Receives samples that should be demodulated. */
  receiveSamples(frequency: number, data: ArrayBuffer): void;

  /** Sets a sample receiver to be executed right after this one. */
  andThen(next: SampleReceiver): SampleReceiver;
}

export function concatenateReceivers(
  prev: SampleReceiver,
  next: SampleReceiver
): SampleReceiver {
  let list = [];
  if (prev instanceof ReceiverSequence) {
    list.push(...prev.receivers);
  } else {
    list.push(prev);
  }
  if (next instanceof ReceiverSequence) {
    list.push(...next.receivers);
  } else {
    list.push(next);
  }
  return new ReceiverSequence(list);
}

class ReceiverSequence implements SampleReceiver {
  constructor(public receivers: SampleReceiver[]) {}

  setSampleRate(sampleRate: number): void {
    for (let receiver of this.receivers) {
      receiver.setSampleRate(sampleRate);
    }
  }

  receiveSamples(frequency: number, data: ArrayBuffer): void {
    for (let receiver of this.receivers) {
      receiver.receiveSamples(frequency, data);
    }
  }

  andThen(next: SampleReceiver): SampleReceiver {
    return concatenateReceivers(this, next);
  }
}

export class LoggingReceiver implements SampleReceiver {
  private adsBDemodulator: AdsBDemodulator;
  private ismDemodulator: IsmDemodulator;
  private protocol: Protocol;
  private onMsg;

  constructor(protocol: Protocol, onMsg) {
    this.protocol = protocol;
    this.onMsg = onMsg;
    this.adsBDemodulator = new AdsBDemodulator();
    this.ismDemodulator = new IsmDemodulator();
  }

  setSampleRate(sampleRate: number): void {
    console.log("setSampleRate", sampleRate);
  }

  receiveSamples(frequency: number, data: ArrayBuffer | any): void {
    // Check if data is a GNSS log message
    if (isGNSS(this.protocol) && data && typeof data === 'object' && data.type === 'gnss_log') {
      console.log(`[LoggingReceiver] Received GNSS log message: ${data.message}`);
      // Pass the log message directly to the callback
      this.onMsg({
        time: new Date(data.timestamp),
        msg: data,
        decoded: data.message
      });
      return;
    }

    // Check if data is already a GNSS result object (JSON from parse_gnss_logs)
    if (isGNSS(this.protocol) && data && typeof data === 'object' && 'satellites' in data && 'protocol' in data) {
      console.log(`[LoggingReceiver] Received pre-processed GNSS JSON data with ${data.satellites.length} satellites`);
      // Pass the JSON object directly to the callback
      this.onMsg({
        time: new Date(),
        msg: data,  // Pass the JSON object as-is
        decoded: `${data.satellites.length} sat(s) from GNSS-SDR`
      });
      return;
    }

    // Otherwise, treat as binary ArrayBuffer
    const samples = new Uint8Array(data);
    console.log("got samples", samples.length);

    if (this.protocol === Protocol.ADSB) {
      // ADS-B demodulation
      this.adsBDemodulator.process(samples, 256000, (msg) => {
        console.log(msg);
        const nonEmptyFields = {};
        Object.keys(msg).forEach(field => {
          if (msg[field] && field !== 'msg') {
            nonEmptyFields[field] = msg[field];
          }
        });
        this.onMsg({
          time: new Date(),
          msg: msg.msg,
          decoded: JSON.stringify(nonEmptyFields)
        });
      });
    } else if (isGNSS(this.protocol)) {
      // GNSS processing - pass raw buffer to callback
      // The actual GNSS demodulation happens in RtlDecoder.tsx
      console.log(`[LoggingReceiver] Passing ${samples.length} samples to GNSS callback`);
      this.onMsg({
        time: new Date(),
        msg: samples,
        decoded: 'GNSS'
      });
    } else {
      // ISM demodulation
      this.ismDemodulator.process(samples, 256000, (msg) => {
        this.onMsg(msg);
      });
    }
  }

  andThen(next: SampleReceiver): SampleReceiver {
    return concatenateReceivers(this, next);
  }
}
