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

import { FFT } from '../../dsp/fft';

export interface JammingMetrics {
  // Signal strength metrics (relative dB, not calibrated dBm)
  noiseFloorDb: number;           // Noise floor power in dB (relative)
  totalPowerDb: number;           // Total received power in dB (relative)
  signalPowerDb: number;          // GNSS signal power in dB (relative, from correlation)
  jammingToSignalRatio: number;   // J/S ratio in dB

  // Jamming detection
  isJammed: boolean;              // Jamming detected
  jammingType: JammingType;       // Type of jamming
  jammerConfidence: number;       // 0-1 confidence level

  // Spectrum analysis
  peakFrequencyHz: number;        // Frequency of strongest interference
  bandwidthHz: number;            // Bandwidth of interference
  spectralDensity: Float32Array;  // Power spectral density

  // Pulse analysis (envelope autocorrelation)
  pulseRateHz: number;            // Estimated pulse repetition rate (0 = none)
  pulseDutyCycle: number;         // Fraction of time the envelope is "on"
  pulseAcfPeak: number;           // Autocorrelation peak at the detected period

  // Statistical metrics
  kurtosis: number;               // Signal kurtosis (detects pulsed jamming)
  agcLevel: number;               // "AGC-like" level: total power above noise floor (dB)
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
  private readonly fft: FFT;
  private readonly hann: Float32Array;

  // History for temporal analysis
  private powerHistory: number[] = [];
  private readonly historyLength: number = 100;

  constructor(sampleRate: number = 2.048e6) {
    this.sampleRate = sampleRate;
    this.fft = FFT.ofLength(this.fftSize);
    this.hann = new Float32Array(this.fftSize);
    for (let i = 0; i < this.fftSize; i++) {
      this.hann[i] = 0.5 * (1 - Math.cos((2 * Math.PI * i) / (this.fftSize - 1)));
    }
    this.fft.setWindow(this.hann);
  }

  /**
   * Analyze samples for jamming
   * signalSnr: Optional SNR from satellite correlation (if satellites were found)
   */
  analyze(samples: Float32Array, signalSnr?: number): JammingMetrics {
    // Calculate total received power (in relative dB scale)
    const totalPower = this.calculatePower(samples);
    const totalPowerDb = 10 * Math.log10(totalPower);

    // Calculate noise floor (median segment power: robust against jamming peaks)
    const noiseFloor = this.estimateNoiseFloor(samples);
    const noiseFloorDb = 10 * Math.log10(noiseFloor);

    // If we have actual satellite SNR, use it to calculate signal power
    // Otherwise, assume typical GPS signal is buried ~20dB below noise
    let signalPowerDb: number;
    let jammingToSignalRatio: number;

    if (signalSnr !== undefined && signalSnr > 0) {
      // We found satellites! Calculate signal power from SNR
      // SNR is the ratio: Signal Power / Noise Floor
      signalPowerDb = noiseFloorDb + 10 * Math.log10(signalSnr);

      // J/S = Jamming Power / Signal Power
      // Jamming Power ≈ Total Power - Signal Power (in linear domain)
      const totalPowerLinear = totalPower;
      const signalPowerLinear = noiseFloor * signalSnr;
      const jammingPowerLinear = Math.max(totalPowerLinear - signalPowerLinear, noiseFloor);
      jammingToSignalRatio = 10 * Math.log10(jammingPowerLinear / signalPowerLinear);
    } else {
      // No satellites found - cannot calculate accurate J/S ratio
      // GPS C/A signal is typically 20-25 dB below noise floor
      signalPowerDb = noiseFloorDb - 23; // Typical GPS C/A at receiver

      // Check if total power is significantly elevated above noise floor
      // This indicates possible jamming/interference
      // For normal conditions: totalPower ≈ noiseFloor (within ~3-6 dB)
      // Only flag as jamming if power is significantly elevated (>10 dB above noise floor)
      const powerElevationDb = totalPowerDb - noiseFloorDb;

      if (powerElevationDb > 10) {
        // Elevated power - calculate J/S assuming signal at typical GPS level
        jammingToSignalRatio = totalPowerDb - signalPowerDb;
      } else {
        // Normal noise floor - no jamming
        jammingToSignalRatio = 0;
      }
    }

    // Perform FFT for spectrum analysis (real radix-2 FFT on deinterleaved IQ)
    const spectrum = this.computeFFT(samples);
    const peakInfo = this.findPeakFrequency(spectrum);

    // Calculate statistical metrics
    const kurtosis = this.calculateKurtosis(samples);
    const agcLevel = totalPowerDb - noiseFloorDb; // How much above noise floor

    // Pulse-rate estimation via envelope autocorrelation
    const pulse = this.estimatePulseRate(samples);

    // Detect jamming type
    const jammingType = this.detectJammingType(
      totalPowerDb,
      spectrum,
      kurtosis,
      peakInfo,
      pulse.rate
    );

    // Calculate confidence
    const jammerConfidence = this.calculateConfidence(
      jammingToSignalRatio,
      jammingType,
      kurtosis,
      pulse.acfPeak
    );

    // Update history
    this.powerHistory.push(totalPowerDb);
    if (this.powerHistory.length > this.historyLength) {
      this.powerHistory.shift();
    }

    return {
      noiseFloorDb,
      totalPowerDb,
      signalPowerDb,
      jammingToSignalRatio,
      isJammed: jammingToSignalRatio > 20 || pulse.detected, // J/S > 20 dB or periodic pulsing
      jammingType,
      jammerConfidence,
      peakFrequencyHz: peakInfo.frequency,
      bandwidthHz: peakInfo.bandwidth,
      spectralDensity: spectrum,
      pulseRateHz: pulse.rate,
      pulseDutyCycle: pulse.dutyCycle,
      pulseAcfPeak: pulse.acfPeak,
      kurtosis,
      agcLevel,
      correlationLoss: Math.min(jammingToSignalRatio / 10, 100),
      timestamp: Date.now()
    };
  }

