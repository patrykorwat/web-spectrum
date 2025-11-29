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
 * GNSS Jamming Detection and Analysis
 *
 * Detects and characterizes GNSS interference/jamming signals
 * Common jamming types:
 * - Broadband Noise Jamming (most common)
 * - Continuous Wave (CW) Jamming
 * - Swept CW Jamming
 * - Pulsed Jamming
 * - Meaconing (GPS spoofing)
 */

export interface JammingMetrics {
  // Signal strength metrics
  noisePowerDbm: number;          // Total noise power
  signalPowerDbm: number;         // Expected GNSS signal power
  jammingToSignalRatio: number;   // J/S ratio in dB

  // Jamming detection
  isJammed: boolean;              // Jamming detected
  jammingType: JammingType;       // Type of jamming
  jammerConfidence: number;       // 0-1 confidence level

  // Spectrum analysis
  peakFrequencyHz: number;        // Frequency of strongest interference
  bandwidthHz: number;            // Bandwidth of interference
  spectralDensity: Float32Array;  // Power spectral density

  // Statistical metrics
  kurtosis: number;               // Signal kurtosis (detects pulsed jamming)
  agcLevel: number;               // Automatic Gain Control level
  correlationLoss: number;        // Loss in correlation due to jamming

  timestamp: number;
}

export enum JammingType {
  NONE = 'NONE',
  BROADBAND_NOISE = 'BROADBAND_NOISE',
  CW_TONE = 'CW_TONE',
  SWEPT_CW = 'SWEPT_CW',
  PULSED = 'PULSED',
  SPOOFING = 'SPOOFING',
  UNKNOWN = 'UNKNOWN'
}

/**
 * GNSS Jamming Detector
 */
export class GNSSJammingDetector {
  private readonly sampleRate: number;
  private readonly fftSize: number = 2048;
  private readonly noiseThresholdDb: number = -110; // Typical GNSS noise floor

  // History for temporal analysis
  private powerHistory: number[] = [];
  private readonly historyLength: number = 100;

  constructor(sampleRate: number = 2.048e6) {
    this.sampleRate = sampleRate;
  }

  /**
   * Analyze samples for jamming
   */
  analyze(samples: Float32Array): JammingMetrics {
    // Calculate basic power metrics
    const noisePower = this.calculatePower(samples);
    const noisePowerDbm = 10 * Math.log10(noisePower * 1000); // Convert to dBm

    // Expected GNSS signal power at antenna (very weak!)
    const signalPowerDbm = -130; // Typical GPS C/A signal at antenna

    // Calculate J/S ratio
    const jammingToSignalRatio = noisePowerDbm - signalPowerDbm;

    // Perform FFT for spectrum analysis
    const spectrum = this.computeFFT(samples);
    const peakInfo = this.findPeakFrequency(spectrum);

    // Calculate statistical metrics
    const kurtosis = this.calculateKurtosis(samples);
    const agcLevel = this.estimateAGC(noisePower);

    // Detect jamming type
    const jammingType = this.detectJammingType(
      noisePowerDbm,
      spectrum,
      kurtosis,
      peakInfo
    );

    // Calculate confidence
    const jammerConfidence = this.calculateConfidence(
      jammingToSignalRatio,
      jammingType,
      kurtosis
    );

    // Update history
    this.powerHistory.push(noisePowerDbm);
    if (this.powerHistory.length > this.historyLength) {
      this.powerHistory.shift();
    }

    return {
      noisePowerDbm,
      signalPowerDbm,
      jammingToSignalRatio,
      isJammed: jammingToSignalRatio > 20, // J/S > 20 dB indicates jamming
      jammingType,
      jammerConfidence,
      peakFrequencyHz: peakInfo.frequency,
      bandwidthHz: peakInfo.bandwidth,
      spectralDensity: spectrum,
      kurtosis,
      agcLevel,
      correlationLoss: Math.min(jammingToSignalRatio / 10, 100),
      timestamp: Date.now()
    };
  }

  /**
   * Calculate total signal power
   */
  private calculatePower(samples: Float32Array): number {
    let sum = 0;
    for (let i = 0; i < samples.length; i++) {
      sum += samples[i] * samples[i];
    }
    return sum / samples.length;
  }

  /**
   * Compute FFT magnitude spectrum
   */
  private computeFFT(samples: Float32Array): Float32Array {
    const fftSize = Math.min(this.fftSize, samples.length);
    const spectrum = new Float32Array(fftSize / 2);

    // Simple DFT (in real implementation, use FFT library)
    for (let k = 0; k < fftSize / 2; k++) {
      let real = 0;
      let imag = 0;

      for (let n = 0; n < fftSize; n++) {
        const angle = -2 * Math.PI * k * n / fftSize;
        real += samples[n] * Math.cos(angle);
        imag += samples[n] * Math.sin(angle);
      }

      spectrum[k] = Math.sqrt(real * real + imag * imag) / fftSize;
    }

    return spectrum;
  }

