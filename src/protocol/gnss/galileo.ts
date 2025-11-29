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

/**
 * Galileo E1 Signal Processing
 * Frequency: 1575.42 MHz (same as GPS L1)
 * Code Rate: 1.023 MHz
 * Code Length: 4092 chips (4x GPS)
 */

import { SatelliteInfo } from './gps.ts';

/**
 * Galileo E1 Code Generator
 */
export class GalileoE1CodeGenerator {
  /**
   * Generate E1-C pilot channel code for acquisition
   */
  static generate(svid: number): Int8Array {
    const codeLength = 4092;
    const code = new Int8Array(codeLength);

    // Generate primary code using memory codes
    const primaryCode = this.generatePrimaryCode(svid);

    // E1-C is 4092 chips long (25 * 4092 = 1ms)
    for (let i = 0; i < codeLength; i++) {
      code[i] = primaryCode[i % primaryCode.length];
    }

    return code;
  }

  /**
   * Generate primary code for Galileo E1
   */
  private static generatePrimaryCode(svid: number): Int8Array {
    const codeLength = 4092;
    const code = new Int8Array(codeLength);

    // Use simplified memory code generation
    // In reality, Galileo uses predefined memory codes
    let state = 0x1FF + svid; // 9-bit LFSR seeded with SVID

    for (let i = 0; i < codeLength; i++) {
      const output = state & 1;
      code[i] = output ? 1 : -1;

      // Feedback polynomial (simplified)
      const feedback = ((state >> 8) ^ (state >> 4)) & 1;
      state = ((state << 1) | feedback) & 0x1FF;
    }

    return code;
  }
}

/**
 * Galileo Signal Acquisition Engine
 */
export class GalileoAcquisition {
  private readonly sampleRate: number;
  private readonly dopplerRange: number;
  private readonly dopplerStep: number;
  private readonly threshold: number;

  constructor(
    sampleRate: number = 2.048e6,
    dopplerRange: number = 5000,
    dopplerStep: number = 500,
    threshold: number = 2.5
  ) {
    this.sampleRate = sampleRate;
    this.dopplerRange = dopplerRange;
    this.dopplerStep = dopplerStep;
    this.threshold = threshold;
  }

  /**
   * Search for Galileo satellites (SVID 1-50)
   */
  searchSatellites(samples: Float32Array, svidList: number[]): SatelliteInfo[] {
    const satellites: SatelliteInfo[] = [];

    for (const svid of svidList) {
      const result = this.acquireSatellite(samples, svid);
      if (result) {
        satellites.push(result);
      }
    }

    return satellites;
  }

  /**
   * Try to acquire a specific Galileo satellite
   */
  private acquireSatellite(samples: Float32Array, svid: number): SatelliteInfo | null {
    const e1Code = GalileoE1CodeGenerator.generate(svid);
    let maxCorr = 0;
    let bestDoppler = 0;
    let bestPhase = 0;

    // Search over Doppler frequencies
    for (let doppler = -this.dopplerRange; doppler <= this.dopplerRange; doppler += this.dopplerStep) {
      const result = this.correlate(samples, e1Code, doppler);

      if (result.correlation > maxCorr) {
        maxCorr = result.correlation;
        bestDoppler = doppler;
        bestPhase = result.codePhase;
      }
    }

    // Calculate SNR estimate
    const snr = maxCorr / (samples.length * 0.01); // Normalized

    if (snr >= this.threshold) {
      return {
        prn: svid, // Use SVID as PRN for consistency
        dopplerHz: bestDoppler,
        snr,
        codePhase: bestPhase
      };
    }

    return null;
  }

  /**
   * Correlate signal with E1 code at specific Doppler frequency
   */
  private correlate(samples: Float32Array, e1Code: Int8Array, doppler: number): { correlation: number, codePhase: number } {
    const codeLength = e1Code.length;
    const samplesPerChip = this.sampleRate / 1.023e6; // Same chip rate as GPS
    let maxCorr = 0;
    let bestPhase = 0;

    // Search over code phases (skip by 4 for speed)
    for (let phase = 0; phase < codeLength; phase += 4) {
      let correlation = 0;

      const samplesToCorrelate = Math.min(samples.length, Math.floor(codeLength * samplesPerChip));

      for (let i = 0; i < samplesToCorrelate; i++) {
        const chipIndex = Math.floor((i / samplesPerChip + phase) % codeLength);

        // Apply Doppler shift
        const dopplerPhase = 2 * Math.PI * doppler * i / this.sampleRate;
        const carrierI = Math.cos(dopplerPhase);
        const carrierQ = Math.sin(dopplerPhase);

        // Mix down and correlate
        const sampleI = samples[i] * carrierI;
        const sampleQ = samples[i] * carrierQ;

        correlation += Math.abs(sampleI * e1Code[chipIndex]) + Math.abs(sampleQ * e1Code[chipIndex]);
      }

      if (correlation > maxCorr) {
        maxCorr = correlation;
        bestPhase = phase;
      }
    }

    return { correlation: maxCorr, codePhase: bestPhase };
  }
}