  /**
   * Estimate noise floor from segment powers
   * Uses the median of 2048-sample RMS powers, which is robust against
   * strong transient peaks (jamming pulses, saturating bursts).
   */
  private estimateNoiseFloor(samples: Float32Array): number {
    const seg = 2048;
    const nSeg = Math.floor(samples.length / seg);
    if (nSeg === 0) return 1e-10;
    // Cap the number of analyzed segments to keep the cost bounded
    const step = Math.max(1, Math.floor(nSeg / 512));
    const powers: number[] = [];
    for (let s = 0; s < nSeg; s += step) {
      let sum = 0;
      const base = s * seg;
      for (let i = base; i < base + seg; i++) {
        sum += samples[i] * samples[i];
      }
      powers.push(sum / seg);
    }
    powers.sort((a, b) => a - b);
    return powers[Math.floor(powers.length / 2)] || 1e-10;
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
   * Compute magnitude spectrum using the shared radix-2 FFT.
   * The input buffer holds interleaved I/Q samples; they are deinterleaved
   * into a complex vector so the spectrum covers ±fs/2 correctly.
   */
  private computeFFT(samples: Float32Array): Float32Array {
    const n = Math.min(this.fftSize, Math.floor(samples.length / 2));
    const real = new Float32Array(this.fftSize);
    const imag = new Float32Array(this.fftSize);
    for (let i = 0; i < n; i++) {
      real[i] = samples[2 * i];
      imag[i] = samples[2 * i + 1];
    }
    const out = this.fft.transform(real, imag);
    const spectrum = new Float32Array(this.fftSize / 2);
    for (let k = 0; k < this.fftSize / 2; k++) {
      spectrum[k] = Math.sqrt(out.real[k] * out.real[k] + out.imag[k] * out.imag[k]);
    }
    return spectrum;
  }

  /**
   * Find peak frequency and bandwidth in spectrum
   */
  private findPeakFrequency(spectrum: Float32Array): { frequency: number, bandwidth: number } {
    let maxPower = 0;
    let maxIndex = 0;

    // Skip DC bin (index 0) and nearby bins to avoid DC offset
    for (let i = 5; i < spectrum.length; i++) {
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
   * Estimate pulse repetition rate from the power envelope.
   *
   * The envelope (200 us boxcar average of instantaneous power) of a pulsed
   * jammer is an on/off waveform; its autocorrelation shows a strong peak at
   * the pulse period. Random noise does not. Bounded to the first ~0.5 s of
   * the buffer so the cost stays low; periodicity down to 20 Hz is detectable.
   */
  private estimatePulseRate(samples: Float32Array): { detected: boolean, rate: number, dutyCycle: number, acfPeak: number } {
    const noDetection = { detected: false, rate: 0, dutyCycle: 0, acfPeak: 0 };
    const maxSamples = Math.min(samples.length, 1048576); // ~0.5 s at 2.048 MSPS
    const win = Math.max(1, Math.round(0.0002 * this.sampleRate)); // 200 us boxcar
    const nWin = Math.floor(maxSamples / win);
    if (nWin < 200) return noDetection;
    const envRate = this.sampleRate / win;

    // Envelope in dB
    const env = new Float32Array(nWin);
    for (let w = 0; w < nWin; w++) {
      let sum = 0;
      const base = w * win;
      for (let i = base; i < base + win; i++) {
        sum += samples[i] * samples[i];
      }
      env[w] = 10 * Math.log10(sum / win + 1e-12);
    }

    // Median envelope level
    const sorted = Array.from(env).sort((a, b) => a - b);
    const median = sorted[Math.floor(nWin / 2)];

    // On/off waveform: 6 dB above the median envelope level
    const thresh = median + 6;
    let onCount = 0;
    for (let i = 0; i < nWin; i++) {
      if (env[i] > thresh) onCount++;
    }
    const dutyCycle = onCount / nWin;
    if (dutyCycle <= 0.02 || dutyCycle >= 0.98) {
      return { detected: false, rate: 0, dutyCycle, acfPeak: 0 };
    }

    // Autocorrelation of the on/off waveform via FFT (O(n log n))
    const pad = FFT.ofLength(2 * nWin);
    const re = new Float32Array(pad.length);
    const im = new Float32Array(pad.length);
    for (let i = 0; i < nWin; i++) {
      re[i] = (env[i] > thresh ? 1 : 0) - dutyCycle; // zero-mean
    }
    const fwd = pad.transform(re, im);
    // Power spectrum (real and even for real input) -> inverse transform is the ACF
    const pre = new Float32Array(pad.length);
    const pim = new Float32Array(pad.length);
    for (let k = 0; k < pad.length; k++) {
      pre[k] = fwd.real[k] * fwd.real[k] + fwd.imag[k] * fwd.imag[k];
    }
    const inv = pad.reverse(pre, pim);

    // Search pulse periods: skip the first 1 ms, search down to 20 Hz
    const minLag = Math.max(2, Math.round(0.001 * envRate));
    const maxLag = Math.min(nWin - 1, Math.round(envRate / 20));
    if (maxLag <= minLag) return noDetection;
    const ref = inv.real[0] + 1e-12;
    let bestLag = minLag;
    let bestVal = -Infinity;
    for (let l = minLag; l <= maxLag; l++) {
      const v = inv.real[l] / ref;
      if (v > bestVal) {
        bestVal = v;
        bestLag = l;
      }
    }
    // ACF peaks repeat at every multiple of the true period; take the FIRST
    // lag within 10% of the best peak so the fundamental period wins over
    // 2T/3T harmonics (argmax alone can pick 2T).
    let acfLag = bestLag;
    for (let l = minLag; l <= bestLag; l++) {
      if (inv.real[l] / ref >= bestVal * 0.9) {
        acfLag = l;
        break;
      }
    }
    const acfPeak = inv.real[acfLag] / ref;
    if (acfPeak > 0.5) {
      return { detected: true, rate: envRate / acfLag, dutyCycle, acfPeak };
    }
    return { detected: false, rate: 0, dutyCycle, acfPeak };
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
   * Detect type of jamming
   */
  private detectJammingType(
    totalPowerDb: number,
    spectrum: Float32Array,
    kurtosis: number,
    peakInfo: { frequency: number, bandwidth: number },
    pulseRate: number
  ): JammingType {
    // totalPowerDb is relative (not calibrated), so we can't use absolute thresholds
    // This check is performed in the analyze() method using power elevation
    // If we're here, assume some interference is present

    // Periodic pulsing confirmed by envelope autocorrelation
    if (pulseRate > 0) {
      return JammingType.PULSED;
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
    kurtosis: number,
    acfPeak: number
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
    if (jammingType === JammingType.PULSED && (kurtosis > 5 || acfPeak > 0.5)) {
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
