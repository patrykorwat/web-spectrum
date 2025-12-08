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

import React, { useState, useEffect } from 'react';

import Container from '@mui/material/Container';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import ButtonGroup from '@mui/material/ButtonGroup';
import { FormControl } from '@mui/base/FormControl';
import MuiFormControl from '@mui/material/FormControl';
import LinearProgress from '@mui/material/LinearProgress';

import { LineChart } from '@mui/x-charts/LineChart';

import MenuItem from '@mui/material/MenuItem';
import Select from '@mui/material/Select';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';
import Radio from '@mui/material/Radio';
import RadioGroup from '@mui/material/RadioGroup';
import FormControlLabel from '@mui/material/FormControlLabel';
import FormLabel from '@mui/material/FormLabel';

import Label from '../components/Label.tsx';
import NumberInput from '../components/NumberInput.tsx';
import Stack from '@mui/system/Stack';

import Table from '@mui/material/Table';
import TableBody from '@mui/material/TableBody';
import TableCell from '@mui/material/TableCell';
import TableContainer from '@mui/material/TableContainer';
import TableHead from '@mui/material/TableHead';
import TableRow from '@mui/material/TableRow';
import Paper from '@mui/material/Paper';

import { LoggingReceiver } from '../device/sample_receiver.ts';
import { FilteringSampleReceiver, FilterConfig } from '../device/filter_receiver.ts';
import { WebSocketReceiver } from '../device/websocket_receiver.ts';
import { Demodulator as IsmDemodulator } from '../protocol/ism/demodulator.ts'
import { GNSSDemodulator } from '../protocol/gnss/demodulator.ts'
import { Protocol, isIsm, isGNSS } from '../protocol/protocol.ts'

import { downloadFile } from '../utils/io.ts';

const toHex = (buffer: Uint8Array) => {
  return Array.prototype.map.call(buffer, (x: number) => ('00' + x.toString(16)).slice(-2)).join('');
}

