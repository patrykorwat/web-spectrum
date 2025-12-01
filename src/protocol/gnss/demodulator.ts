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

import { Protocol } from '../protocol.ts';
import { GNSSAcquisition, SatelliteInfo } from './gps.ts';
import { GalileoAcquisition } from './galileo.ts';
import { GLONASSAcquisition } from './glonass.ts';
import { BeiDouAcquisition } from './beidou.ts';
import { GNSSJammingDetector, JammingMetrics } from './jamming.ts';
import { InterferenceMitigation } from './mitigation.ts';

export interface GNSSDemodulatorResult {
  protocol: Protocol;
  satellites: SatelliteInfo[];
  jamming: JammingMetrics;
  timestamp: number;
}

/**
 * Unified GNSS Demodulator for all constellations
 */
export class GNSSDemodulator {
  private protocol: Protocol = Protocol.GNSS_GPS_L1;
  private sampleBuffer: Float32Array;
  private bufferPosition: number = 0;
  private readonly bufferSize: number = 2048000; // 1000ms (1 second) at 2.048 MSPS for better sensitivity in jamming

  private gpsAcquisition: GNSSAcquisition;
  private galileoAcquisition: GalileoAcquisition;
  private glonassAcquisition: GLONASSAcquisition;
  private beidouAcquisition: BeiDouAcquisition;
  private jammingDetector: GNSSJammingDetector;
  private mitigation: InterferenceMitigation;

  // Throttling to prevent browser hang
  private lastProcessTime: number = 0;
  private readonly processIntervalMs: number = 15000; // Process every 15 seconds (needs time to fill 1-second buffer)

  constructor() {
    this.sampleBuffer = new Float32Array(this.bufferSize);

    // Initialize acquisition engines with VERY LOW threshold for weak signals in extreme jamming
    // Standard threshold is 2.5, we use 1.5 to be extremely sensitive (may have false positives)
    this.gpsAcquisition = new GNSSAcquisition(2.048e6, 5000, 250, 1.5); // Also narrower Doppler steps
    this.galileoAcquisition = new GalileoAcquisition(2.048e6, 5000, 250, 1.5);
    this.glonassAcquisition = new GLONASSAcquisition(2.048e6, 5000, 250, 1.5);
    this.beidouAcquisition = new BeiDouAcquisition(2.048e6, 5000, 250, 1.5);
    this.jammingDetector = new GNSSJammingDetector(2.048e6);
    this.mitigation = new InterferenceMitigation(2.048e6);
  }

  setProtocol(protocol: Protocol): void {
    this.protocol = protocol;
    this.bufferPosition = 0; // Reset buffer when protocol changes
  }

