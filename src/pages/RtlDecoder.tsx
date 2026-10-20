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

import React, { useState } from 'react';

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
import { FilteringSampleReceiver, FilterConfig } from '../device/filter_receiver';
import { WebSocketReceiver } from '../device/websocket_receiver';
import { Demodulator as IsmDemodulator } from '../protocol/ism/demodulator'
import { GNSSDemodulator } from '../protocol/gnss/demodulator'
import { Protocol, isIsm, isGNSS } from '../protocol/protocol'

import { downloadFile } from '../utils/io';

const toHex = (buffer: Uint8Array) => {
  return Array.prototype.map.call(buffer, (x: number) => ('00' + x.toString(16)).slice(-2)).join('');
}

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

  // Interference mitigation filter state
  const [filterEnabled, setFilterEnabled] = useState<boolean>(false);
  const [notchFrequency, setNotchFrequency] = useState<number>(0); // Auto-detect
  const [filterReceiver, setFilterReceiver] = useState<FilteringSampleReceiver | null>(null);

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
  const [gnssDemodulator] = useState(() => new GNSSDemodulator());

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
      sx={{ marginBottom: '30px' }}>

      <Stack spacing={2} sx={{ marginRight: '30px' }}>
        <ButtonGroup variant="contained" aria-label="Basic button group">
        <Button disabled={radio?.isPlaying() || websocketReceiver?.isConnected()} onClick={ async () => {
          const freqHz = frequency*frequencyMag;
          console.log("frequency to be set", freqHz);

            // WebSocket input source
            if (inputSource === 'WebSocket') {
              console.log(`[WebSocket] Starting WebSocket receiver from ${websocketUrl}`);

              // Store filter receiver ref for dynamic updates
              let filterReceiverRef: FilteringSampleReceiver | null = null;

              // Create the logging receiver
              const loggingReceiver = new LoggingReceiver(protocol, (msg) => {
                if (protocol === Protocol.ADSB) {
                  setDecodedItems(prevDecodedItems => {
                    return [msg, ...prevDecodedItems];
                  });
                } else if (isGNSS(protocol)) {
                  // GNSS processing
                  console.log(`[RtlDecoder] GNSS callback received, msg.msg type: ${msg.msg?.constructor?.name}, length: ${msg.msg?.length}`);
                  // Protocol is set once when radio starts, not on every sample batch
                  const result = gnssDemodulator.processSamples(msg.msg.buffer);
                  if (result) {
                    // Auto-update notch filter frequency if CW jamming detected
                    if (result.jamming.isJammed && result.jamming.jammingType === 'CW_TONE' && filterReceiverRef) {
                      const detectedFreq = result.jamming.peakFrequencyHz;
                      console.log(`[AUTO-FILTER] CW tone detected at ${detectedFreq.toFixed(0)} Hz, updating notch filter`);
                      filterReceiverRef.updateConfig({
                        notchFrequencyHz: detectedFreq
                      });
                      setNotchFrequency(Math.round(detectedFreq));
                    }

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

                    // Satellite info
                    if (result.satellites.length > 0) {
                      decoded += `${result.satellites.length} sat(s): ${result.satellites.map(s => `${s.prn}(${s.snr.toFixed(1)}dB)`).join(', ')}`;
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
                  }
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

              // Wrap in filtering receiver if enabled
              let sampleReceiver: SampleReceiver = loggingReceiver;
              if (filterEnabled) {
                const filterConfig: FilterConfig = {
                  notchFilterEnabled: true,
                  notchFrequencyHz: notchFrequency || 0, // Will auto-detect if 0
                  notchBandwidthHz: 1000, // 1 kHz notch width
                  agcLimitEnabled: true,
                  agcTargetPower: 0.1, // -10dB target
                  pulseBlankingEnabled: true,
                  pulseThresholdMultiplier: 3.0
                };

                const filteringReceiver = new FilteringSampleReceiver(loggingReceiver, filterConfig);
                filterReceiverRef = filteringReceiver; // Set local ref
                setFilterReceiver(filteringReceiver); // Set state
                sampleReceiver = filteringReceiver;
                console.log('[RTL-SDR] Interference mitigation filters ENABLED');
              } else {
                console.log('[WebSocket] Interference mitigation filters DISABLED');
              }

              // Set GNSS protocol once (not on every sample batch!)
              if (isGNSS(protocol)) {
                console.log(`[WebSocket] Setting GNSS protocol: ${protocol}`);
                gnssDemodulator.setProtocol(protocol);
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

              // Store filter receiver ref for dynamic updates
              let filterReceiverRef: FilteringSampleReceiver | null = null;

              // Create the logging receiver
              const loggingReceiver = new LoggingReceiver(protocol, (msg) => {
                if (protocol === Protocol.ADSB) {
                  setDecodedItems(prevDecodedItems => {
                    return [msg, ...prevDecodedItems];
                  });
                } else if (isGNSS(protocol)) {
                  // GNSS processing
                  console.log(`[RtlDecoder] GNSS callback received, msg.msg type: ${msg.msg?.constructor?.name}, length: ${msg.msg?.length}`);
                  // Protocol is set once when radio starts, not on every sample batch
                  const result = gnssDemodulator.processSamples(msg.msg.buffer);
                  if (result) {
                    // Auto-update notch filter frequency if CW jamming detected
                    if (result.jamming.isJammed && result.jamming.jammingType === 'CW_TONE' && filterReceiverRef) {
                      const detectedFreq = result.jamming.peakFrequencyHz;
                      console.log(`[AUTO-FILTER] CW tone detected at ${detectedFreq.toFixed(0)} Hz, updating notch filter`);
                      filterReceiverRef.updateConfig({
                        notchFrequencyHz: detectedFreq
                      });
                      setNotchFrequency(Math.round(detectedFreq));
                    }

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

                    // Satellite info
                    if (result.satellites.length > 0) {
                      decoded += `${result.satellites.length} sat(s): ${result.satellites.map(s => `${s.prn}(${s.snr.toFixed(1)}dB)`).join(', ')}`;
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
                  }
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

              // Wrap in filtering receiver if enabled
              let sampleReceiver: SampleReceiver = loggingReceiver;
              if (filterEnabled) {
                const filterConfig: FilterConfig = {
                  notchFilterEnabled: true,
                  notchFrequencyHz: notchFrequency || 0, // Will auto-detect if 0
                  notchBandwidthHz: 1000, // 1 kHz notch width
                  agcLimitEnabled: true,
                  agcTargetPower: 0.1, // -10dB target
                  pulseBlankingEnabled: true,
                  pulseThresholdMultiplier: 3.0
                };

                const filteringReceiver = new FilteringSampleReceiver(loggingReceiver, filterConfig);
                filterReceiverRef = filteringReceiver; // Set local ref
                setFilterReceiver(filteringReceiver); // Set state
                sampleReceiver = filteringReceiver;
                console.log('[RTL-SDR] Interference mitigation filters ENABLED');
              } else {
                console.log('[RTL-SDR] Interference mitigation filters DISABLED');
              }

              const rtlRadio = new Radio(rtlProvider, sampleReceiver);
              rtlRadio.setFrequency(freqHz);
              rtlRadio.setGain(40);

              // Enable Bias-T if requested (for active GNSS antennas)
              if (biasTEnabled) {
                console.log("[RTL-SDR] Enabling Bias-T for active antenna power");
                rtlRadio.enableBiasTee(true);
              }

              // Set GNSS protocol once (not on every sample batch!)
              if (isGNSS(protocol)) {
                console.log(`[RTL-SDR] Setting GNSS protocol: ${protocol}`);
                gnssDemodulator.setProtocol(protocol);
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
      <Label>Interference Mitigation (Notch Filter + AGC + Pulse Blanking)</Label>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
        <input
          type="checkbox"
          id="filterCheckbox"
          disabled={radio?.isPlaying()}
          checked={filterEnabled}
          onChange={(e) => setFilterEnabled(e.target.checked)}
          style={{ width: '20px', height: '20px', cursor: radio?.isPlaying() ? 'not-allowed' : 'pointer' }}
        />
        <label htmlFor="filterCheckbox" style={{ cursor: radio?.isPlaying() ? 'not-allowed' : 'pointer' }}>
          {filterEnabled ? 'ENABLED (removes CW jamming)' : 'DISABLED'}
        </label>
      </Box>
      {filterEnabled && (
        <Box sx={{ mt: 1, pl: 4 }}>
          <label htmlFor="notchFreq" style={{ fontSize: '0.9em' }}>
            Notch Frequency (Hz, 0=auto-detect):
          </label>
          <input
            type="number"
            id="notchFreq"
            disabled={radio?.isPlaying()}
            value={notchFrequency}
            onChange={(e) => setNotchFrequency(parseInt(e.target.value) || 0)}
            style={{ marginLeft: '10px', width: '100px' }}
          />
        </Box>
      )}
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
