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
 * GPS L1 C/A Signal Processing
 * Frequency: 1575.42 MHz
 * Code Rate: 1.023 MHz
 * Code Length: 1023 chips
 */

export interface SatelliteInfo {
  prn: number;
  dopplerHz: number;
  snr: number;
  codePhase: number;
}

/**
 * GPS C/A Code Generator
 * Generates Gold codes for GPS satellites (PRN 1-32)
 */
export class CACodeGenerator {
  // G2 tap selections for each PRN
  private static readonly G2_DELAY: ReadonlyMap<number, [number, number]> = new Map([
    [1, [2, 6]], [2, [3, 7]], [3, [4, 8]], [4, [5, 9]], [5, [1, 9]],
    [6, [2, 10]], [7, [1, 8]], [8, [2, 9]], [9, [3, 10]], [10, [2, 3]],
    [11, [3, 4]], [12, [5, 6]], [13, [6, 7]], [14, [7, 8]], [15, [8, 9]],
    [16, [9, 10]], [17, [1, 4]], [18, [2, 5]], [19, [3, 6]], [20, [4, 7]],
    [21, [5, 8]], [22, [6, 9]], [23, [1, 3]], [24, [4, 6]], [25, [5, 7]],
    [26, [6, 8]], [27, [7, 9]], [28, [8, 10]], [29, [1, 6]], [30, [2, 7]],
    [31, [3, 8]], [32, [4, 9]]
  ]);

  /**
   * Generate C/A code for a specific PRN
   */
  static generate(prn: number): Int8Array {
    const codeLength = 1023;
    const code = new Int8Array(codeLength);

    let g1 = 0x3ff; // 10 bits all 1s
    let g2 = 0x3ff;

    const taps = this.G2_DELAY.get(prn);
    if (!taps) {
      throw new Error(`Invalid PRN: ${prn}`);
    }
    const [tap1, tap2] = taps;

    for (let i = 0; i < codeLength; i++) {
      // Get output bits
      const g1Out = (g1 >> 9) & 1;
      const g2Out = ((g2 >> (10 - tap1)) ^ (g2 >> (10 - tap2))) & 1;

      // XOR outputs to get C/A code chip
      code[i] = (g1Out ^ g2Out) ? 1 : -1;

      // Feedback: G1 polynomial = x^10 + x^3 + 1
      const g1Feedback = ((g1 >> 9) ^ (g1 >> 2)) & 1;
      g1 = ((g1 << 1) | g1Feedback) & 0x3ff;

      // Feedback: G2 polynomial = x^10 + x^9 + x^8 + x^6 + x^3 + x^2 + 1
      const g2Feedback = ((g2 >> 9) ^ (g2 >> 8) ^ (g2 >> 7) ^ (g2 >> 5) ^ (g2 >> 2) ^ (g2 >> 1)) & 1;
      g2 = ((g2 << 1) | g2Feedback) & 0x3ff;
    }

    return code;
  }
}

/**
 * GPS Signal Acquisition Engine
 */
export class GNSSAcquisition {
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
   * Search for satellites in the signal
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
   * Try to acquire a specific satellite
   */
  private acquireSatellite(samples: Float32Array, prn: number): SatelliteInfo | null {
    const caCode = CACodeGenerator.generate(prn);
    let maxCorr = 0;
    let bestDoppler = 0;
    let bestPhase = 0;

    // Search over Doppler frequencies
    for (let doppler = -this.dopplerRange; doppler <= this.dopplerRange; doppler += this.dopplerStep) {
      const result = this.correlate(samples, caCode, doppler);

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
   * Correlate signal with C/A code at specific Doppler frequency
   */
  private correlate(samples: Float32Array, caCode: Int8Array, doppler: number): { correlation: number, codePhase: number } {
    const codeLength = caCode.length;
    const samplesPerChip = this.sampleRate / 1.023e6; // GPS C/A chip rate
    let maxCorr = 0;
    let bestPhase = 0;

    // Search over code phases
    for (let phase = 0; phase < codeLength; phase += 1) {
      let correlation = 0;

      // Correlate samples with code
      const samplesToCorrelate = Math.min(samples.length, Math.floor(codeLength * samplesPerChip));

      for (let i = 0; i < samplesToCorrelate; i++) {
        const chipIndex = Math.floor((i / samplesPerChip + phase) % codeLength);

        // Apply Doppler shift (simplified)
        const dopplerPhase = 2 * Math.PI * doppler * i / this.sampleRate;
        const carrierI = Math.cos(dopplerPhase);
        const carrierQ = Math.sin(dopplerPhase);

        // Mix down and correlate
        const sampleI = samples[i] * carrierI;
        const sampleQ = samples[i] * carrierQ;

        correlation += Math.abs(sampleI * caCode[chipIndex]) + Math.abs(sampleQ * caCode[chipIndex]);
      }

      if (correlation > maxCorr) {
        maxCorr = correlation;
        bestPhase = phase;
      }
    }

    return { correlation: maxCorr, codePhase: bestPhase };
  }
}
