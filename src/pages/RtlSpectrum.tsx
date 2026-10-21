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

// Live spectrum analyzer + waterfall for the RTL-SDR dongle (WebUSB),
// in the style of jtarrio/radioreceiver (issue #9): real-time FFT with
// averaging, peak hold, dB/grid scale and a scrolling heatmap waterfall.

import React, { useRef, useState, useEffect } from 'react';

import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import ButtonGroup from '@mui/material/ButtonGroup';
import MenuItem from '@mui/material/MenuItem';
import Select from '@mui/material/Select';
import Typography from '@mui/material/Typography';

import { FormControl } from '@mui/base/FormControl';

import Label from '../components/Label';
import NumberInput from '../components/NumberInput';
import Stack from '@mui/system/Stack';

import { RTL2832U_Provider } from "../device/rtlsdr/rtl2832u";
import { Radio } from '../device/radio';
import { SampleReceiver, concatenateReceivers } from '../device/sample_receiver';
import { FFT } from '../dsp/fft';
import { heatmap } from '../components/spectrumColors';
import { downloadFile } from '../utils/io';

const NFFT = 2048;

/** Receiver that forwards raw interleaved IQ chunks to the analyzer. */
class SpectrumTap implements SampleReceiver {
  constructor(private onSamples: (data: Float32Array) => void) {}
  setSampleRate(_sampleRate: number): void { /* not needed here */ }
  receiveSamples(_frequency: number, data: ArrayBuffer): void {
    this.onSamples(new Float32Array(data));
  }
  andThen(next: SampleReceiver): SampleReceiver { return concatenateReceivers(this, next); }
}

const SPEC_W = 1000, SPEC_H = 280;
const WF_W = 1000, WF_H = 240;
const RANGE_DB = 70;            // vertical span of the display
const AVG_ALPHA = 0.25;         // exponential averaging weight
const PEAK_DECAY = 0.9995;      // slow peak-hold decay per update

