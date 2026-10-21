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

import React, { useRef, useState } from 'react';

import Container from '@mui/material/Container';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import ButtonGroup from '@mui/material/ButtonGroup';
import { FormControl } from '@mui/base/FormControl';
import Tab from '@mui/material/Tab';
import Tabs from '@mui/material/Tabs';

import { LineChart } from '@mui/x-charts/LineChart';
import JammingHistoryChart, { JammingHistoryPoint } from '../components/JammingHistoryChart';
import SkyMapChart, { SkyMapSat } from '../components/SkyMapChart';

import MenuItem from '@mui/material/MenuItem';
import Select from '@mui/material/Select';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';

import Label from '../components/Label';
import NumberInput from '../components/NumberInput';
import Stack from '@mui/system/Stack';

import Table from '@mui/material/Table';
import TableBody from '@mui/material/TableBody';
import TableCell from '@mui/material/TableCell';
import TableContainer from '@mui/material/TableContainer';
import TableHead from '@mui/material/TableHead';
import TableRow from '@mui/material/TableRow';
import Paper from '@mui/material/Paper';

import { RTL2832U_Provider } from "../device/rtlsdr/rtl2832u";
import { Radio } from '../device/radio';
import { LoggingReceiver, SampleReceiver } from '../device/sample_receiver';
import { WebSocketReceiver } from '../device/websocket_receiver';
import { Demodulator as IsmDemodulator } from '../protocol/ism/demodulator'
import { GnssDemodulatorClient } from '../protocol/gnss/gnssWorkerClient'
import { Protocol, isIsm, isGNSS } from '../protocol/protocol'

import { downloadFile } from '../utils/io';

const toHex = (buffer: Uint8Array) => {
  return Array.prototype.map.call(buffer, (x: number) => ('00' + x.toString(16)).slice(-2)).join('');
}

// Doppler search grids. A typical un-calibrated RTL-SDR clock is 20-80 PPM off
// (31-126 kHz at L1), so the DEEP range is the one that actually finds satellites
// on an un-calibrated dongle; the cluster center then yields the PPM correction.
const DOPPLER_MODES = {
  normal: { range: 5000, step: 250 },
  wide: { range: 25000, step: 250 },
  deep: { range: 160000, step: 500 },
} as const;
type DopplerMode = keyof typeof DOPPLER_MODES;