function SdrPlayDecoder() {
  const [protocol, setProtocol] = useState<Protocol>(Protocol.GNSS_GPS_L1);
  const [frequency, setFrequency] = useState<number>(1575.42);
  const [frequencyMag, setFrequencyMag] = useState<number>(1000000);

  // Bridge mode selection
  const [bridgeMode, setBridgeMode] = useState<'sdrplay' | 'gnss-sdr'>('gnss-sdr');

  // WebSocket connection
  const defaultWebSocketUrl = bridgeMode === 'gnss-sdr' ? 'ws://localhost:8766' : 'ws://localhost:8765';
  const [websocketUrl, setWebsocketUrl] = useState<string>(defaultWebSocketUrl);
  const [websocketReceiver, setWebsocketReceiver] = useState<WebSocketReceiver | null>(null);

  // RSPduo-specific settings
  const [tunerSelection, setTunerSelection] = useState<number>(1);
  const [biasTeeEnabled, setBiasTeeEnabled] = useState<boolean>(false);

  // Interference mitigation filter state
  const [filterEnabled, setFilterEnabled] = useState<boolean>(false);
  const [notchFrequency, setNotchFrequency] = useState<number>(0); // Auto-detect
  const [filterReceiver, setFilterReceiver] = useState<FilteringSampleReceiver | null>(null);

  const [decodedItems, setDecodedItems] = useState<any>([]);

  const [powerLevels, setPowerLevels] = useState([]);

  // Satellite tracking history for chart (last 60 data points)
  const [satelliteHistory, setSatelliteHistory] = useState<Array<{time: number, count: number, avgCN0: number}>>([]);

  // Progress tracking for recording and processing
  const [progressPhase, setProgressPhase] = useState<string>('');
  const [progressPercent, setProgressPercent] = useState<number>(0);
  const [progressElapsed, setProgressElapsed] = useState<number>(0);
  const [progressTotal, setProgressTotal] = useState<number>(0);
  const [progressMessage, setProgressMessage] = useState<string>('');

  // GNSS collection control
  const [gnssCollectionRunning, setGnssCollectionRunning] = useState<boolean>(false);
  const [gnssCollectionLoading, setGnssCollectionLoading] = useState<boolean>(false);
  const [gnssCollectionError, setGnssCollectionError] = useState<string | null>(null);

  const pointsBatch = 10000;

  const xPoints: Array<number> = [];
  for (let i = 0; i < pointsBatch; i++) {
    xPoints.push(i);
  }

  const ismDemodulator = new IsmDemodulator();
  const [gnssDemodulator] = useState(() => new GNSSDemodulator());

  // Update WebSocket URL when bridge mode changes
  useEffect(() => {
    if (!websocketReceiver?.isConnected()) {
      const newUrl = bridgeMode === 'gnss-sdr' ? 'ws://localhost:8766' : 'ws://localhost:8765';
      setWebsocketUrl(newUrl);
    }
  }, [bridgeMode, websocketReceiver]);

  // Poll GNSS collection status every 2 seconds
  useEffect(() => {
    if (bridgeMode !== 'gnss-sdr') return;

    const pollStatus = async () => {
      try {
        const response = await fetch('http://localhost:8767/status');
        const data = await response.json();
        setGnssCollectionRunning(data.running);
        setGnssCollectionError(null);
      } catch (error) {
        // Control API not running - that's okay
        setGnssCollectionRunning(false);
      }
    };

    pollStatus(); // Check immediately
    const interval = setInterval(pollStatus, 2000); // Then every 2 seconds

    return () => clearInterval(interval);
  }, [bridgeMode]);

  const download = () => {
    let lines = 'decoded,time,msg'
    for(let i=0; i<decodedItems.length; i++) {
      lines += [decodedItems[i].decoded, decodedItems[i].time.toISOString(), decodedItems[i].msg].join(',');
      lines += '\n';
    }
    downloadFile(`spectrum-${new Date().toISOString()}.csv`, 'data:text/csv;charset=UTF-8,' + encodeURIComponent(lines));
  };

  // GNSS Collection Control Functions
  const handleStartGnssCollection = async () => {
    setGnssCollectionLoading(true);
    setGnssCollectionError(null);
    try {
      const response = await fetch('http://localhost:8767/start', { method: 'POST' });
      const data = await response.json();
      if (response.ok) {
        setGnssCollectionRunning(true);
        console.log('[GNSS Control] Started collection:', data);
      } else {
        setGnssCollectionError(data.error || 'Failed to start collection');
      }
    } catch (error) {
      setGnssCollectionError('Control API not available. Run control_api.py first.');
      console.error('[GNSS Control] Error starting collection:', error);
    } finally {
      setGnssCollectionLoading(false);
    }
  };

  const handleStopGnssCollection = async () => {
    setGnssCollectionLoading(true);
    setGnssCollectionError(null);
    try {
      const response = await fetch('http://localhost:8767/stop', { method: 'POST' });
      const data = await response.json();
      if (response.ok) {
        setGnssCollectionRunning(false);
        console.log('[GNSS Control] Stopped collection:', data);
      } else {
        setGnssCollectionError(data.error || 'Failed to stop collection');
      }
    } catch (error) {
      setGnssCollectionError('Control API not available');
      console.error('[GNSS Control] Error stopping collection:', error);
    } finally {
      setGnssCollectionLoading(false);
    }
  };

  const handleRestartGnssCollection = async () => {
    setGnssCollectionLoading(true);
    setGnssCollectionError(null);
    try {
      const response = await fetch('http://localhost:8767/restart', { method: 'POST' });
      const data = await response.json();
      if (response.ok) {
        setGnssCollectionRunning(true);
        console.log('[GNSS Control] Restarted collection:', data);
      } else {
        setGnssCollectionError(data.error || 'Failed to restart collection');
      }
    } catch (error) {
      setGnssCollectionError('Control API not available. Run control_api.py first.');
      console.error('[GNSS Control] Error restarting collection:', error);
    } finally {
      setGnssCollectionLoading(false);
    }
  };

return (
  <Container maxWidth="lg">
    {/* Bridge Mode Selector */}
    <Box sx={{ marginBottom: '20px', marginTop: '20px' }}>
      <MuiFormControl>
        <FormLabel id="bridge-mode-label">Signal Processing Mode</FormLabel>
        <RadioGroup
          row
          aria-labelledby="bridge-mode-label"
          name="bridge-mode-group"
          value={bridgeMode}
          onChange={(event) => setBridgeMode(event.target.value as 'sdrplay' | 'gnss-sdr')}
        >
          <FormControlLabel
            value="sdrplay"
            control={<Radio />}
            label="Raw IQ Mode (Browser Processing)"
            disabled={websocketReceiver?.isConnected()}
          />
          <FormControlLabel
            value="gnss-sdr"
            control={<Radio />}
            label="Professional Mode (GNSS-SDR)"
            disabled={websocketReceiver?.isConnected()}
          />
        </RadioGroup>
        <Typography variant="caption" color="text.secondary" sx={{ marginTop: '5px' }}>
          {bridgeMode === 'sdrplay'
            ? '⚠️ Raw IQ: Browser-based correlation (simplified algorithms, high bandwidth)'
            : '✅ Professional: Uses GNSS-SDR for accurate C/N0, positioning, and jamming detection'
          }
        </Typography>
      </MuiFormControl>
    </Box>

    {/* Listen & Decode Button - Show first so user connects before starting collection */}
    <Box
      display="flex"
      flexDirection="column"
      alignItems="flex-start"
      gap={3}
      minHeight="10vh"
      sx={{ marginBottom: '30px' }}>

      <Box sx={{ display: 'flex', gap: 2, alignItems: 'center', flexWrap: 'wrap' }}>
        <ButtonGroup variant="contained" aria-label="Basic button group">
        <Button disabled={websocketReceiver?.isConnected()} onClick={ async () => {
          const freqHz = frequency*frequencyMag;
          console.log(`[SDRPlay WebSocket] Connecting to ${websocketUrl} for ${protocol}`);

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

                  // Check if msg.msg is already a JSON result object (from parse_gnss_logs)
                  // or if it's a Uint8Array buffer that needs processing
                  let result;
                  if (msg.msg && typeof msg.msg === 'object' && 'satellites' in msg.msg && 'protocol' in msg.msg) {
                    // Already a GNSS result object from parse_gnss_logs.py
                    console.log(`[RtlDecoder] Received pre-processed GNSS data with ${msg.msg.satellites.length} satellites`);
                    result = msg.msg;
                  } else if (msg.msg && msg.msg.buffer) {
                    // Binary IQ samples that need processing
                    result = gnssDemodulator.processSamples(msg.msg.buffer);
                  } else {
                    result = null;
                  }

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

                    // Update satellite history for chart
                    setSatelliteHistory(prevHistory => {
                      const satCount = result.satellites.length;
                      const avgCN0 = satCount > 0
                        ? result.satellites.reduce((sum: number, sat: any) => sum + (sat.cn0 || 0), 0) / satCount
                        : 0;

                      const newPoint = {
                        time: Date.now(),
                        count: satCount,
                        avgCN0: avgCN0
                      };

                      // Keep last 60 points (about 1 minute of data)
                      const updated = [newPoint, ...prevHistory].slice(0, 60);
                      return updated;
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
              let sampleReceiver = loggingReceiver;
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

          // Create and connect WebSocket receiver with progress callback
          const wsReceiver = new WebSocketReceiver(websocketUrl, sampleReceiver, (progress) => {
            setProgressPhase(progress.phase);
            setProgressPercent(progress.progress);
            setProgressElapsed(progress.elapsed);
            setProgressTotal(progress.total);
            setProgressMessage(progress.message);
          });
          try {
            await wsReceiver.connect();
            setWebsocketReceiver(wsReceiver);
            console.log('[SDRPlay WebSocket] Connected and streaming!');
          } catch (error) {
            console.error('[SDRPlay WebSocket] Failed to connect:', error);

            let errorMessage = `Failed to connect to WebSocket server at ${websocketUrl}\n\n`;

            if (bridgeMode === 'gnss-sdr') {
              errorMessage += `Make sure the GNSS-SDR bridge is running:\n\n`;
              errorMessage += `Terminal 1: Start GNSS-SDR Bridge\n`;
              errorMessage += `./run_gnss_sdr_bridge.sh\n\n`;
              errorMessage += `This will automatically start GNSS-SDR and listen on port 8766.\n`;
              errorMessage += `GNSS-SDR processes signals professionally with accurate C/N0 measurements.`;
            } else {
              const tunerArg = `--tuner ${tunerSelection}`;
              const biasTeeArg = biasTeeEnabled ? ' --bias-tee' : '';
              errorMessage += `Make sure the SDRPlay bridge is running:\n\n`;
              errorMessage += `./run_sdrplay_bridge.sh --freq ${freqHz} --rate 2.048e6 --gain 40 ${tunerArg}${biasTeeArg}`;
            }

            alert(errorMessage);
          }
      }}>Listen&Decode</Button>
      <Button disabled={websocketReceiver === null || !websocketReceiver.isConnected()} onClick={async ()=>{
        if (websocketReceiver) {
          websocketReceiver.disconnect();
          setWebsocketReceiver(null);
        }
      }}>Disconnect</Button>
        </ButtonGroup>

        <TextField
          disabled={websocketReceiver?.isConnected()}
          label={bridgeMode === 'gnss-sdr' ? 'WebSocket URL (GNSS-SDR Bridge)' : 'WebSocket URL (SDRPlay Bridge)'}
          aria-label="WebSocket URL"
          placeholder={bridgeMode === 'gnss-sdr' ? 'ws://localhost:8766' : 'ws://localhost:8765'}
          value={websocketUrl}
          onChange={(event) => setWebsocketUrl(event.target.value)}
          size="small"
          sx={{ width: '320px' }}
        />

        <Button onClick={download} variant="outlined">Download spectrum</Button>
      </Box>
    </Box>

    {/* Collection Control Buttons - ALWAYS visible in GNSS-SDR mode */}
    {bridgeMode === 'gnss-sdr' && (
      <Box sx={{ marginBottom: '20px', padding: '20px', backgroundColor: 'rgba(76, 175, 80, 0.08)', borderRadius: '8px', border: '1px solid rgba(76, 175, 80, 0.3)' }}>
        <Typography variant="h6" sx={{ marginBottom: '15px', color: 'success.main' }}>
          🎛️ Data Collection Control
        </Typography>

        <Box sx={{ marginBottom: '10px', display: 'flex', gap: 2, alignItems: 'center' }}>
          <ButtonGroup variant="contained" size="medium">
            <Button
              disabled={gnssCollectionRunning || gnssCollectionLoading}
              onClick={handleStartGnssCollection}
              color="success"
            >
              {gnssCollectionLoading ? 'Starting...' : 'Start Collection'}
            </Button>
            <Button
              disabled={!gnssCollectionRunning || gnssCollectionLoading}
              onClick={handleStopGnssCollection}
              color="error"
            >
              {gnssCollectionLoading ? 'Stopping...' : 'Stop Collection'}
            </Button>
            <Button
              disabled={gnssCollectionLoading}
              onClick={handleRestartGnssCollection}
              color="warning"
            >
              {gnssCollectionLoading ? 'Restarting...' : 'Restart Collection'}
            </Button>
          </ButtonGroup>

          <Typography variant="body1" sx={{ fontWeight: 'bold', color: gnssCollectionRunning ? 'success.main' : 'error.main' }}>
            {gnssCollectionRunning ? '🟢 RUNNING' : '🔴 STOPPED'}
          </Typography>
        </Box>

        {gnssCollectionError && (
          <Typography variant="body2" sx={{ marginTop: '10px', color: 'error.main', padding: '8px', backgroundColor: 'rgba(255, 0, 0, 0.1)', borderRadius: '4px' }}>
            ⚠️ Backend not available: {gnssCollectionError}
          </Typography>
        )}
      </Box>
    )}

    {/* Progress Status - Show when collection is running */}
    {bridgeMode === 'gnss-sdr' && gnssCollectionRunning && websocketReceiver?.isConnected() && (
      <Box sx={{ marginBottom: '20px', padding: '20px', backgroundColor: 'rgba(33, 150, 243, 0.08)', borderRadius: '8px', border: '1px solid rgba(33, 150, 243, 0.3)' }}>
        {progressPhase ? (
          <>
            <Typography variant="h6" sx={{ marginBottom: '10px', color: progressPhase === 'complete' ? 'success.main' : 'info.main' }}>
              📊 Current Status: {progressPhase === 'recording' ? '📡 Recording' : progressPhase === 'processing' ? '🛰️ Processing' : progressPhase === 'complete' ? '✅ Complete' : '⏳ ' + progressPhase}
            </Typography>

            <Box sx={{ marginBottom: '10px' }}>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', marginBottom: '5px' }}>
                <Typography variant="body2" sx={{ fontWeight: 'bold' }}>
                  {progressMessage}
                </Typography>
                <Typography variant="body2" sx={{ fontWeight: 'bold' }}>
                  {progressPercent}%
                </Typography>
              </Box>
              <LinearProgress
                variant="determinate"
                value={progressPercent}
                sx={{ height: '8px', borderRadius: '4px' }}
              />
            </Box>

            <Box sx={{ display: 'flex', gap: 3, marginTop: '10px' }}>
              <Typography variant="caption">
                ⏱️ Elapsed: {Math.floor(progressElapsed / 60)}:{String(progressElapsed % 60).padStart(2, '0')}
              </Typography>
              {progressTotal > 0 && (
                <>
                  <Typography variant="caption">
                    ⏳ Total: {Math.floor(progressTotal / 60)}:{String(progressTotal % 60).padStart(2, '0')}
                  </Typography>
                  <Typography variant="caption">
                    🕐 Remaining: {Math.floor((progressTotal - progressElapsed) / 60)}:{String((progressTotal - progressElapsed) % 60).padStart(2, '0')}
                  </Typography>
                </>
              )}
            </Box>
          </>
        ) : (
          <>
            <Typography variant="h6" sx={{ marginBottom: '10px', color: 'info.main' }}>
              ⏳ Collection Running
            </Typography>
            <Typography variant="body2" sx={{ marginBottom: '10px' }}>
              Waiting for progress update from data collection process...
            </Typography>
            <LinearProgress sx={{ height: '8px', borderRadius: '4px' }} />
            <Typography variant="caption" sx={{ display: 'block', marginTop: '10px', fontStyle: 'italic' }}>
              Progress updates arrive every ~10 seconds
            </Typography>
          </>
        )}
      </Box>
    )}

    {/* Setup Instructions - Only show for GNSS-SDR mode when not connected */}
    {bridgeMode === 'gnss-sdr' && !websocketReceiver?.isConnected() && (
      <Box sx={{ marginBottom: '20px', padding: '20px', backgroundColor: 'rgba(33, 150, 243, 0.08)', borderRadius: '8px', border: '1px solid rgba(33, 150, 243, 0.3)' }}>
        <Typography variant="h6" sx={{ marginBottom: '15px', color: 'info.main' }}>
          📡 Setup Instructions
        </Typography>

        <Typography variant="body2" sx={{ display: 'block', marginBottom: '15px', padding: '15px', backgroundColor: 'rgba(76, 175, 80, 0.1)', borderRadius: '4px', border: '1px solid rgba(76, 175, 80, 0.3)' }}>
          <strong>🚀 Setup (one time):</strong><br />
          <Box component="span" sx={{ display: 'block', fontFamily: 'monospace', backgroundColor: 'rgba(0,0,0,0.3)', padding: '10px', borderRadius: '4px', marginTop: '10px', fontSize: '1.1em' }}>
            ./start_all.sh
          </Box>
          <span style={{ fontSize: '0.95em', display: 'block', marginTop: '10px' }}>
            This starts the backend services (Control API + GNSS Bridge).
          </span>
        </Typography>

        <Typography variant="body2" sx={{ display: 'block', marginBottom: '15px', padding: '15px', backgroundColor: 'rgba(33, 150, 243, 0.1)', borderRadius: '4px', border: '1px solid rgba(33, 150, 243, 0.3)' }}>
          <strong>📡 Usage (every time):</strong><br />
          <Box component="ol" sx={{ marginTop: '10px', paddingLeft: '20px', '& li': { marginBottom: '8px' } }}>
            <li><strong>First:</strong> Click <strong>"Listen&Decode"</strong> (above) to connect to the bridge</li>
            <li><strong>Then:</strong> Click <strong>"Start Collection"</strong> (below) to begin GPS recording</li>
            <li>Wait ~8-10 minutes for first satellite data to appear</li>
            <li>Use <strong>"Stop"</strong> or <strong>"Restart Collection"</strong> as needed</li>
          </Box>
        </Typography>
        <Typography variant="caption" sx={{ display: 'block', marginTop: '10px', color: 'info.main', fontStyle: 'italic' }}>
          ℹ️ First cycle takes 5-10 minutes (recording + ephemeris decoding). Be patient!
        </Typography>

        {/* Processing Timeline */}
        <Box sx={{ marginTop: '15px', padding: '12px', backgroundColor: 'rgba(0, 0, 0, 0.3)', borderRadius: '4px' }}>
          <Typography variant="caption" sx={{ display: 'block', marginBottom: '8px', fontWeight: 'bold' }}>
            📊 Processing Timeline (First Cycle):
          </Typography>
          <Box sx={{ paddingLeft: '10px', fontSize: '0.85em' }}>
            <Typography variant="caption" component="div" sx={{ marginBottom: '3px' }}>
              <span style={{ color: '#4CAF50' }}>⏱️ Min 0-5:</span> 📡 Recording GPS samples (5 minutes)
            </Typography>
            <Typography variant="caption" component="div" sx={{ marginBottom: '3px' }}>
              <span style={{ color: '#2196F3' }}>⏱️ Min 5-6:</span> 🛰️  Satellite acquisition (tracking starts)
            </Typography>
            <Typography variant="caption" component="div" sx={{ marginBottom: '3px' }}>
              <span style={{ color: '#FF9800' }}>⏱️ Min 6-8:</span> 📖 Ephemeris decoding (navigation data)
            </Typography>
            <Typography variant="caption" component="div" sx={{ color: '#4CAF50', fontWeight: 'bold' }}>
              <span>⏱️ Min 8-10:</span> 📍 First position fix! → ✅ DATA APPEARS HERE!
            </Typography>
          </Box>
        </Box>

        <Typography variant="caption" sx={{ display: 'block', marginTop: '10px', color: 'warning.main' }}>
          ⚠️ Make sure your GPS antenna has a clear sky view!
        </Typography>
      </Box>
    )}

    {/* Satellite Acquisition Info - Only show for GNSS-SDR mode when connected */}
    {bridgeMode === 'gnss-sdr' && websocketReceiver?.isConnected() && (
      <Box sx={{ marginBottom: '20px', padding: '15px', backgroundColor: 'rgba(0, 255, 0, 0.05)', borderRadius: '8px', border: '1px solid rgba(0, 255, 0, 0.2)' }}>
        {/* Device Status Alert */}
        {decodedItems.length > 0 && decodedItems[0].msg?.deviceStatus && !decodedItems[0].msg.deviceStatus.sdrplayConnected && (
          <Box sx={{ marginBottom: '15px', padding: '15px', backgroundColor: 'rgba(255, 0, 0, 0.15)', borderRadius: '8px', border: '2px solid #f44336' }}>
            <Typography variant="h6" sx={{ color: 'error.main', marginBottom: '10px', fontWeight: 'bold' }}>
              ⚠️ SDRPlay Device Disconnected!
            </Typography>
            <Typography variant="body2" sx={{ color: 'error.main', marginBottom: '8px' }}>
              {decodedItems[0].msg.deviceStatus.deviceError}
            </Typography>
            <Typography variant="caption" sx={{ display: 'block', color: 'text.secondary' }}>
              Possible solutions:
              <Box component="ul" sx={{ marginTop: '5px', paddingLeft: '20px' }}>
                <li>Check USB cable is securely connected</li>
                <li>Try a different USB port (avoid USB hubs)</li>
                <li>Unplug and replug the SDRPlay device</li>
                <li>Click "Restart Collection" button above after reconnecting</li>
              </Box>
            </Typography>
          </Box>
        )}

        <Typography variant="h6" sx={{ marginBottom: '10px', color: 'success.main' }}>
          🛰️ Satellite Acquisition Status
        </Typography>
        <Box>
          <Typography variant="body1" sx={{ marginBottom: '5px' }}>
            {decodedItems.length > 0 && decodedItems[0].msg?.satellites ? (
              <>
                <strong>Satellites Tracking:</strong> {decodedItems[0].msg.satellites.length} satellite(s)
                {decodedItems[0].msg.satellites.length > 0 && (
                  <Box sx={{ marginTop: '10px', fontSize: '0.9em' }}>
                    {decodedItems[0].msg.satellites.slice(0, 8).map((sat: any, idx: number) => (
                      <Box key={idx} sx={{ marginBottom: '5px', paddingLeft: '20px' }}>
                        • PRN {sat.prn}: C/N0 = {sat.cn0?.toFixed(1) || 'N/A'} dB-Hz,
                        Doppler = {sat.dopplerHz?.toFixed(0) || 'N/A'} Hz,
                        State = {sat.state || 'UNKNOWN'}
                      </Box>
                    ))}
                    {decodedItems[0].msg.satellites.length > 8 && (
                      <Box sx={{ paddingLeft: '20px', fontStyle: 'italic', color: 'text.secondary' }}>
                        ... and {decodedItems[0].msg.satellites.length - 8} more
                      </Box>
                    )}
                  </Box>
                )}
              </>
            ) : (
              <>
                <strong>Status:</strong> Acquiring satellites... (this may take 30-60 seconds)
                <br />
                <Typography variant="caption" color="text.secondary">
                  GNSS-SDR is processing signals. Satellite data will appear once acquisition completes.
                </Typography>
              </>
            )}
          </Typography>
          {decodedItems.length > 0 && decodedItems[0].msg?.jamming && progressPhase === 'complete' && (
            <Box sx={{ marginTop: '10px', padding: '10px', backgroundColor: decodedItems[0].msg.jamming.isJammed ? 'rgba(244, 67, 54, 0.1)' : 'rgba(76, 175, 80, 0.1)', borderRadius: '4px' }}>
              <Typography variant="body2" sx={{ color: decodedItems[0].msg.jamming.isJammed ? 'error.main' : 'success.main', fontWeight: 'bold' }}>
                {decodedItems[0].msg.jamming.isJammed ? '⚠️ Signal Anomaly Detected' : '✓ Signal Quality Normal'}
              </Typography>
              {decodedItems[0].msg.jamming.isJammed && (
                <Box sx={{ marginTop: '8px', fontSize: '0.85em' }}>
                  <Typography variant="body2" sx={{ color: 'text.primary' }}>
                    <strong>Type:</strong> {decodedItems[0].msg.jamming.jammingType.replace(/_/g, ' ')}
                    {(decodedItems[0].msg.jamming.jammingType.includes('SPOOFING') ||
                      decodedItems[0].msg.jamming.jammingType === 'MATCHED_POWER_ATTACK') && ' 🚨'}
                  </Typography>
                  <Typography variant="body2" sx={{ color: 'text.primary' }}>
                    <strong>Severity:</strong> {decodedItems[0].msg.jamming.jammingSeverity || 'UNKNOWN'}
                    {' '}(Confidence: {(decodedItems[0].msg.jamming.jammerConfidence * 100).toFixed(0)}%)
                  </Typography>
                  <Typography variant="body2" sx={{ color: 'text.primary' }}>
                    <strong>Detection Method:</strong> {(decodedItems[0].msg.jamming.detectionMethod || 'UNKNOWN').replace(/_/g, ' ')}
                  </Typography>
                  <Typography variant="body2" sx={{ color: 'text.primary' }}>
                    <strong>Avg C/N0:</strong> {decodedItems[0].msg.jamming.avgCN0.toFixed(1)} dB-Hz
                    {' '}(Variation: ±{decodedItems[0].msg.jamming.cn0Variation?.toFixed(1) || '0.0'} dB)
                  </Typography>
                  {decodedItems[0].msg.jamming.cn0StdDev && (
                    <Typography variant="body2" sx={{ color: 'text.primary' }}>
                      <strong>Multi-Satellite Analysis:</strong> Std Dev = {decodedItems[0].msg.jamming.cn0StdDev.toFixed(1)} dB
                      {' '}(Range: {decodedItems[0].msg.jamming.minCN0.toFixed(1)} - {decodedItems[0].msg.jamming.maxCN0.toFixed(1)} dB-Hz)
                    </Typography>
                  )}
                  {decodedItems[0].msg.jamming.cn0Correlation !== undefined && (
                    <Typography variant="body2" sx={{ color: decodedItems[0].msg.jamming.cn0Correlation > 0.95 ? 'error.main' : 'text.primary' }}>
                      <strong>C/N0 Correlation:</strong> {(decodedItems[0].msg.jamming.cn0Correlation * 100).toFixed(1)}%
                      {decodedItems[0].msg.jamming.cn0Correlation > 0.95 && ' ⚠️ High correlation - spoofing indicator!'}
                    </Typography>
                  )}
                  {decodedItems[0].msg.jamming.dopplerVariation !== undefined && (
                    <Typography variant="body2" sx={{ color: decodedItems[0].msg.jamming.dopplerVariation < 20 ? 'warning.main' : 'text.primary' }}>
                      <strong>Doppler Analysis:</strong> Variation = {decodedItems[0].msg.jamming.dopplerVariation.toFixed(1)} Hz
                      {decodedItems[0].msg.jamming.dopplerVariation < 20 && ' ⚠️ Low variation - possible spoofing!'}
                    </Typography>
                  )}
                  {decodedItems[0].msg.jamming.jammingType === 'HIGH_CONFIDENCE_SPOOFING' && (
                    <Typography variant="caption" sx={{ display: 'block', marginTop: '8px', color: 'error.main', fontWeight: 'bold', fontStyle: 'italic' }}>
                      🚨 HIGH CONFIDENCE SPOOFING DETECTED! Multiple indicators confirm attack. DO NOT TRUST POSITION DATA.
                    </Typography>
                  )}
                  {(decodedItems[0].msg.jamming.jammingType === 'POSSIBLE_SPOOFING' ||
                    decodedItems[0].msg.jamming.jammingType === 'SUSPECTED_SPOOFING_LOW_DOPPLER') && (
                    <Typography variant="caption" sx={{ display: 'block', marginTop: '8px', color: 'warning.main', fontStyle: 'italic' }}>
                      ⚠️ Spoofing indicators detected. Verify position accuracy with alternative sources.
                    </Typography>
                  )}
                </Box>
              )}
              {!decodedItems[0].msg.jamming.isJammed && (
                <Typography variant="body2" sx={{ marginTop: '5px', fontSize: '0.85em', color: 'text.secondary' }}>
                  Avg C/N0: {decodedItems[0].msg.jamming.avgCN0.toFixed(1)} dB-Hz | {decodedItems[0].msg.jamming.numTracking} satellites tracked
                </Typography>
              )}
            </Box>
          )}
        </Box>

        {/* Satellite Tracking History Chart */}
        {satelliteHistory.length > 1 && (
          <Box sx={{ marginTop: '15px' }}>
            <Typography variant="h6" sx={{ marginBottom: '10px', fontSize: '0.95em' }}>
              📈 Satellite Tracking History
            </Typography>
            <LineChart
              width={900}
              height={200}
              series={[
                {
                  data: satelliteHistory.slice().reverse().map(p => p.count),
                  label: 'Satellites',
                  color: '#4CAF50',
                  showMark: false
                },
                {
                  data: satelliteHistory.slice().reverse().map(p => p.avgCN0 / 5), // Scale down to fit
                  label: 'Avg C/N0 (/5)',
                  color: '#2196F3',
                  showMark: false
                }
              ]}
              xAxis={[{
                data: satelliteHistory.slice().reverse().map((_, i) => i),
                label: 'Time (recent →)'
              }]}
              yAxis={[{
                label: 'Count / C/N0 (scaled)'
              }]}
              slotProps={{
                legend: {
                  direction: 'row',
                  position: { vertical: 'top', horizontal: 'middle' },
                  padding: 0
                }
              }}
            />
            <Typography variant="caption" sx={{ display: 'block', marginTop: '5px', color: 'text.secondary', textAlign: 'center' }}>
              Shows last {satelliteHistory.length} updates (~{Math.round(satelliteHistory.length / 60)} min of data)
            </Typography>
          </Box>
        )}
      </Box>
    )}

    {/* Hide all detailed settings when GNSS-SDR mode is selected */}
    <Box display="flex"
      flexWrap="wrap"
      justifyContent="center"
      alignItems="flex-start"
      gap={3}
      minHeight="10vh"
      sx={{ marginBottom: '30px' }}>

      {bridgeMode === 'sdrplay' && (
      <>
      <FormControl defaultValue="" >
      <Label>Protocol</Label>

      <Stack direction="row" >
        <Select
          disabled={websocketReceiver?.isConnected()}
          value={protocol}
          onChange={(event) => {
            setProtocol(event.target.value);
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
          disabled={websocketReceiver?.isConnected()}
          aria-label="Tested frequency"
          placeholder="Type a number…"
          value={frequency}
          onChange={(_, val) => setFrequency(val)}
        />
        <Select
          disabled={websocketReceiver?.isConnected()}
          value={frequencyMag}
          onChange={(event: any) => setFrequencyMag(event.target.value)}
        >
          <MenuItem value={1}>Hz</MenuItem>
          <MenuItem value={1000}>kHz</MenuItem>
          <MenuItem value={1000000}>MHz</MenuItem>
          <MenuItem value={1000000000}>GHz</MenuItem>
        </Select>
      </Stack>
    </FormControl>

    <FormControl>
      <Label>RSPduo Tuner Selection</Label>
      <Select
        disabled={websocketReceiver?.isConnected()}
        value={tunerSelection}
        onChange={(event) => {
          const newTuner = Number(event.target.value);
          setTunerSelection(newTuner);
          // Auto-disable T-bias if switching to Tuner 1
          if (newTuner === 1 && biasTeeEnabled) {
            setBiasTeeEnabled(false);
          }
        }}
        sx={{ width: '150px' }}
      >
        <MenuItem value={1}>Tuner 1</MenuItem>
        <MenuItem value={2}>Tuner 2</MenuItem>
      </Select>
    </FormControl>

    <FormControl>
      <Label>T-bias (RSPduo Tuner 2 only)</Label>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
        <input
          type="checkbox"
          id="biasTeeCheckbox"
          disabled={websocketReceiver?.isConnected()}
          checked={biasTeeEnabled}
          onChange={(e) => {
            const newBiasTee = e.target.checked;
            setBiasTeeEnabled(newBiasTee);
            // Auto-select Tuner 2 if enabling T-bias
            if (newBiasTee && tunerSelection !== 2) {
              setTunerSelection(2);
            }
          }}
          style={{ width: '20px', height: '20px', cursor: websocketReceiver?.isConnected() ? 'not-allowed' : 'pointer' }}
        />
        <label htmlFor="biasTeeCheckbox" style={{ cursor: websocketReceiver?.isConnected() ? 'not-allowed' : 'pointer' }}>
          {biasTeeEnabled ? 'ENABLED (for active antenna)' : 'DISABLED'}
        </label>
      </Box>
      {biasTeeEnabled && (
        <Typography variant="caption" color="success.main" sx={{ mt: 0.5 }}>
          ✓ T-bias enabled on Tuner 2 (powers active antenna)
        </Typography>
      )}
    </FormControl>

    <FormControl>
      <Label>Interference Mitigation (Notch Filter + AGC + Pulse Blanking)</Label>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
        <input
          type="checkbox"
          id="filterCheckbox"
          disabled={websocketReceiver?.isConnected()}
          checked={filterEnabled}
          onChange={(e) => setFilterEnabled(e.target.checked)}
          style={{ width: '20px', height: '20px', cursor: websocketReceiver?.isConnected() ? 'not-allowed' : 'pointer' }}
        />
        <label htmlFor="filterCheckbox" style={{ cursor: websocketReceiver?.isConnected() ? 'not-allowed' : 'pointer' }}>
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
            disabled={websocketReceiver?.isConnected()}
            value={notchFrequency}
            onChange={(e) => setNotchFrequency(parseInt(e.target.value) || 0)}
            style={{ marginLeft: '10px', width: '100px' }}
          />
        </Box>
      )}
    </FormControl>
    </>
    )}
  </Box>
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
</Container>
);
}

export default SdrPlayDecoder;