function RtlSpectrum() {
  const [radio, setRadio] = useState<Radio>();
  const [frequency, setFrequency] = useState<number>(1575.42);
  const [frequencyMag, setFrequencyMag] = useState<number>(1000000);
  const [gain, setGain] = useState<number | null>(40);
  const [sampleRate, setSampleRate] = useState<number>(2048000);
  const [biasTEnabled, setBiasTEnabled] = useState<boolean>(false);
  const [refDb, setRefDb] = useState<number>(-20);   // level shown at the top of the display
  const [running, setRunning] = useState<boolean>(false);
  const [fps, setFps] = useState<number>(0);

  const specCanvas = useRef<HTMLCanvasElement>(null);
  const wfCanvas = useRef<HTMLCanvasElement>(null);

  // DSP + rendering state lives in refs (mutated at sample rate, no re-renders)
  const fft = useRef<FFT>(FFT.ofLength(NFFT));
  const windowReady = useRef<boolean>(false);
  const avg = useRef<Float32Array>(new Float32Array(NFFT));
  const peak = useRef<Float32Array>(new Float32Array(NFFT));
  const haveData = useRef<boolean>(false);
  const carry = useRef<Float32Array>(new Float32Array(0));
  const reBuf = useRef<Float32Array>(new Float32Array(NFFT));
  const imBuf = useRef<Float32Array>(new Float32Array(NFFT));
  const lastSpecDraw = useRef<number>(0);
  const lastWfDraw = useRef<number>(0);
  const frames = useRef<number>(0);
  const freqRef = useRef<number>(1575.42e6);
  const spanRef = useRef<number>(2048000);
  const refDbRef = useRef<number>(-20);

  useEffect(() => {
    freqRef.current = frequency * frequencyMag;
  }, [frequency, frequencyMag]);
  useEffect(() => {
    spanRef.current = sampleRate;
    // frequencies changed: restart averaging
    avg.current.fill(0);
    peak.current.fill(0);
    haveData.current = false;
    const wfCtx = wfCanvas.current?.getContext('2d');
    if (wfCtx) wfCtx.clearRect(0, 0, WF_W, WF_H);
  }, [sampleRate]);
  useEffect(() => {
    refDbRef.current = refDb;
  }, [refDb]);
  // Hann window once
  useEffect(() => {
    if (windowReady.current) return;
    const win = new Float32Array(NFFT);
    for (let i = 0; i < NFFT; i++) {
      win[i] = 0.5 * (1 - Math.cos((2 * Math.PI * i) / (NFFT - 1)));
    }
    fft.current.setWindow(win);
    windowReady.current = true;
  }, []);
  // fps counter
  useEffect(() => {
    const t = setInterval(() => { setFps(frames.current); frames.current = 0; }, 1000);
    return () => clearInterval(t);
  }, []);
  // stop the radio when leaving the page
  useEffect(() => {
    const r = radio;
    return () => { if (r) r.stop(); };
  }, [radio]);

  const binPower = (cur: Float32Array) => {
    // exponential average + decaying peak hold
    const a = haveData.current ? AVG_ALPHA : 1.0;
    for (let k = 0; k < NFFT; k++) {
      avg.current[k] = a * cur[k] + (1 - a) * avg.current[k];
      peak.current[k] = Math.max(peak.current[k] * PEAK_DECAY, cur[k]);
    }
    haveData.current = true;
  };

  const drawSpectrum = () => {
    const canvas = specCanvas.current;
    const ctx = canvas?.getContext('2d');
    if (!canvas || !ctx) return;
    const dbTop = refDbRef.current;
    const dbBot = dbTop - RANGE_DB;
    const yOf = (db: number) => SPEC_H - ((db - dbBot) / (dbTop - dbBot)) * SPEC_H;

    ctx.clearRect(0, 0, SPEC_W, SPEC_H);
    ctx.fillStyle = '#0b0f19';
    ctx.fillRect(0, 0, SPEC_W, SPEC_H);
    // grid every 10 dB
    ctx.strokeStyle = '#2a3350';
    ctx.lineWidth = 1;
    ctx.fillStyle = '#8a93b5';
    ctx.font = '10px monospace';
    let first = Math.ceil(dbBot / 10) * 10;
    for (let db = first; db <= dbTop; db += 10) {
      const y = Math.round(yOf(db)) + 0.5;
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(SPEC_W, y);
      ctx.stroke();
      ctx.fillText(`${db}`, 4, y - 3);
    }
    // frequency scale
    const f0 = freqRef.current - spanRef.current / 2;
    const f1 = freqRef.current + spanRef.current / 2;
    ctx.fillText(`${(f0 / 1e6).toFixed(3)} MHz`, 4, SPEC_H - 4);
    const c = (f0 / 2 + f1 / 2) / 1e6;
    ctx.fillText(`${c.toFixed(3)} MHz`, SPEC_W / 2 - 34, SPEC_H - 4);
    ctx.textAlign = 'right';
    ctx.fillText(`${(f1 / 1e6).toFixed(3)} MHz`, SPEC_W - 4, SPEC_H - 4);
    ctx.textAlign = 'left';

    // traces: averaged (cyan) + peak hold (gray)
    const drawTrace = (data: Float32Array, color: string) => {
      ctx.strokeStyle = color;
      ctx.lineWidth = 1;
      ctx.beginPath();
      for (let k = 0; k < NFFT; k++) {
        const x = (k / (NFFT - 1)) * (SPEC_W - 1);
        const y = yOf(Math.max(dbBot, Math.min(dbTop, data[k])));
        if (k === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
      }
      ctx.stroke();
    };
    drawTrace(peak.current, '#5f6b7a');
    drawTrace(avg.current, '#00e5ff');
  };

  const drawWaterfallRow = () => {
    const canvas = wfCanvas.current;
    const ctx = canvas?.getContext('2d');
    if (!ctx) return;
    const dbTop = refDbRef.current;
    const dbBot = dbTop - RANGE_DB;
    ctx.drawImage(ctx.canvas, 0, 0, WF_W, WF_H - 1, 0, 1, WF_W, WF_H - 1);
    const bucket = Math.max(1, Math.floor(NFFT / WF_W));
    for (let x = 0; x < WF_W; x++) {
      // max of the bins covered by this pixel column
      let p = -Infinity;
      for (let j = x * bucket; j < Math.min((x + 1) * bucket, NFFT); j++) {
        if (avg.current[j] > p) p = avg.current[j];
      }
      let mag = 0;
      if (isFinite(p)) {
        const rel = (p - dbBot) / RANGE_DB;
        mag = Math.max(0, Math.min(heatmap.length - 1, Math.floor(rel * heatmap.length)));
      }
      ctx.fillStyle = '#' + heatmap[mag];
      ctx.fillRect(x, 0, 1, 1);
    }
  };

  const onSamples = (f32: Float32Array) => {
    const avail = f32.length / 2;
    if (avail <= 0) return;

    // keep the most recent NFFT complex samples (accumulate small chunks)
    let block = f32;
    if (avail < NFFT) {
      const merged = new Float32Array(carry.current.length + f32.length);
      merged.set(carry.current, 0);
      merged.set(f32, carry.current.length);
      block = merged;
      const keep = Math.min(block.length, 2 * NFFT);
      block = block.subarray(block.length - keep);
    }
    const tail = block.length >= 2 * NFFT
      ? block.subarray(block.length - 2 * NFFT)
      : null;
    if (!tail) {
      carry.current = new Float32Array(block);
      return;
    }
    carry.current = new Float32Array(0);

    // deinterleave the newest NFFT complex samples
    const re = reBuf.current, im = imBuf.current;
    for (let i = 0; i < NFFT; i++) {
      re[i] = tail[2 * i];
      im[i] = tail[2 * i + 1];
    }
    const out = fft.current.transform(re, im);
    // fftshift: bin order -fs/2..fs/2
    const half = NFFT / 2;
    const cur = new Float32Array(NFFT);
    for (let k = 0; k < NFFT; k++) {
      const src = (k + half) % NFFT;
      const p = out.real[src] * out.real[src] + out.imag[src] * out.imag[src];
      cur[k] = 10 * Math.log10(p / (NFFT * NFFT) + 1e-20);
    }
    binPower(cur);
    frames.current++;

    const now = Date.now();
    if (now - lastSpecDraw.current > 33) {
      lastSpecDraw.current = now;
      drawSpectrum();
    }
    if (now - lastWfDraw.current > 50) {
      lastWfDraw.current = now;
      drawWaterfallRow();
    }
  };

  const start = () => {
    if (radio) {
      radio.stop();
    }
    avg.current.fill(0);
    peak.current.fill(0);
    haveData.current = false;
    const wfCtx = wfCanvas.current?.getContext('2d');
    if (wfCtx) wfCtx.clearRect(0, 0, WF_W, WF_H);

    const provider = new RTL2832U_Provider();
    const receiver = new SpectrumTap(onSamples);
    const rtlRadio = new Radio(provider, receiver);
    const freqHz = frequency * frequencyMag;
    freqRef.current = freqHz;
    spanRef.current = sampleRate;
    rtlRadio.setFrequency(freqHz);
    rtlRadio.setSampleRate(sampleRate);
    if (gain !== null) rtlRadio.setGain(gain);
    if (biasTEnabled) rtlRadio.enableBiasTee(true);
    rtlRadio.start();
    setRadio(rtlRadio);
    setRunning(true);
  };

  const stop = () => {
    if (radio) radio.stop();
    setRunning(false);
  };

  const retune = (newFreqHz: number) => {
    freqRef.current = newFreqHz;
    if (radio && running) radio.setFrequency(newFreqHz);
  };

  const changeRef = (delta: number) => {
    setRefDb(Math.min(0, Math.max(-120, refDb + delta)));
  };

  const resetPeak = () => {
    peak.current.fill(0);
  };

  const download = () => {
    const f0 = freqRef.current - spanRef.current / 2;
    const step = spanRef.current / NFFT;
    let lines = 'freq_hz,db\n';
    for (let k = 0; k < NFFT; k++) {
      lines += `${(f0 + k * step).toFixed(1)},${avg.current[k].toFixed(2)}\n`;
    }
    downloadFile(`rtlsdr-spectrum-${new Date().toISOString()}.csv`,
      'data:text/csv;charset=UTF-8,' + encodeURIComponent(lines));
  };

  const setGainLive = (g: number | null) => {
    setGain(g);
    if (radio && running) radio.setGain(g);
  };

  const setBiasLive = (on: boolean) => {
    setBiasTEnabled(on);
    if (radio && running) radio.enableBiasTee(on);
  };

  return (
    <Container>
      <Box display="flex" justifyContent="center" alignItems="center"
        minHeight="8vh" sx={{ marginBottom: '10px' }}>
        <Stack spacing={2} sx={{ marginRight: '30px' }}>
          <ButtonGroup variant="contained" aria-label="Basic button group">
            <Button disabled={running} onClick={start}>Start</Button>
            <Button disabled={!running} onClick={stop}>Stop</Button>
            <Button onClick={download}>Download spectrum</Button>
          </ButtonGroup>
        </Stack>

        <FormControl defaultValue="">
          <Label>Frequency [Hz]</Label>
          <Stack direction="row">
            <NumberInput
              disabled={running}
              aria-label="Center frequency"
              placeholder="Type a number…"
              value={frequency}
              onChange={(_, val) => { const v = val ?? frequency; setFrequency(v); retune(v * frequencyMag); }}
            />
            <Select
              disabled={running}
              value={frequencyMag}
              onChange={(event) => setFrequencyMag(Number(event.target.value))}
              sx={{ marginRight: '15px' }}
            >
              <MenuItem value={1}>Hz</MenuItem>
              <MenuItem value={1000}>kHz</MenuItem>
              <MenuItem value={1000000}>MHz</MenuItem>
              <MenuItem value={1000000000}>GHz</MenuItem>
            </Select>
          </Stack>
        </FormControl>

        <FormControl defaultValue="">
          <Label>RF gain</Label>
          <Select
            value={gain === null ? 'auto' : String(gain)}
            onChange={(event) => setGainLive(event.target.value === 'auto' ? null : Number(event.target.value))}
            sx={{ marginRight: '15px', width: '120px' }}
          >
            <MenuItem value="auto">Auto</MenuItem>
            <MenuItem value="0">0 dB</MenuItem>
            <MenuItem value="9.6">9.6 dB</MenuItem>
            <MenuItem value="19.7">19.7 dB</MenuItem>
            <MenuItem value="29.7">29.7 dB</MenuItem>
            <MenuItem value="40.2">40.2 dB</MenuItem>
            <MenuItem value="49.6">49.6 dB</MenuItem>
          </Select>
        </FormControl>

        <FormControl defaultValue="">
          <Label>Sample rate</Label>
          <Select
            disabled={running}
            value={sampleRate}
            onChange={(event) => setSampleRate(Number(event.target.value))}
            sx={{ marginRight: '15px', width: '130px' }}
          >
            <MenuItem value={1024000}>1.024 MSPS</MenuItem>
            <MenuItem value={2048000}>2.048 MSPS</MenuItem>
            <MenuItem value={2400000}>2.4 MSPS</MenuItem>
          </Select>
        </FormControl>

        <FormControl>
          <Label>Bias-T</Label>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <input
              type="checkbox"
              id="spectrumBiast"
              checked={biasTEnabled}
              onChange={(e) => setBiasLive(e.target.checked)}
              style={{ width: '20px', cursor: 'pointer' }}
            />
            <label htmlFor="spectrumBiast" style={{ cursor: 'pointer' }}>
              {biasTEnabled ? 'ON (5V to antenna)' : 'OFF'}
            </label>
          </Box>
        </FormControl>
      </Box>

      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, marginBottom: '4px' }}>
        <Typography variant="caption" color="text.secondary">
          {running ? 'Live' : 'Stopped'} · {fps} FFT/s · span {spanRef.current / 1e6} MHz
        </Typography>
        <ButtonGroup size="small" sx={{ marginLeft: 'auto' }}>
          <Button onClick={() => changeRef(+5)} disabled={!haveData.current}>Ref +5</Button>
          <Button onClick={() => changeRef(-5)} disabled={!haveData.current}>Ref −5</Button>
          <Button onClick={resetPeak} disabled={!haveData.current}>Reset peak</Button>
        </ButtonGroup>
      </Box>

      <canvas ref={specCanvas} width={SPEC_W} height={SPEC_H}
        style={{ width: '100%', maxWidth: '1000px', display: 'block', border: '1px solid #2a3350' }} />
      <canvas ref={wfCanvas} width={WF_W} height={WF_H}
        style={{ width: '100%', maxWidth: '1000px', display: 'block', border: '1px solid #2a3350' }} />

      <Typography variant="caption" color="text.secondary" display="block" sx={{ marginTop: '4px' }}>
        Levels are relative (dBFS) — no absolute dBm without calibration. Waterfall: newest at the top.
        Requires WebUSB (Chrome/Edge/Opera) and RTL2832U (0x0bda:0x2832/0x2838).
      </Typography>
    </Container>
  );
}

function Container(props: { children: React.ReactNode }) {
  return <Box sx={{ width: '100%', maxWidth: '1000px', margin: '0 auto' }}>{props.children}</Box>;
}

export default RtlSpectrum;