function RtlDecoder() {
  const [radio, setRadio] = useState<Radio>();
  const [protocol, setProtocol] = useState<Protocol>(Protocol.ADSB);
  const [frequency, setFrequency] = useState<number>(1090);
  const [frequencyMag, setFrequencyMag] = useState<number>(1000000);
  const [biasTEnabled, setBiasTEnabled] = useState<boolean>(false);

  // Input source selection
  const [inputSource, setInputSource] = useState<'USB' | 'WebSocket'>('USB');
  const defaultWebSocketUrl = 'ws://localhost:8765';
  const [websocketUrl, setWebsocketUrl] = useState<string>(defaultWebSocketUrl);
  const [websocketReceiver, setWebsocketReceiver] = useState<WebSocketReceiver | null>(null);

  // Doppler search mode (un-calibrated RTL clocks are tens of PPM off) + PPM correction
  const [dopplerMode, setDopplerMode] = useState<DopplerMode>('normal');
  const [ppm, setPpm] = useState<number>(0);

  const [decodedItems, setDecodedItems] = useState<any>([]);
  // Satellites detected in the last demodulator pass (live sky map input)
  const [skySats, setSkySats] = useState<SkyMapSat[]>([]);

  // Active tab (0 = Decode, 1 = Live Sky Map)
  const [activeTab, setActiveTab] = useState<number>(0);

  const [powerLevels, setPowerLevels] = useState([]);

  // Jamming status
  const [jammingStatus, setJammingStatus] = useState<any>(null);
  const [jammingHistory, setJammingHistory] = useState<JammingHistoryPoint[]>([]);

  const pointsBatch = 10000;

  const xPoints: Array<number> = [];
  for (let i = 0; i < pointsBatch; i++) {
    xPoints.push(i);
  }

  const ismDemodulator = new IsmDemodulator();
  const gnssDemodulator = useRef(new GnssDemodulatorClient()).current;
  // Terminate the demodulation worker when the page unmounts
  React.useEffect(() => () => gnssDemodulator.terminate(), []);

  const download = () => {
    let lines = 'decoded,time,msg'
    for(let i=0; i<decodedItems.length; i++) {
      lines += [decodedItems[i].decoded, decodedItems[i].time.toISOString(), decodedItems[i].msg].join(',');
      lines += '\n';
    }
    downloadFile(`spectrum-${new Date().toISOString()}.csv`, 'data:text/csv;charset=UTF-8,' + encodeURIComponent(lines));
  };

return (
  <Container maxWidth="lg">
    <Tabs
      value={activeTab}
      onChange={(_, v: number) => setActiveTab(v)}
      sx={{ marginBottom: '10px' }}
    >
      <Tab label="Decode" />
      <Tab label="Live Sky Map" />
    </Tabs>
    {activeTab === 1 && (
      <Box sx={{ marginBottom: '20px' }}>
        <SkyMapChart detectedSats={skySats} />
      </Box>
    )}
    {activeTab === 0 && (
    <>
    <Box display="flex"
      justifyContent="center"
      alignItems="center"
      minHeight="10vh"
      sx={{ marginBottom: '30px', flexWrap: 'wrap', rowGap: 2 }}>

      <Stack spacing={2} sx={{ marginRight: '30px' }}>
        <ButtonGroup variant="contained" aria-label="Basic button group">
        <Button disabled={radio?.isPlaying() || websocketReceiver?.isConnected()} onClick={ async () => {
          const freqHz = frequency*frequencyMag;
          console.log("frequency to be set", freqHz);

            // WebSocket input source
            if (inputSource === 'WebSocket') {
              console.log(`[WebSocket] Starting WebSocket receiver from ${websocketUrl}`);

              // Create the logging receiver
              // Handle demodulator results (from the worker or the inline fallback)
              const handleGnssResult = (result: any) => {

                    // Create a message object for display with jamming info
                    let decoded = '';

                    // Jamming status (if present)
                    if (result.jamming.isJammed) {
                      // Show frequency only for CW tone jamming (not broadband noise)
                      const freqInfo = (result.jamming.jammingType === 'CW_TONE' || result.jamming.jammingType === 'SWEPT_CW')
                        ? `, Freq: ${(result.jamming.peakFrequencyHz / 1000).toFixed(1)}kHz`
                        : '';
                      decoded += `⚠️ JAMMING: ${result.jamming.jammingType} (J/S: ${result.jamming.jammingToSignalRatio.toFixed(1)}dB${freqInfo}) | `;
                    }

                    // Satellite info; in wide/deep mode the mean Doppler of the
                    // cluster ≈ the dongle clock error (baseband offset = -PPM·1575.42 Hz)
                    if (result.satellites.length > 0) {
                      decoded += `${result.satellites.length} sat(s): ${result.satellites.map(s => `${s.prn}(${s.snr.toFixed(1)}dB)`).join(', ')}`;
                      if (dopplerMode !== 'normal') {
                        const meanHz = result.satellites.reduce((sum, s) => sum + s.dopplerHz, 0) / result.satellites.length;
                        decoded += ` | clock offset ≈ ${(meanHz / 1000).toFixed(1)} kHz → try PPM ${(-meanHz / 1575.42).toFixed(1)}`;
                      }
                    } else if (result.jamming.isJammed) {
                      decoded += 'No satellites - jammed';
                    } else {
                      decoded += `No satellites | Noise: ${result.jamming.noiseFloorDb.toFixed(1)}dB (relative)`;
                    }

                    const gnssMsg = {
                      decoded,
                      time: new Date(result.timestamp),
                      msg: result
                    };
                    setDecodedItems(prevDecodedItems => {
                      return [gnssMsg, ...prevDecodedItems];
                    });

                    // Update jamming status, observables history and live sky map
                    setJammingStatus(result.jamming);
                    setSkySats(result.satellites.map(s => ({ prn: s.prn, snr: s.snr })));
                    setJammingHistory(prev => {
                      const list = (result.satellites || []) as any[];
                      const tracking = list.some(s => s.state) ? list.filter(s => s.state === 'TRACKING') : list;
                      const n = tracking.length;
                      const cn0 = n > 0 ? tracking.reduce((sum: number, s: any) => sum + (s.cn0 || 0), 0) / n : 0;
                      const next = [...prev, {
                        time: result.timestamp,
                        noiseFloorDb: result.jamming.noiseFloorDb,
                        totalPowerDb: result.jamming.totalPowerDb,
                        cn0,
                        sats: n
                      }];
                      return next.slice(-100);
                    });
              };
              gnssDemodulator.onResult(handleGnssResult);

              const loggingReceiver = new LoggingReceiver(protocol, (msg) => {
                if (protocol === Protocol.ADSB) {
                  setDecodedItems(prevDecodedItems => {
                    return [msg, ...prevDecodedItems];
                  });
                } else if (isGNSS(protocol)) {
                  // GNSS processing
                  console.log(`[RtlDecoder] GNSS callback received, msg.msg type: ${msg.msg?.constructor?.name}, length: ${msg.msg?.length}`);
                  // Protocol is set once when radio starts, not on every sample batch
                  const workerResult = gnssDemodulator.processSamples(msg.msg.buffer);
                  if (workerResult) handleGnssResult(workerResult);
                } else {
                  setPowerLevels(prevMsg => {
                    if (prevMsg.length > pointsBatch-1000) {
                      const groups = ismDemodulator.detectPulses(protocol, prevMsg, 0.050, 10000);
                      setDecodedItems(prevDecodedItems => {
                        return [...groups, ...prevDecodedItems];
                      });
                      return msg;
                    } else {
                      return [...prevMsg, ...msg];
                    }
                  });
                }
              });

              let sampleReceiver: SampleReceiver = loggingReceiver;

              // Set GNSS protocol once (not on every sample batch!)
              if (isGNSS(protocol)) {
                console.log(`[WebSocket] Setting GNSS protocol: ${protocol}`);
                gnssDemodulator.setProtocol(protocol);
                gnssDemodulator.setDoppler(DOPPLER_MODES[dopplerMode].range, DOPPLER_MODES[dopplerMode].step);
              }

              // Create and connect WebSocket receiver
              const wsReceiver = new WebSocketReceiver(websocketUrl, sampleReceiver);
              try {
                await wsReceiver.connect();
                setWebsocketReceiver(wsReceiver);
                console.log('[WebSocket] Connected and streaming!');
              } catch (error) {
                console.error('[WebSocket] Failed to connect:', error);
                alert(`Failed to connect to WebSocket server at ${websocketUrl}\n\nMake sure the SDRPlay bridge is running:\npython sdrplay_bridge.py`);
              }

            // USB (RTL-SDR) input source
            } else if (radio === undefined) {
              const rtlProvider = new RTL2832U_Provider();
              // Ask for the device inside the click gesture: Chrome only shows
              // the USB chooser while transient user activation is valid, and
              // Radio.start() would otherwise call requestDevice() too late.
              // (The provider caches the device, so Radio.start() reuses it.)
              await rtlProvider.get();

              // Create the logging receiver
              // Handle demodulator results (from the worker or the inline fallback)
              const handleGnssResult = (result: any) => {

                    // Create a message object for display with jamming info
                    let decoded = '';

                    // Jamming status (if present)
                    if (result.jamming.isJammed) {
                      // Show frequency only for CW tone jamming (not broadband noise)
                      const freqInfo = (result.jamming.jammingType === 'CW_TONE' || result.jamming.jammingType === 'SWEPT_CW')
                        ? `, Freq: ${(result.jamming.peakFrequencyHz / 1000).toFixed(1)}kHz`
                        : '';
                      decoded += `⚠️ JAMMING: ${result.jamming.jammingType} (J/S: ${result.jamming.jammingToSignalRatio.toFixed(1)}dB${freqInfo}) | `;
                    }

                    // Satellite info; in wide/deep mode the mean Doppler of the
                    // cluster ≈ the dongle clock error (baseband offset = -PPM·1575.42 Hz)
                    if (result.satellites.length > 0) {
                      decoded += `${result.satellites.length} sat(s): ${result.satellites.map(s => `${s.prn}(${s.snr.toFixed(1)}dB)`).join(', ')}`;
                      if (dopplerMode !== 'normal') {
                        const meanHz = result.satellites.reduce((sum, s) => sum + s.dopplerHz, 0) / result.satellites.length;
                        decoded += ` | clock offset ≈ ${(meanHz / 1000).toFixed(1)} kHz → try PPM ${(-meanHz / 1575.42).toFixed(1)}`;
                      }
                    } else if (result.jamming.isJammed) {
                      decoded += 'No satellites - jammed';
                    } else {
                      decoded += `No satellites | Noise: ${result.jamming.noiseFloorDb.toFixed(1)}dB (relative)`;
                    }

                    const gnssMsg = {
                      decoded,
                      time: new Date(result.timestamp),
                      msg: result
                    };
                    setDecodedItems(prevDecodedItems => {
                      return [gnssMsg, ...prevDecodedItems];
                    });

                    // Update jamming status, observables history and live sky map
                    setJammingStatus(result.jamming);
                    setSkySats(result.satellites.map(s => ({ prn: s.prn, snr: s.snr })));
                    setJammingHistory(prev => {
                      const list = (result.satellites || []) as any[];
                      const tracking = list.some(s => s.state) ? list.filter(s => s.state === 'TRACKING') : list;
                      const n = tracking.length;
                      const cn0 = n > 0 ? tracking.reduce((sum: number, s: any) => sum + (s.cn0 || 0), 0) / n : 0;
                      const next = [...prev, {
                        time: result.timestamp,
                        noiseFloorDb: result.jamming.noiseFloorDb,
                        totalPowerDb: result.jamming.totalPowerDb,
                        cn0,
                        sats: n
                      }];
                      return next.slice(-100);
                    });
              };
              gnssDemodulator.onResult(handleGnssResult);

              const loggingReceiver = new LoggingReceiver(protocol, (msg) => {
                if (protocol === Protocol.ADSB) {
                  setDecodedItems(prevDecodedItems => {
                    return [msg, ...prevDecodedItems];
                  });
                } else if (isGNSS(protocol)) {
                  // GNSS processing
                  console.log(`[RtlDecoder] GNSS callback received, msg.msg type: ${msg.msg?.constructor?.name}, length: ${msg.msg?.length}`);
                  // Protocol is set once when radio starts, not on every sample batch
                  const workerResult = gnssDemodulator.processSamples(msg.msg.buffer);
                  if (workerResult) handleGnssResult(workerResult);
                } else {
                  setPowerLevels(prevMsg => {
                    if (prevMsg.length > pointsBatch-1000) {
                      const groups = ismDemodulator.detectPulses(protocol, prevMsg, 0.050, 10000);
                      setDecodedItems(prevDecodedItems => {
                        return [...groups, ...prevDecodedItems];
                      });
                      return msg;
                    } else {
                      return [...prevMsg, ...msg];
                    }
                  });
                }
              });

              let sampleReceiver: SampleReceiver = loggingReceiver;

              const rtlRadio = new Radio(rtlProvider, sampleReceiver);
              rtlRadio.setFrequency(freqHz);
              rtlRadio.setGain(40);
              // The GNSS demodulator assumes 2.048 MSPS (1 ms = 2048 samples);
              // the Radio default is 2.0 MSPS, which breaks C/A-code correlation.
              if (isGNSS(protocol)) rtlRadio.setSampleRate(2048000);
              // Clock (PPM) correction for the RTL-SDR dongle
              if (ppm !== 0) rtlRadio.setFrequencyCorrection(ppm);

              // Enable Bias-T if requested (for active GNSS antennas)
              if (biasTEnabled) {
                console.log("[RTL-SDR] Enabling Bias-T for active antenna power");
                rtlRadio.enableBiasTee(true);
              }

              // Set GNSS protocol once (not on every sample batch!)
              if (isGNSS(protocol)) {
                console.log(`[RTL-SDR] Setting GNSS protocol: ${protocol}`);
                gnssDemodulator.setProtocol(protocol);
                gnssDemodulator.setDoppler(DOPPLER_MODES[dopplerMode].range, DOPPLER_MODES[dopplerMode].step);
              }

              rtlRadio.start();
              setRadio(rtlRadio);
            } else {
              radio.setFrequency(freqHz);
              radio.start();
            }
      }}>Listen&Decode</Button>
      <Button disabled={(radio === undefined || !radio.isPlaying()) && (websocketReceiver === null || !websocketReceiver.isConnected())} onClick={async ()=>{
        if (radio) {
          await radio.stop();
        }
        if (websocketReceiver) {
          websocketReceiver.disconnect();
          setWebsocketReceiver(null);
        }
      }}>Disconnect</Button>
        </ButtonGroup>
        <Button onClick={download}>Download spectrum</Button>
      </Stack>

      <FormControl defaultValue="">
        <Label>Input Source</Label>
        <Stack direction="row">
          <Select
            disabled={radio?.isPlaying() || websocketReceiver?.isConnected()}
            value={inputSource}
            onChange={(event: any) => setInputSource(event.target.value)}
            sx={{ marginRight: '15px' }}
          >
            <MenuItem value="USB">RTL-SDR (USB)</MenuItem>
            <MenuItem value="WebSocket">WebSocket (SDRPlay/Remote)</MenuItem>
          </Select>
        </Stack>
      </FormControl>

      {inputSource === 'WebSocket' && (
        <FormControl defaultValue="">
          <Label>WebSocket URL</Label>
          <Stack direction="row">
            <TextField
              disabled={websocketReceiver?.isConnected()}
              aria-label="WebSocket URL"
              placeholder="ws://localhost:8765"
              value={websocketUrl}
              onChange={(event) => setWebsocketUrl(event.target.value)}
              sx={{ width: '300px', marginRight: '15px' }}
              size="small"
              variant="outlined"
            />
          </Stack>
        </FormControl>
      )}

      <FormControl defaultValue="" >
      <Label>Protocol</Label>

      <Stack direction="row" >
        <Select
          disabled={radio?.isPlaying()}
          value={protocol}
          onChange={(event) => {
            setProtocol(event.target.value as Protocol);
            if (event.target.value === Protocol.ADSB) {
              setFrequency(1090);
              setFrequencyMag(1000000);
            } else if (event.target.value === Protocol.GNSS_GPS_L1) {
              setFrequency(1575.42);
              setFrequencyMag(1000000);
            } else if (event.target.value === Protocol.GNSS_GALILEO_E1) {
              setFrequency(1575.42);
              setFrequencyMag(1000000);
            } else if (event.target.value === Protocol.GNSS_GLONASS_L1) {
              setFrequency(1602);
              setFrequencyMag(1000000);
            } else if (event.target.value === Protocol.GNSS_BEIDOU_B1I) {
              setFrequency(1561.098);
              setFrequencyMag(1000000);
            } else {
              setFrequency(433);
              setFrequencyMag(1000000);
            }
          }}
          sx={{ marginRight: '15px' }}
        >
          <MenuItem value={Protocol.ADSB}>ADS-B</MenuItem>
          <MenuItem disabled value={""}>GNSS Constellations</MenuItem>
          <MenuItem value={Protocol.GNSS_GPS_L1}>GPS L1 C/A (USA)</MenuItem>
          <MenuItem value={Protocol.GNSS_GALILEO_E1}>Galileo E1 (Europe)</MenuItem>
          <MenuItem value={Protocol.GNSS_GLONASS_L1}>GLONASS L1OF (Russia)</MenuItem>
          <MenuItem value={Protocol.GNSS_BEIDOU_B1I}>BeiDou B1I (China)</MenuItem>
          <MenuItem disabled value={""}>ISM bands</MenuItem>
          <MenuItem value={Protocol.GateTX24}>GateTX (24bit)</MenuItem>
        </Select>
      </Stack>
    </FormControl>

      <FormControl defaultValue="">
      <Label>Tested frequency [Hz]</Label>
      <Stack direction="row" >
        <NumberInput
          disabled={radio?.isPlaying()}
          aria-label="Tested frequency"
          placeholder="Type a number…"
          value={frequency}
          onChange={(_, val) => setFrequency(val ?? 1090)}
        />
        <Select
          disabled={radio?.isPlaying()}
          value={frequencyMag}
          onChange={(event: any) => setFrequencyMag(event.target.value)}
          sx={{ marginRight: '15px' }}
        >
          <MenuItem value={1}>Hz</MenuItem>
          <MenuItem value={1000}>kHz</MenuItem>
          <MenuItem value={1000000}>MHz</MenuItem>
          <MenuItem value={1000000000}>GHz</MenuItem>
        </Select>
      </Stack>
    </FormControl>

    <FormControl>
      <Label>Bias-T (Active Antenna Power)</Label>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
        <input
          type="checkbox"
          id="biastCheckbox"
          disabled={radio?.isPlaying()}
          checked={biasTEnabled}
          onChange={(e) => setBiasTEnabled(e.target.checked)}
          style={{ width: '20px', height: '20px', cursor: radio?.isPlaying() ? 'not-allowed' : 'pointer' }}
        />
        <label htmlFor="biastCheckbox" style={{ cursor: radio?.isPlaying() ? 'not-allowed' : 'pointer' }}>
          {biasTEnabled ? 'ON (5V power to antenna)' : 'OFF'}
        </label>
      </Box>
    </FormControl>

    <FormControl>
      <Label>Clock correction (PPM, live)</Label>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
        <NumberInput
          aria-label="PPM correction"
          placeholder="0"
          value={ppm}
          onChange={(_, val) => {
            const v = val ?? 0;
            setPpm(v);
            radio?.setFrequencyCorrection(v);
          }}
        />
        <Typography variant="caption" color="text.secondary">
          Typical RTL-SDR: 20–80 PPM. Wrong PPM shifts satellites outside the Doppler grid.
        </Typography>
      </Box>
    </FormControl>

    <FormControl>
      <Label>Doppler search range</Label>
      <Stack direction="row" sx={{ alignItems: 'center' }}>
        <Select
          value={dopplerMode}
          onChange={(event) => {
            const mode = event.target.value as DopplerMode;
            setDopplerMode(mode);
            gnssDemodulator.setDoppler(DOPPLER_MODES[mode].range, DOPPLER_MODES[mode].step);
          }}
          sx={{ marginRight: '15px', width: '300px' }}
        >
          <MenuItem value="normal">Normal (±5 kHz) — fastest</MenuItem>
          <MenuItem value="wide">WIDE (±25 kHz) — covers ±16 PPM</MenuItem>
          <MenuItem value="deep">DEEP (±160 kHz) — covers ±100 PPM, ~7 min/cycle</MenuItem>
        </Select>
        <Typography variant="caption" color="text.secondary">
          Start with DEEP on an un-calibrated dongle; the detected cluster gives the PPM.
        </Typography>
      </Stack>
    </FormControl>
  </Box>
  </>
  )}

  <Box
    justifyContent='center'
  >
    { isIsm(protocol) ? <LineChart
      width={1100}
      height={300}
      slotProps={{ legend: { hidden: true } }}
      series={[{ data: powerLevels, label: 'dB',  showMark: false, color: '#cc0052' }]}
      xAxis={[{ data: xPoints}]}
    /> : null} 
    <TableContainer component={Paper}>
    <Table size="small" aria-label="simple table">
      <TableHead>
        <TableRow>
          <TableCell width='60%'>Decoded</TableCell>
          <TableCell width='20%'>Time</TableCell>
          <TableCell width='20%'>Data</TableCell>
        </TableRow>
      </TableHead>
      <TableBody>
      {decodedItems.map((row, index) => (
          <TableRow
            key={index}
            sx={{ '&:last-child td, &:last-child th': { border: 0 } }}
          >
            <TableCell width='60%' sx={{'fontSize': 12, wordBreak: 'break-all'}} component="th" scope="row">
              {row.decoded}
            </TableCell>
            <TableCell width='20%' component="th" scope="row">
              {row.time.toISOString()}
            </TableCell>
            <TableCell width='20%' component="th" scope="row">
              {toHex(row.msg).replace(/0+$/, '')}
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  </TableContainer>
  </Box>
  {jammingHistory.length > 0 && <JammingHistoryChart history={jammingHistory} />}
</Container>
);
}

export default RtlDecoder;
