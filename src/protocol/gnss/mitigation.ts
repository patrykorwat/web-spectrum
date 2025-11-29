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

import { JammingType, JammingMetrics } from './jamming.ts';

/**
 * GNSS Interference Mitigation
 * Implements techniques to extract GNSS signals from jamming environment
 */
export class InterferenceMitigation {
  private sampleRate: number;
  private notchFilters: NotchFilter[] = [];

  constructor(sampleRate: number = 2.048e6) {
    this.sampleRate = sampleRate;
  }

  /**
   * Apply interference mitigation based on detected jamming type
   */
  mitigateSamples(samples: Float32Array, jamming: JammingMetrics): Float32Array {
    let mitigated = new Float32Array(samples);

    console.log(`[MITIGATION] Applying mitigation for ${jamming.jammingType}`);

    // 1. Pulse blanking for pulsed jamming
    if (jamming.jammingType === JammingType.PULSED) {
      mitigated = this.pulseBlanking(mitigated);
    }

    // 2. Notch filter for CW tones (your main problem!)
    if (jamming.jammingType === JammingType.CW_TONE ||
        jamming.jammingType === JammingType.SWEPT_CW) {
      mitigated = this.notchFilterCW(mitigated, jamming.peakFrequencyHz);
    }

    // 3. AGC limiting to prevent saturation
    if (jamming.isJammed && jamming.jammingToSignalRatio > 40) {
      mitigated = this.agcLimit(mitigated);
    }

    // 4. Spectral subtraction for broadband noise
    if (jamming.jammingType === JammingType.BROADBAND_NOISE) {
      mitigated = this.spectralSubtraction(mitigated, jamming.noisePowerDbm);
    }

    const power = this.calculatePower(mitigated);
    const powerDbm = 10 * Math.log10(power * 1000);
    console.log(`[MITIGATION] Original power: ${jamming.noisePowerDbm.toFixed(1)} dBm, After mitigation: ${powerDbm.toFixed(1)} dBm, Reduction: ${(jamming.noisePowerDbm - powerDbm).toFixed(1)} dB`);

    return mitigated;
  }

  /**
   * Notch filter to remove CW tone jamming
   * This is critical for Kaliningrad CW tone jamming
   */
  private notchFilterCW(samples: Float32Array, peakFreqHz: number): Float32Array {
    const output = new Float32Array(samples.length);

    // Calculate normalized frequency (0 to 1, where 1 = Nyquist)
    const normalizedFreq = peakFreqHz / (this.sampleRate / 2);

    // Notch filter parameters
    const notchWidth = 0.01; // Narrow notch (1% of sample rate)
    const r = 1 - notchWidth; // Pole radius (closer to 1 = sharper notch)

    // Notch filter coefficients (2nd order IIR)
    const theta = 2 * Math.PI * normalizedFreq;
    const cosTheta = Math.cos(theta);

    // Numerator coefficients (zeros on unit circle)
    const b0 = 1;
    const b1 = -2 * cosTheta;
    const b2 = 1;

    // Denominator coefficients (poles inside unit circle)
    const a1 = -2 * r * cosTheta;
    const a2 = r * r;

    // Apply IIR filter
    let x1 = 0, x2 = 0; // Input history
    let y1 = 0, y2 = 0; // Output history

    for (let i = 0; i < samples.length; i++) {
      const x0 = samples[i];
      const y0 = b0 * x0 + b1 * x1 + b2 * x2 - a1 * y1 - a2 * y2;

      output[i] = y0;

      // Update history
      x2 = x1;
      x1 = x0;
      y2 = y1;
      y1 = y0;
    }

    console.log(`[MITIGATION] Applied notch filter at ${peakFreqHz.toFixed(0)} Hz`);
    return output;
  }

  /**
   * Pulse blanking - zero out samples during pulse jamming
   */
  private pulseBlanking(samples: Float32Array): Float32Array {
    const output = new Float32Array(samples);
    const threshold = this.calculatePower(samples) * 3; // 3x average power

    let blankedSamples = 0;

    for (let i = 0; i < samples.length; i++) {
      const power = samples[i] * samples[i];
      if (power > threshold) {
        output[i] = 0; // Blank the sample
        blankedSamples++;
      }
    }

    console.log(`[MITIGATION] Pulse blanking: zeroed ${blankedSamples}/${samples.length} samples (${(blankedSamples/samples.length*100).toFixed(1)}%)`);
    return output;
  }

  /**
   * AGC limiting to prevent receiver saturation
   */
  private agcLimit(samples: Float32Array): Float32Array {
    const output = new Float32Array(samples.length);
    const targetPower = 0.1; // Target normalized power
    const currentPower = this.calculatePower(samples);

    if (currentPower > targetPower) {
      const gain = Math.sqrt(targetPower / currentPower);
      for (let i = 0; i < samples.length; i++) {
        output[i] = samples[i] * gain;
      }
      console.log(`[MITIGATION] AGC: reduced gain by ${(20 * Math.log10(gain)).toFixed(1)} dB`);
    } else {
      return samples;
    }

    return output;
  }

  /**
   * Spectral subtraction for broadband noise
   */
  private spectralSubtraction(samples: Float32Array, noiseFloorDbm: number): Float32Array {
    // Simple time-domain implementation
    // In production, this would use FFT-based spectral subtraction
    const output = new Float32Array(samples.length);
    const noiseEstimate = Math.pow(10, noiseFloorDbm / 10) / 1000;

    for (let i = 0; i < samples.length; i++) {
      const power = samples[i] * samples[i];
      if (power > noiseEstimate) {
        output[i] = samples[i] * Math.sqrt((power - noiseEstimate) / power);
      } else {
        output[i] = 0;
      }
    }

    return output;
  }

  /**
   * Calculate signal power
   */
  private calculatePower(samples: Float32Array): number {
    let sum = 0;
    for (let i = 0; i < samples.length; i++) {
      sum += samples[i] * samples[i];
    }
    return sum / samples.length;
  }
}

/**
 * Notch filter implementation
 */
class NotchFilter {
  private centerFreq: number;
  private bandwidth: number;

  constructor(centerFreq: number, bandwidth: number) {
    this.centerFreq = centerFreq;
    this.bandwidth = bandwidth;
  }
}