  /**
   * Find peak frequency and bandwidth in spectrum
   */
  private findPeakFrequency(spectrum: Float32Array): { frequency: number, bandwidth: number } {
    let maxPower = 0;
    let maxIndex = 0;

    for (let i = 0; i < spectrum.length; i++) {
      if (spectrum[i] > maxPower) {
        maxPower = spectrum[i];
        maxIndex = i;
      }
    }

    const frequency = (maxIndex * this.sampleRate) / (spectrum.length * 2);

    // Estimate bandwidth at -3dB points
    const threshold = maxPower / Math.sqrt(2);
    let lowerIndex = maxIndex;
    let upperIndex = maxIndex;

    while (lowerIndex > 0 && spectrum[lowerIndex] > threshold) {
      lowerIndex--;
    }

    while (upperIndex < spectrum.length - 1 && spectrum[upperIndex] > threshold) {
      upperIndex++;
    }

    const bandwidth = ((upperIndex - lowerIndex) * this.sampleRate) / (spectrum.length * 2);

    return { frequency, bandwidth };
  }

  /**
   * Calculate kurtosis (detects pulsed jamming)
   * Kurtosis > 3 indicates non-Gaussian (pulsed) signals
   */
  private calculateKurtosis(samples: Float32Array): number {
    const mean = samples.reduce((a, b) => a + b, 0) / samples.length;

    let m2 = 0;
    let m4 = 0;

    for (let i = 0; i < samples.length; i++) {
      const diff = samples[i] - mean;
      const diff2 = diff * diff;
      m2 += diff2;
      m4 += diff2 * diff2;
    }

    m2 /= samples.length;
    m4 /= samples.length;

    return m4 / (m2 * m2);
  }

  /**
   * Estimate AGC level based on signal power
   */
  private estimateAGC(power: number): number {
    // AGC tries to maintain constant output power
    // Higher AGC = weaker input signal or jamming
    const nominalPower = 1e-13; // Expected GNSS power
    return 10 * Math.log10(power / nominalPower);
  }

  /**
   * Detect type of jamming
   */
  private detectJammingType(
    noisePowerDbm: number,
    spectrum: Float32Array,
    kurtosis: number,
    peakInfo: { frequency: number, bandwidth: number }
  ): JammingType {
    // Check if jammed at all
    if (noisePowerDbm < this.noiseThresholdDb + 10) {
      return JammingType.NONE;
    }

    // Pulsed jamming: high kurtosis
    if (kurtosis > 5) {
      return JammingType.PULSED;
    }

    // CW tone: narrow bandwidth, single peak
    if (peakInfo.bandwidth < 100e3) { // < 100 kHz
      // Check for swept CW (multiple strong tones over time)
      if (this.detectSweptCW()) {
        return JammingType.SWEPT_CW;
      }
      return JammingType.CW_TONE;
    }

    // Broadband noise: wide bandwidth, flat spectrum
    if (peakInfo.bandwidth > 1e6) { // > 1 MHz
      return JammingType.BROADBAND_NOISE;
    }

    return JammingType.UNKNOWN;
  }

  /**
   * Detect swept CW jamming (frequency changes over time)
   */
  private detectSweptCW(): boolean {
    // Need at least 10 samples in history
    if (this.powerHistory.length < 10) {
      return false;
    }

    // Look for periodic variations in power
    let variations = 0;
    for (let i = 1; i < this.powerHistory.length; i++) {
      if (Math.abs(this.powerHistory[i] - this.powerHistory[i - 1]) > 5) {
        variations++;
      }
    }

    return variations > this.powerHistory.length * 0.3;
  }

  /**
   * Calculate jamming confidence level
   */
  private calculateConfidence(
    jsRatio: number,
    jammingType: JammingType,
    kurtosis: number
  ): number {
    if (jammingType === JammingType.NONE) {
      return 0;
    }

    let confidence = 0;

    // J/S ratio contribution
    if (jsRatio > 20) confidence += 0.4;
    if (jsRatio > 30) confidence += 0.2;
    if (jsRatio > 40) confidence += 0.2;

    // Type-specific indicators
    if (jammingType === JammingType.PULSED && kurtosis > 5) {
      confidence += 0.2;
    } else if (jammingType !== JammingType.UNKNOWN) {
      confidence += 0.2;
    }

    return Math.min(confidence, 1.0);
  }

  /**
   * Get jamming severity description
   */
  static getJammingSeverity(jsRatio: number): string {
    if (jsRatio < 10) return 'None';
    if (jsRatio < 20) return 'Light';
    if (jsRatio < 30) return 'Moderate';
    if (jsRatio < 40) return 'Heavy';
    return 'Severe';
  }

  /**
   * Get jamming type description
   */
  static getJammingDescription(type: JammingType): string {
    switch (type) {
      case JammingType.NONE:
        return 'No jamming detected';
      case JammingType.BROADBAND_NOISE:
        return 'Broadband noise jamming - continuous wideband interference';
      case JammingType.CW_TONE:
        return 'CW tone jamming - single continuous wave interference';
      case JammingType.SWEPT_CW:
        return 'Swept CW jamming - frequency-hopping interference';
      case JammingType.PULSED:
        return 'Pulsed jamming - intermittent high-power interference';
      case JammingType.SPOOFING:
        return 'Possible spoofing - false GNSS signals detected';
      case JammingType.UNKNOWN:
        return 'Unknown interference pattern detected';
    }
  }
}