  /**
   * Process incoming RTL-SDR samples
   */
  processSamples(samples: ArrayBuffer): GNSSDemodulatorResult | null {
    const u8Samples = new Uint8Array(samples);

    // If buffer is already full, check if it's time to process before adding more samples
    if (this.bufferPosition >= this.sampleBuffer.length) {
      const now = Date.now();

      // Check if throttle interval has passed
      if (now - this.lastProcessTime >= this.processIntervalMs) {
        // Time to process! Continue to processing section below
      } else {
        // Still throttled - skip these samples and wait
        const timeRemaining = ((this.processIntervalMs - (now - this.lastProcessTime)) / 1000).toFixed(1);
        console.log(`[GNSS] Buffer full, waiting ${timeRemaining}s before processing...`);
        return null;
      }
    }

    // Debug: Log when we start filling buffer
    const positionBefore = this.bufferPosition;
    if (this.bufferPosition === 0) {
      console.log(`[GNSS] Starting to fill buffer, received ${u8Samples.length} samples, need ${this.bufferSize} total`);
    }

    // Convert RTL-SDR samples (uint8) to normalized float
    for (let i = 0; i < u8Samples.length && this.bufferPosition < this.sampleBuffer.length; i++) {
      // RTL-SDR samples are 0-255, convert to -1 to +1
      this.sampleBuffer[this.bufferPosition++] = (u8Samples[i] - 127.5) / 127.5;
    }

    const positionAfter = this.bufferPosition;
    console.log(`[GNSS] Buffer position: ${positionBefore} → ${positionAfter} (added ${positionAfter - positionBefore} samples)`);

    // Debug: Log buffer fill progress
    if (this.bufferPosition >= this.sampleBuffer.length) {
      console.log(`[GNSS] Buffer is now FULL: ${this.bufferPosition}/${this.bufferSize}`);
    } else {
      console.log(`[GNSS] Buffer filling: ${this.bufferPosition}/${this.bufferSize} (${(this.bufferPosition/this.bufferSize*100).toFixed(1)}%)`);
    }

    // When buffer is full, process it (throttle check already done at start of function)
    if (this.bufferPosition >= this.sampleBuffer.length) {
      this.lastProcessTime = Date.now();

      console.log(`[GNSS] Buffer full (${this.sampleBuffer.length} samples), analyzing...`);

      // Step 1: Search for satellites first (to get SNR for accurate J/S calculation)
      console.log(`[GNSS] Searching for ${this.getConstellationName()} satellites...`);
      let satellites = this.processBufferWithSamples(this.sampleBuffer);

      // Get best SNR from found satellites (if any)
      const bestSnr = satellites.length > 0
        ? Math.max(...satellites.map(s => s.snr))
        : undefined;

      if (satellites.length > 0) {
        console.log(
          `[GNSS] Found ${satellites.length} satellite(s)!`,
          satellites.map(s => `${this.getIdLabel()} ${s.prn}: SNR ${s.snr.toFixed(1)}dB, Doppler ${s.dopplerHz.toFixed(0)}Hz`)
        );
      }

      // Step 2: Analyze for jamming with actual signal SNR
      const jammingMetrics = this.jammingDetector.analyze(this.sampleBuffer, bestSnr);

      // Log jamming status
      if (jammingMetrics.isJammed) {
        console.warn(
          `[GNSS JAMMING] ⚠️ INTERFERENCE DETECTED!`,
          `Type: ${jammingMetrics.jammingType}`,
          `J/S Ratio: ${jammingMetrics.jammingToSignalRatio.toFixed(1)} dB`,
          `Severity: ${GNSSJammingDetector.getJammingSeverity(jammingMetrics.jammingToSignalRatio)}`,
          `Confidence: ${(jammingMetrics.jammerConfidence * 100).toFixed(0)}%`
        );
      } else {
        console.log(`[GNSS] No jamming detected. Noise floor: ${jammingMetrics.noiseFloorDb.toFixed(1)} dB (relative)`);
      }

      // Step 3: Apply interference mitigation if jammed, then re-search
      let processedSamples = this.sampleBuffer;
      if (jammingMetrics.isJammed) {
        processedSamples = this.mitigation.mitigateSamples(this.sampleBuffer, jammingMetrics);

        // Re-search after mitigation
        console.log(`[GNSS] Re-searching after mitigation...`);
        satellites = this.processBufferWithSamples(processedSamples);

        if (satellites.length > 0) {
          console.log(
            `[GNSS] After mitigation: Found ${satellites.length} satellite(s)!`,
            satellites.map(s => `${this.getIdLabel()} ${s.prn}: SNR ${s.snr.toFixed(1)}dB`)
          );
        }
      }

      // Final status
      if (satellites.length === 0) {
        if (jammingMetrics.isJammed) {
          console.log('[GNSS] No satellites acquired - JAMMING PREVENTING ACQUISITION');
        } else {
          console.log('[GNSS] No satellites acquired. Signal may be too weak (indoor location?)');
        }
      }

      this.bufferPosition = 0; // Reset for next batch

      // Always return result with jamming info
      return this.createResult(satellites, jammingMetrics, u8Samples);
    }

    return null;
  }

  /**
   * Process the sample buffer to search for satellites
   */
  private processBuffer(): SatelliteInfo[] {
    return this.processBufferWithSamples(this.sampleBuffer);
  }

  /**
   * Process custom samples (e.g., after mitigation) to search for satellites
   */
  private processBufferWithSamples(samples: Float32Array): SatelliteInfo[] {
    switch (this.protocol) {
      case Protocol.GNSS_GPS_L1:
        return this.gpsAcquisition.searchSatellites(
          samples,
          [1, 3, 6, 7, 8, 9, 11, 14, 17, 19, 22, 23, 28, 30, 31, 32] // Common visible PRNs
        );

      case Protocol.GNSS_GALILEO_E1:
        return this.galileoAcquisition.searchSatellites(
          samples,
          [1, 2, 3, 4, 5, 7, 8, 9, 11, 12, 19, 24, 25, 26, 27, 30] // Common Galileo SVIDs
        );

      case Protocol.GNSS_GLONASS_L1:
        return this.glonassAcquisition.searchSatellites(
          samples,
          [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12] // GLONASS slots
        );

      case Protocol.GNSS_BEIDOU_B1I:
        return this.beidouAcquisition.searchSatellites(
          samples,
          [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14] // BeiDou PRNs
        );

      default:
        return [];
    }
  }

  /**
   * Create result object from acquired satellites
   */
  private createResult(satellites: SatelliteInfo[], jamming: JammingMetrics, rawSamples: Uint8Array): GNSSDemodulatorResult {
    return {
      protocol: this.protocol,
      satellites,
      jamming,
      timestamp: Date.now()
    };
  }

  /**
   * Get constellation name for logging
   */
  private getConstellationName(): string {
    switch (this.protocol) {
      case Protocol.GNSS_GPS_L1: return 'GPS';
      case Protocol.GNSS_GALILEO_E1: return 'Galileo';
      case Protocol.GNSS_GLONASS_L1: return 'GLONASS';
      case Protocol.GNSS_BEIDOU_B1I: return 'BeiDou';
      default: return 'Unknown';
    }
  }

  /**
   * Get ID label for logging (PRN/SVID/Slot)
   */
  private getIdLabel(): string {
    switch (this.protocol) {
      case Protocol.GNSS_GPS_L1: return 'PRN';
      case Protocol.GNSS_GALILEO_E1: return 'SVID';
      case Protocol.GNSS_GLONASS_L1: return 'Slot';
      case Protocol.GNSS_BEIDOU_B1I: return 'PRN';
      default: return 'ID';
    }
  }
}
