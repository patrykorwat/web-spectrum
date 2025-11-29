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

import { SampleReceiver } from './sample_receiver';

/**
 * Filtering configuration for RTL-SDR
 */
export interface FilterConfig {
  // Notch filter for CW tone jamming
  notchFilterEnabled: boolean;
  notchFrequencyHz: number;  // Center frequency to notch out
  notchBandwidthHz: number;  // Width of notch

  // AGC limiting
  agcLimitEnabled: boolean;
  agcTargetPower: number;    // Target normalized power (0.1 = -10dB)

  // Pulse blanking
  pulseBlankingEnabled: boolean;
  pulseThresholdMultiplier: number; // Blanking threshold (3.0 = 3x average)
}

/**
 * Sample receiver that applies DSP filtering before passing to demodulators
 * This helps mitigate interference at the hardware level
 */
export class FilteringSampleReceiver implements SampleReceiver {
  private nextReceiver: SampleReceiver;
  private config: FilterConfig;
  private sampleRate: number = 2048000;

  // Notch filter state
  private notchX1: number = 0;
  private notchX2: number = 0;
  private notchY1: number = 0;
  private notchY2: number = 0;

  constructor(nextReceiver: SampleReceiver, config: FilterConfig) {
    this.nextReceiver = nextReceiver;
    this.config = config;
  }

  setSampleRate(sampleRate: number): void {
    this.sampleRate = sampleRate;
    this.nextReceiver.setSampleRate(sampleRate);
  }

  receiveSamples(frequency: number, data: ArrayBuffer): void {
    let samples = new Uint8Array(data);

    // Apply filters if any are enabled
    if (this.config.notchFilterEnabled ||
        this.config.agcLimitEnabled ||
        this.config.pulseBlankingEnabled) {

      // Convert to float for processing
      const floatSamples = this.u8ToFloat(samples);

      // Apply filters in order
      let filtered = floatSamples;

      if (this.config.notchFilterEnabled) {
        filtered = this.applyNotchFilter(filtered);
      }

      if (this.config.pulseBlankingEnabled) {
        filtered = this.applyPulseBlanking(filtered);
      }

      if (this.config.agcLimitEnabled) {
        filtered = this.applyAgcLimit(filtered);
      }

      // Convert back to uint8
      samples = this.floatToU8(filtered);
    }

    // Pass filtered samples to next receiver
    this.nextReceiver.receiveSamples(frequency, samples.buffer);
  }

  andThen(next: SampleReceiver): SampleReceiver {
    // Not typically used in filter chains
    return this;
  }

  /**
   * Update filter configuration on the fly
   */
  updateConfig(config: Partial<FilterConfig>): void {
    this.config = { ...this.config, ...config };

    // Reset notch filter state when frequency changes
    if (config.notchFrequencyHz !== undefined) {
      this.notchX1 = 0;
      this.notchX2 = 0;
      this.notchY1 = 0;
      this.notchY2 = 0;
    }

    console.log('[FILTER] Configuration updated:', this.config);
  }

  /**
   * Apply notch filter to remove CW tone jamming
   */
  private applyNotchFilter(samples: Float32Array): Float32Array {
    const output = new Float32Array(samples.length);

    // Calculate normalized frequency
    const normalizedFreq = this.config.notchFrequencyHz / (this.sampleRate / 2);

    // Notch width parameter
    const r = 1 - (this.config.notchBandwidthHz / this.sampleRate);

    // Notch filter coefficients
    const theta = 2 * Math.PI * normalizedFreq;
    const cosTheta = Math.cos(theta);

    const b0 = 1;
    const b1 = -2 * cosTheta;
    const b2 = 1;
    const a1 = -2 * r * cosTheta;
    const a2 = r * r;

    // Apply IIR filter
    for (let i = 0; i < samples.length; i++) {
      const x0 = samples[i];
      const y0 = b0 * x0 + b1 * this.notchX1 + b2 * this.notchX2 -
                 a1 * this.notchY1 - a2 * this.notchY2;

      output[i] = y0;

      // Update history
      this.notchX2 = this.notchX1;
      this.notchX1 = x0;
      this.notchY2 = this.notchY1;
      this.notchY1 = y0;
    }

    return output;
  }

  /**
   * Apply pulse blanking to zero out strong pulses
   */
  private applyPulseBlanking(samples: Float32Array): Float32Array {
    const output = new Float32Array(samples);

    // Calculate average power
    let avgPower = 0;
    for (let i = 0; i < samples.length; i++) {
      avgPower += samples[i] * samples[i];
    }
    avgPower /= samples.length;

    const threshold = avgPower * this.config.pulseThresholdMultiplier;

    // Blank samples above threshold
    let blankedCount = 0;
    for (let i = 0; i < samples.length; i++) {
      const power = samples[i] * samples[i];
      if (power > threshold) {
        output[i] = 0;
        blankedCount++;
      }
    }

    if (blankedCount > 0) {
      console.log(`[FILTER] Pulse blanking: zeroed ${blankedCount}/${samples.length} samples`);
    }

    return output;
  }

  /**
   * Apply AGC limiting to prevent saturation
   */
  private applyAgcLimit(samples: Float32Array): Float32Array {
    // Calculate current power
    let currentPower = 0;
    for (let i = 0; i < samples.length; i++) {
      currentPower += samples[i] * samples[i];
    }
    currentPower /= samples.length;

    // If power exceeds target, reduce gain
    if (currentPower > this.config.agcTargetPower) {
      const output = new Float32Array(samples.length);
      const gain = Math.sqrt(this.config.agcTargetPower / currentPower);

      for (let i = 0; i < samples.length; i++) {
        output[i] = samples[i] * gain;
      }

      const reductionDb = 20 * Math.log10(gain);
      console.log(`[FILTER] AGC: reduced gain by ${reductionDb.toFixed(1)} dB`);

      return output;
    }

    return samples;
  }

  /**
   * Convert uint8 RTL-SDR samples to normalized float (-1 to +1)
   */
  private u8ToFloat(samples: Uint8Array): Float32Array {
    const output = new Float32Array(samples.length);
    for (let i = 0; i < samples.length; i++) {
      output[i] = (samples[i] - 127.5) / 127.5;
    }
    return output;
  }

  /**
   * Convert normalized float back to uint8 RTL-SDR samples
   */
  private floatToU8(samples: Float32Array): Uint8Array {
    const output = new Uint8Array(samples.length);
    for (let i = 0; i < samples.length; i++) {
      // Clamp to -1 to +1 range, then convert to 0-255
      const clamped = Math.max(-1, Math.min(1, samples[i]));
      output[i] = Math.round((clamped * 127.5) + 127.5);
    }
    return output;
  }
}
