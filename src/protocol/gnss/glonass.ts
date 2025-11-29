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
 * GLONASS L1OF Signal Processing
 * Frequency: 1602 MHz + channel_number * 562.5 kHz (FDMA)
 * Code Rate: 511 kHz
 * Code Length: 511 chips
 */

import { SatelliteInfo } from './gps.ts';

/**
 * GLONASS Code Generator
 * All GLONASS satellites use the same C/A code (differentiated by FDMA)
 */
export class GLONASSCodeGenerator {
  /**
   * Generate GLONASS C/A code (same for all satellites)
   */
  static generate(): Int8Array {
    const codeLength = 511;
    const code = new Int8Array(codeLength);

    // 9-stage LFSR with polynomial x^9 + x^5 + 1
    let state = 0x1FF; // All ones

    for (let i = 0; i < codeLength; i++) {
      const output = state & 1;
      code[i] = output ? 1 : -1;

      // Feedback
      const feedback = ((state >> 8) ^ (state >> 4)) & 1;
      state = ((state << 1) | feedback) & 0x1FF;
    }

    return code;
  }

  /**
   * Get GLONASS L1 frequency for a specific channel number
   * Channel numbers range from -7 to +6 (or +13 for newer satellites)
   */
  static getFrequency(channelNumber: number): number {
    const baseFreq = 1602e6; // 1602 MHz
    const channelSpacing = 562.5e3; // 562.5 kHz
    return baseFreq + channelNumber * channelSpacing;
  }
}

/**
 * GLONASS Signal Acquisition Engine
 */
export class GLONASSAcquisition {
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
   * Search for GLONASS satellites (Slots 1-24)
   * Note: GLONASS uses FDMA, so we search for the same code at different frequencies
   */
  searchSatellites(samples: Float32Array, slotList: number[]): SatelliteInfo[] {
    const satellites: SatelliteInfo[] = [];
    const glonassCode = GLONASSCodeGenerator.generate();

    for (const slot of slotList) {
      const result = this.acquireSatellite(samples, glonassCode, slot);
      if (result) {
        satellites.push(result);
      }
    }

    return satellites;
  }

  /**
   * Try to acquire a specific GLONASS satellite
   */
  private acquireSatellite(samples: Float32Array, code: Int8Array, slot: number): SatelliteInfo | null {
    let maxCorr = 0;
    let bestDoppler = 0;
    let bestPhase = 0;

    // Search over Doppler frequencies
    // For GLONASS, we need to account for the FDMA frequency offset
    const channelNumber = this.getChannelNumber(slot);
    const freqOffset = channelNumber * 562.5e3; // Frequency offset from 1602 MHz

    for (let doppler = -this.dopplerRange; doppler <= this.dopplerRange; doppler += this.dopplerStep) {
      const result = this.correlate(samples, code, doppler + freqOffset);

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
        prn: slot, // Use slot number as PRN
        dopplerHz: bestDoppler,
        snr,
        codePhase: bestPhase
      };
    }

    return null;
  }

  /**
   * Get GLONASS channel number for a slot
   * This is a simplified mapping - real GLONASS channel numbers vary
   */
  private getChannelNumber(slot: number): number {
    // Simplified: map slots 1-24 to channels -7 to +6
    return slot - 8;
  }

  /**
   * Correlate signal with GLONASS code at specific Doppler frequency
   */
  private correlate(samples: Float32Array, code: Int8Array, doppler: number): { correlation: number, codePhase: number } {
    const codeLength = code.length;
    const samplesPerChip = this.sampleRate / 511e3; // GLONASS chip rate
    let maxCorr = 0;
    let bestPhase = 0;

    // Search over code phases
    for (let phase = 0; phase < codeLength; phase += 1) {
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

        correlation += Math.abs(sampleI * code[chipIndex]) + Math.abs(sampleQ * code[chipIndex]);
      }

      if (correlation > maxCorr) {
        maxCorr = correlation;
        bestPhase = phase;
      }
    }

    return { correlation: maxCorr, codePhase: bestPhase };
  }
}
