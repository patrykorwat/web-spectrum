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
 * BeiDou B1I Signal Processing
 * Frequency: 1561.098 MHz
 * Code Rate: 2.046 MHz
 * Code Length: 2046 chips
 */

import { SatelliteInfo } from './gps.ts';

/**
 * BeiDou B1I Code Generator
 */
export class BeiDouCodeGenerator {
  // G2 code phase assignments for each PRN
  private static readonly G2_PHASE_SELECTION: ReadonlyMap<number, number> = new Map([
    [1, 1], [2, 2], [3, 3], [4, 4], [5, 5], [6, 6], [7, 7], [8, 8], [9, 9], [10, 10],
    [11, 11], [12, 12], [13, 13], [14, 14], [15, 15], [16, 16], [17, 17], [18, 18], [19, 19], [20, 20],
    [21, 21], [22, 22], [23, 23], [24, 24], [25, 25], [26, 26], [27, 27], [28, 28], [29, 29], [30, 30],
    [31, 31], [32, 32], [33, 33], [34, 34], [35, 35], [36, 36], [37, 37], [38, 38], [39, 29], [40, 40],
    [41, 41], [42, 42], [43, 43], [44, 44], [45, 45], [46, 46], [47, 47], [48, 48], [49, 49], [50, 50],
    [51, 51], [52, 52], [53, 53], [54, 54], [55, 55], [56, 56], [57, 57], [58, 58], [59, 59], [60, 60],
    [61, 61], [62, 62], [63, 63]
  ]);

  /**
   * Generate B1I code for a specific PRN (1-63)
   */
  static generate(prn: number): Int8Array {
    const codeLength = 2046;
    const code = new Int8Array(codeLength);

    // G1 sequence: 11-stage LFSR
    let g1 = 0x7FF; // 11 bits all 1s

    // G2 sequence: 11-stage LFSR
    let g2 = 0x7FF;

    const phase = this.G2_PHASE_SELECTION.get(prn) || 0;

    for (let i = 0; i < codeLength; i++) {
      // Get output bits
      const g1Out = (g1 >> 10) & 1;

      // Apply phase shift to G2
      const g2Shifted = ((g2 >> (11 - (phase % 11))) | (g2 << (phase % 11))) & 0x7FF;
      const g2Out = (g2Shifted >> 10) & 1;

      // XOR outputs to get code chip
      code[i] = (g1Out ^ g2Out) ? 1 : -1;

      // Feedback: G1 polynomial = x^11 + x^9 + 1
      const g1Feedback = ((g1 >> 10) ^ (g1 >> 8)) & 1;
      g1 = ((g1 << 1) | g1Feedback) & 0x7FF;

      // Feedback: G2 polynomial = x^11 + x^10 + x^9 + x^8 + 1
      const g2Feedback = ((g2 >> 10) ^ (g2 >> 9) ^ (g2 >> 8) ^ (g2 >> 7)) & 1;
      g2 = ((g2 << 1) | g2Feedback) & 0x7FF;
    }

    return code;
  }
}

/**
 * Get BeiDou satellite type based on PRN
 */
export function getBeiDouSatelliteType(prn: number): 'GEO' | 'IGSO' | 'MEO' {
  if (prn >= 1 && prn <= 5) return 'GEO';   // Geostationary
  if (prn >= 6 && prn <= 10) return 'IGSO'; // Inclined Geosynchronous
  return 'MEO';                              // Medium Earth Orbit
}

/**
 * BeiDou Signal Acquisition Engine
 */
export class BeiDouAcquisition {
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
   * Search for BeiDou satellites (PRN 1-63)
   */
  searchSatellites(samples: Float32Array, prnList: number[]): SatelliteInfo[] {
    const satellites: SatelliteInfo[] = [];

    for (const prn of prnList) {
      const result = this.acquireSatellite(samples, prn);
      if (result) {
        satellites.push(result);
      }
    }

    return satellites;
  }

  /**
   * Try to acquire a specific BeiDou satellite
   */
  private acquireSatellite(samples: Float32Array, prn: number): SatelliteInfo | null {
    const b1iCode = BeiDouCodeGenerator.generate(prn);
    let maxCorr = 0;
    let bestDoppler = 0;
    let bestPhase = 0;

    // Search over Doppler frequencies
    for (let doppler = -this.dopplerRange; doppler <= this.dopplerRange; doppler += this.dopplerStep) {
      const result = this.correlate(samples, b1iCode, doppler);

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
        prn,
        dopplerHz: bestDoppler,
        snr,
        codePhase: bestPhase
      };
    }

    return null;
  }

  /**
   * Correlate signal with B1I code at specific Doppler frequency
   */
  private correlate(samples: Float32Array, b1iCode: Int8Array, doppler: number): { correlation: number, codePhase: number } {
    const codeLength = b1iCode.length;
    const samplesPerChip = this.sampleRate / 2.046e6; // BeiDou chip rate
    let maxCorr = 0;
    let bestPhase = 0;

    // Search over code phases (skip by 2 for speed)
    for (let phase = 0; phase < codeLength; phase += 2) {
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

        correlation += Math.abs(sampleI * b1iCode[chipIndex]) + Math.abs(sampleQ * b1iCode[chipIndex]);
      }

      if (correlation > maxCorr) {
        maxCorr = correlation;
        bestPhase = phase;
      }
    }

    return { correlation: maxCorr, codePhase: bestPhase };
  }
}
