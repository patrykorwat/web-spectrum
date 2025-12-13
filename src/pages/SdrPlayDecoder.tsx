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

const maskSerial = (serial: string) => {
  if (!serial || serial.length <= 4) return serial;
  const first2 = serial.slice(0, 2);
  const last2 = serial.slice(-2);
  const middle = '*'.repeat(serial.length - 4);
  return `${first2}${middle}${last2}`;
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

  // Jamming/Spoofing status
  const [jammingStatus, setJammingStatus] = useState<any>(null);

  // Progress tracking for recording and processing
  const [progressPhase, setProgressPhase] = useState<string>('');
  const [progressPercent, setProgressPercent] = useState<number>(0);
  const [progressElapsed, setProgressElapsed] = useState<number>(0);
  const [progressTotal, setProgressTotal] = useState<number>(0);
  const [progressMessage, setProgressMessage] = useState<string>('');

  // File-based recording control
  const [isRecording, setIsRecording] = useState<boolean>(false);
  const [isProcessing, setIsProcessing] = useState<boolean>(false);
  const [recordingFile, setRecordingFile] = useState<string>('');

  // Recording configuration from server
  const [recordingConfig, setRecordingConfig] = useState<any>(null);
  const [deviceInfo, setDeviceInfo] = useState<any>(null);
  const [selectedPort, setSelectedPort] = useState<number>(2); // Default to Port 2

  // Spectrum analysis results
  const [spectrumAnalysis, setSpectrumAnalysis] = useState<any>(null);
  const [spectrumImageUrl, setSpectrumImageUrl] = useState<string | null>(null);

  const pointsBatch = 10000;

  const xPoints: Array<number> = [];
  for (let i = 0; i < pointsBatch; i++) {
    xPoints.push(i);
  }

  const ismDemodulator = new IsmDemodulator();
  const [gnssDemodulator] = useState(() => new GNSSDemodulator());

  // Fetch recording configuration and device info from server on mount
  useEffect(() => {
    const fetchConfig = async () => {
      try {
        const response = await fetch('http://localhost:3001/gnss/config');
        if (response.ok) {
          const config = await response.json();
          setRecordingConfig(config);
          // Initialize selected port from config
          if (config.tuner) {
            setSelectedPort(config.tuner);
          }
        }
      } catch (error) {
        console.error('Failed to fetch recording config:', error);
      }
    };

    const fetchDeviceInfo = async () => {
      try {
        const response = await fetch('http://localhost:3001/gnss/device-info');
        if (response.ok) {
          const info = await response.json();
          setDeviceInfo(info);
        }
      } catch (error) {
        console.error('Failed to fetch device info:', error);
      }
    };

    fetchConfig();
    fetchDeviceInfo();
  }, []);

  // Update WebSocket URL when bridge mode changes
  useEffect(() => {
    if (!websocketReceiver?.isConnected()) {
      const newUrl = bridgeMode === 'gnss-sdr' ? 'ws://localhost:8766' : 'ws://localhost:8765';
      setWebsocketUrl(newUrl);
    }
  }, [bridgeMode, websocketReceiver]);


  const download = () => {
    let lines = 'decoded,time,msg'
    for(let i=0; i<decodedItems.length; i++) {
      lines += [decodedItems[i].decoded, decodedItems[i].time.toISOString(), decodedItems[i].msg].join(',');
      lines += '\n';
    }
    downloadFile(`spectrum-${new Date().toISOString()}.csv`, 'data:text/csv;charset=UTF-8,' + encodeURIComponent(lines));
  };

  // File-based GPS recording controls
  const startRecording = async () => {
    try {
      // Check device availability first
      setProgressMessage('Checking SDRplay device availability...');
      const deviceCheckResponse = await fetch('http://localhost:3001/gnss/device-info');

      if (deviceCheckResponse.ok) {
        const deviceCheck = await deviceCheckResponse.json();
        if (!deviceCheck.devices || deviceCheck.devices.length === 0) {
          alert('⚠️ SDRplay device not available!\n\nThe device may be:\n• In use by another application (SDRconnect, CubicSDR, etc.)\n• Disconnected\n• Not powered\n\nPlease close other SDR applications and try again.');
          setProgressMessage('');
          return;
        }
      }

      setIsRecording(true);
      setProgressPhase('recording');
      setProgressPercent(0);
      setProgressMessage('Starting GPS data recording...');

      const response = await fetch('http://localhost:3001/gnss/start-recording', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          duration: 300, // 5 minutes
          tuner: selectedPort // Pass selected port to backend
        })
      });

      if (!response.ok) throw new Error('Failed to start recording');
      const data = await response.json();
      setRecordingFile(data.filename || '');
      setProgressMessage('Recording GPS data (5 minutes)...');

      // Poll for recording errors (check every 5 seconds)
      const recordingPollInterval = setInterval(async () => {
        try {
          const statusResponse = await fetch('http://localhost:3001/gnss/status');
          if (statusResponse.ok) {
            const status = await statusResponse.json();
            if (status.recording.error) {
              clearInterval(recordingPollInterval);
              setIsRecording(false);
              setProgressPhase('');
              setProgressMessage('');
              alert(`❌ Recording failed!\n\n${status.recording.error}\n\nPlease close other SDR applications (SDRconnect, CubicSDR, etc.) and try again.`);
            }
          }
        } catch (err) {
          console.error('Recording status poll error:', err);
        }
      }, 5000);

      // Auto-stop after 5 minutes and automatically start processing
      setTimeout(async () => {
        clearInterval(recordingPollInterval);
        setIsRecording(false);
        setProgressPhase('');
        setProgressMessage(`✅ Recording complete! Starting automatic processing...`);

        // Automatically trigger processing after recording completes
        setTimeout(() => {
          document.querySelector('[data-process-button]')?.click();
        }, 2000); // Wait 2 seconds for file to be fully written
      }, 305000); // 5 minutes + 5 seconds buffer
    } catch (error) {
      console.error('Recording error:', error);
      setIsRecording(false);
      setProgressMessage(`Error: ${error}`);
    }
  };

  const stopRecording = async () => {
    try {
      await fetch('http://localhost:3001/gnss/stop-recording', { method: 'POST' });
      setIsRecording(false);
      setProgressPhase('');
      setProgressMessage('Recording stopped. Starting automatic processing...');

      // Automatically trigger processing after manual stop
      setTimeout(() => {
        document.querySelector('[data-process-button]')?.click();
      }, 2000); // Wait 2 seconds for file to be fully written
    } catch (error) {
      console.error('Stop recording error:', error);
    }
  };

  const processRecording = async () => {
    if (!recordingFile) {
      alert('No recording file available. Please record data first.');
      return;
    }

    try {
      setIsProcessing(true);
      setProgressPhase('processing');
      setProgressPercent(0);
      setProgressMessage('Starting GNSS-SDR processing...');

      const response = await fetch('http://localhost:3001/gnss/process-recording', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ filename: recordingFile })
      });

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`Failed to start processing: ${errorText}`);
      }

      const data = await response.json();
      console.log('Processing started:', data);

      // Poll for status updates every 2 seconds
      let pollCount = 0;
      const maxPolls = 900; // 30 minutes max (900 * 2 seconds)

      const pollInterval = setInterval(async () => {
        try {
          pollCount++;
          const statusResponse = await fetch('http://localhost:3001/gnss/status');

          if (!statusResponse.ok) {
            console.error('Status endpoint error:', statusResponse.status);
            return;
          }

          const status = await statusResponse.json();
          console.log(`Poll ${pollCount}: processing.active = ${status.processing.active}, duration = ${status.processing.duration}s`);

          if (status.processing.active) {
            // Still processing - update status
            const duration = status.processing.duration;
            const minutes = Math.floor(duration / 60);
            const seconds = duration % 60;
            const message = `Processing: ${minutes}m ${seconds}s elapsed... ${status.processing.status || 'Running GNSS-SDR'}`;
            console.log('Updating progress message:', message);
            setProgressMessage(message);
            setProgressPhase('processing'); // Ensure phase is set
            setIsProcessing(true); // Ensure processing flag is set

            // Check for spectrum analysis results (generated after ~10-15 seconds)
            if (duration > 10 && recordingFile) {
              const spectrumJsonUrl = `http://localhost:3001/gnss/recordings/${recordingFile.replace('.dat', '_spectrum_analysis.json')}`;
              fetch(spectrumJsonUrl)
                .then(res => res.ok ? res.json() : null)
                .then(data => {
                  if (data && !spectrumAnalysis) {
                    console.log('Spectrum analysis loaded:', data);
                    setSpectrumAnalysis(data);
                    setSpectrumImageUrl(`http://localhost:3001/gnss/recordings/${recordingFile.replace('.dat', '_spectrum.png')}`);
                  }
                })
                .catch(() => {});  // Silently fail if not ready yet
            }
          } else {
            // Processing complete or not started
            clearInterval(pollInterval);
            setIsProcessing(false);
            setProgressPhase('');

            // Check if there was an error
            if (status.processing.error) {
              setProgressMessage(`❌ ${status.processing.error}`);
            } else if (pollCount === 1) {
              // First poll already shows inactive - processing may have failed to start
              setProgressMessage('⚠️ Processing did not start. Check backend logs.');
            } else if (status.processing.duration > 0) {
              // Processing ran and completed
              setProgressMessage('✅ Processing complete! Check for output files or satellite data above.');
            } else {
              // Processing inactive with zero duration - unexpected state
              setProgressMessage('⚠️ Processing stopped unexpectedly. Check backend logs.');
            }
          }

          // Safety timeout check
          if (pollCount >= maxPolls) {
            clearInterval(pollInterval);
            setIsProcessing(false);
            setProgressPhase('');
            setProgressMessage('⚠️ Processing timeout - check logs');
          }
        } catch (pollError) {
          console.error('Status poll error:', pollError);
          // Don't stop polling on network errors - keep trying
        }
      }, 2000);

    } catch (error) {
      console.error('Processing error:', error);
      setIsProcessing(false);
      setProgressPhase('');
      setProgressMessage(`❌ Error: ${error}`);
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
                  // Check if this is a GNSS log message
                  if (msg.msg && typeof msg.msg === 'object' && msg.msg.type === 'gnss_log') {
                    // GNSS log message from GNSS-SDR processing
                    const logMsg = {
                      decoded: msg.msg.message,
                      time: new Date(msg.msg.timestamp),
                      msg: msg.msg
                    };
                    setDecodedItems(prevDecodedItems => {
                      return [logMsg, ...prevDecodedItems];
                    });

                    // Parse log message for satellite tracking info
                    // GNSS-SDR format: "Tracking of GPS L1 C/A signal started on channel X for satellite GPS PRN Y"
                    // or "Loss of lock in channel X!"
                    const message = msg.msg.message;

                    // Track satellites by counting tracking starts and losses
                    const trackingStarted = message.match(/Tracking of GPS .* signal started on channel (\d+) for satellite GPS PRN (\d+)/i);
                    const lossOfLock = message.match(/Loss of lock in channel (\d+)/i);
                    const cn0Match = message.match(/CN0\s*=\s*([\d.]+)\s*dB-Hz/i); // Rare, but try anyway

                    // Use a ref or state to track currently locked satellites
                    if (trackingStarted || lossOfLock || cn0Match) {
                      setSatelliteHistory(prev => {
                        const now = Date.now();

                        // Get current tracking count from last entry or start fresh
                        let currentCount = prev.length > 0 ? prev[prev.length - 1].count : 0;
                        let currentCN0 = prev.length > 0 ? prev[prev.length - 1].avgCN0 : 0;

                        if (trackingStarted) {
                          currentCount = Math.min(currentCount + 1, 12); // Max 12 channels
                        } else if (lossOfLock) {
                          currentCount = Math.max(currentCount - 1, 0);
                        }

                        if (cn0Match) {
                          currentCN0 = parseFloat(cn0Match[1]);
                        }

                        const newEntry = {
                          time: now,
                          count: currentCount,
                          avgCN0: currentCN0
                        };

                        // Add entry and keep last 100 points
                        const updated = [...prev, newEntry];
                        return updated.slice(-100);
                      });
                    }

                    return; // Early return - don't process as regular GNSS data
                  }

                  // GNSS processing (debug logging removed for cleaner console output)

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

                    // Position fix status
                    if (result.positionFix) {
                      decoded += `📍 POSITION FIX: ${result.positionFix.latitude.toFixed(6)}°N, ${result.positionFix.longitude.toFixed(6)}°E `;
                      decoded += `(±${result.positionFix.hdop.toFixed(1)}m HDOP, ${result.positionFix.valid_sats} sats) | `;
                    } else if (result.satellites.length > 0) {
                      decoded += `🔍 Searching for position fix (tracking ${result.satellites.length} satellites) | `;
                    } else {
                      decoded += `⏳ Waiting for satellites | `;
                    }

                    // Jamming status (if present)
                    if (result.jamming.isJammed) {
                      // Show frequency only for CW tone jamming (not broadband noise)
                      const freqInfo = (result.jamming.jammingType === 'CW_TONE' || result.jamming.jammingType === 'SWEPT_CW')
                        ? `, Freq: ${(result.jamming.peakFrequencyHz / 1000).toFixed(1)}kHz`
                        : '';
                      decoded += `⚠️ JAMMING: ${result.jamming.jammingType} (J/S: ${result.jamming.jammingToSignalRatio.toFixed(1)}dB${freqInfo}) | `;
                    } else {
                      decoded += `✅ No jamming detected | `;
                    }

                    // Satellite info summary
                    if (result.satellites.length > 0) {
                      const avgCN0 = result.satellites.reduce((sum, s) => sum + s.cn0, 0) / result.satellites.length;
                      decoded += `Satellites: ${result.satellites.length} tracked, avg C/N0: ${avgCN0.toFixed(1)} dB-Hz`;
                    } else if (result.jamming.isJammed) {
                      decoded += 'No satellites visible (jammed)';
                    } else {
                      decoded += `Noise floor: ${result.jamming.noiseFloorDb.toFixed(1)}dB (relative)`;
                    }

                    const gnssMsg = {
                      decoded,
                      time: new Date(result.timestamp),
                      msg: result
                    };
                    setDecodedItems(prevDecodedItems => {
                      return [gnssMsg, ...prevDecodedItems];
                    });

                    // Update jamming status
                    if (result.jamming) {
                      setJammingStatus(result.jamming);
                    }

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

          // Create and connect WebSocket receiver
          const wsReceiver = new WebSocketReceiver(websocketUrl, sampleReceiver, () => {
            // Progress callback - not used in async streaming mode
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



    {/* GPS Recording Control - File-based approach */}
    {bridgeMode === 'gnss-sdr' && (
      <Box sx={{ marginBottom: '20px', padding: '20px', backgroundColor: 'rgba(156, 39, 176, 0.08)', borderRadius: '8px', border: '1px solid rgba(156, 39, 176, 0.3)' }}>
        <Typography variant="h6" sx={{ marginBottom: '15px', color: 'secondary.main' }}>
          🎙️ GPS Recording & Position Fix
        </Typography>

        <Typography variant="body2" sx={{ marginBottom: '15px', color: 'text.secondary' }}>
          Record GPS data to file, then process offline for reliable position fix.
          <br />
          This approach records 5 minutes of IQ data, then processes it with GNSS-SDR.
        </Typography>

        {/* Device Info - if any SDRplay device detected */}
        {deviceInfo && deviceInfo.devices && deviceInfo.devices.length > 0 && (
          <Box sx={{ marginBottom: '15px', padding: '12px', backgroundColor: 'rgba(33, 150, 243, 0.1)', borderRadius: '4px', border: '1px solid rgba(33, 150, 243, 0.3)' }}>
            <Typography variant="subtitle2" sx={{ marginBottom: '8px', fontWeight: 'bold', color: 'info.main' }}>
              📡 Detected Device
            </Typography>
            <Typography variant="body2">
              <strong>Model:</strong> {deviceInfo.devices[0].model} (Serial: {maskSerial(deviceInfo.devices[0].serial)})
              <br />

              {/* RSPduo and RSP2: Show port selection (RSPduo can be detected as RSP2) */}
              {(deviceInfo.devices[0].is_rspduo || deviceInfo.devices[0].model === 'RSP2') && (
                <Box sx={{ marginTop: '12px', marginBottom: '8px' }}>
                  <MuiFormControl component="fieldset">
                    <FormLabel component="legend" sx={{ fontSize: '0.875rem', marginBottom: '6px' }}>
                      <strong>🎯 Antenna Port Selection:</strong>
                    </FormLabel>
                    <RadioGroup
                      row
                      value={selectedPort}
                      onChange={(e) => setSelectedPort(parseInt(e.target.value))}
                    >
                      <FormControlLabel
                        value={1}
                        control={<Radio size="small" />}
                        label="Port 1 (Antenna A)"
                        disabled={isRecording || isProcessing}
                      />
                      <FormControlLabel
                        value={2}
                        control={<Radio size="small" />}
                        label="Port 2 (Antenna B)"
                        disabled={isRecording || isProcessing}
                      />
                    </RadioGroup>
                  </MuiFormControl>
                  {recordingConfig && (
                    <Typography variant="caption" color="success.main" display="block" sx={{ marginTop: '4px' }}>
                      ✓ Bias-T {recordingConfig.bias_tee}, Gain {recordingConfig.actual_gain} dB
                    </Typography>
                  )}
                </Box>
              )}

              {/* Other devices: Show settings info only */}
              {!deviceInfo.devices[0].is_rspduo && deviceInfo.devices[0].model !== 'RSP2' && recordingConfig && (
                <>
                  <strong>🎯 Settings:</strong> Bias-T {recordingConfig.bias_tee}, Gain {recordingConfig.actual_gain} dB
                  <br />
                  <Typography variant="caption" color="success.main">
                    ✓ Device configured for GPS reception
                  </Typography>
                </>
              )}
            </Typography>
          </Box>
        )}

        {/* Show info if no RSPduo or device detection failed */}
        {deviceInfo && (!deviceInfo.devices || deviceInfo.devices.length === 0) && recordingConfig && (
          <Box sx={{ marginBottom: '15px', padding: '12px', backgroundColor: isRecording ? 'rgba(33, 150, 243, 0.1)' : 'rgba(255, 152, 0, 0.1)', borderRadius: '4px', border: isRecording ? '1px solid rgba(33, 150, 243, 0.3)' : '1px solid rgba(255, 152, 0, 0.3)' }}>
            <Typography variant="body2" color={isRecording ? 'info.main' : 'warning.main'}>
              {isRecording ? 'ℹ️ Device in use (recording active)' : '⚠️ SDRplay device not detected (may be in use)'}
              <br />
              <Typography variant="caption" color="text.secondary">
                {isRecording
                  ? 'Device is currently recording GPS data. Detection unavailable during active recording.'
                  : `Configured for: RSPduo Tuner ${recordingConfig.tuner} with Bias-T ${recordingConfig.bias_tee}`
                }
              </Typography>
            </Typography>
          </Box>
        )}

        {/* Jamming/Spoofing Status Indicator */}
        {jammingStatus && (
          <Box sx={{
            marginBottom: '15px',
            padding: '12px',
            backgroundColor: jammingStatus.isJammed
              ? (jammingStatus.severity === 'SPOOFING_DETECTED' || jammingStatus.severity === 'SEVERE')
                ? 'rgba(211, 47, 47, 0.15)'
                : 'rgba(255, 152, 0, 0.15)'
              : 'rgba(76, 175, 80, 0.15)',
            borderRadius: '4px',
            border: jammingStatus.isJammed
              ? (jammingStatus.severity === 'SPOOFING_DETECTED' || jammingStatus.severity === 'SEVERE')
                ? '2px solid rgba(211, 47, 47, 0.5)'
                : '2px solid rgba(255, 152, 0, 0.5)'
              : '1px solid rgba(76, 175, 80, 0.3)'
          }}>
            <Typography variant="subtitle2" sx={{ marginBottom: '8px', fontWeight: 'bold' }}>
              {jammingStatus.isJammed ? '⚠️ GPS Interference Detected' : '✅ GPS Signal Status: Normal'}
            </Typography>
            <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px', fontSize: '0.875rem' }}>
              <Box>
                <strong>Status:</strong> {jammingStatus.isJammed ? 'JAMMED' : 'Clear'}
              </Box>
              <Box>
                <strong>Severity:</strong> {jammingStatus.severity || 'N/A'}
              </Box>
              <Box>
                <strong>Type:</strong> {jammingStatus.type || 'N/A'}
              </Box>
              <Box>
                <strong>Avg C/N0:</strong> {jammingStatus.avgCN0 ? jammingStatus.avgCN0.toFixed(1) : 'N/A'} dB-Hz
              </Box>
              {jammingStatus.cn0Variation !== undefined && (
                <Box>
                  <strong>C/N0 Variation:</strong> {jammingStatus.cn0Variation.toFixed(2)} dB
                </Box>
              )}
              {jammingStatus.dopplerVariation !== undefined && (
                <Box>
                  <strong>Doppler Var:</strong> {jammingStatus.dopplerVariation.toFixed(1)} Hz
                </Box>
              )}
              {jammingStatus.cn0Correlation !== undefined && (
                <Box>
                  <strong>C/N0 Correlation:</strong> {jammingStatus.cn0Correlation.toFixed(3)}
                </Box>
              )}
            </Box>
            {jammingStatus.isJammed && (
              <Typography variant="caption" sx={{ display: 'block', marginTop: '8px', fontStyle: 'italic', color: 'text.secondary' }}>
                {jammingStatus.type === 'BROADBAND_NOISE' && '📡 Likely RF jamming from external source (e.g., Kaliningrad region jammers)'}
                {jammingStatus.type === 'HIGH_CONFIDENCE_SPOOFING' && '🚨 High confidence GPS spoofing attack detected!'}
                {jammingStatus.type === 'POSSIBLE_SPOOFING' && '⚠️ Possible spoofing - abrupt signal changes detected'}
                {jammingStatus.type === 'SUSPECTED_SPOOFING_LOW_DOPPLER' && '⚠️ Suspected spoofing - constant Doppler indicates fixed-location attacker'}
                {jammingStatus.type === 'CW_TONE' && '📻 Continuous wave interference detected'}
              </Typography>
            )}
          </Box>
        )}

        {/* Configuration Info - Dynamic from server */}
        {recordingConfig ? (
          <Box sx={{ marginBottom: '15px', padding: '12px', backgroundColor: 'rgba(0, 0, 0, 0.15)', borderRadius: '4px', border: '1px solid rgba(156, 39, 176, 0.2)' }}>
            <Typography variant="subtitle2" sx={{ marginBottom: '8px', fontWeight: 'bold', color: 'secondary.main' }}>
              📋 Recording Configuration
            </Typography>
            <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px', fontSize: '0.875rem' }}>
              <Box>
                <strong>Frequency:</strong> {recordingConfig.frequency_mhz} MHz (GPS L1)
              </Box>
              <Box>
                <strong>Sample Rate:</strong> {recordingConfig.sample_rate_msps} MSPS
              </Box>
              <Box>
                <strong>Gain:</strong> {recordingConfig.actual_gain} dB ({recordingConfig.gain_reduction} dB reduction)
              </Box>
              <Box>
                <strong>Bandwidth:</strong> {recordingConfig.bandwidth_mhz} MHz
              </Box>
              <Box>
                <strong>Format:</strong> {recordingConfig.format}
              </Box>
              <Box>
                <strong>RSPduo Tuner:</strong> {recordingConfig.tuner} (Port {recordingConfig.tuner})
              </Box>
              <Box>
                <strong>Bias-T:</strong> {recordingConfig.bias_tee || 'DISABLED'}
              </Box>
              <Box>
                <strong>File Size:</strong> ~{recordingConfig.file_size_per_min_mb} MB/min
              </Box>
              <Box>
                <strong>Duration:</strong> {recordingConfig.duration_default / 60} minutes (default)
              </Box>
              <Box>
                <strong>Expected Size:</strong> ~{recordingConfig.expected_size_5min_gb} GB
              </Box>
            </Box>
          </Box>
        ) : (
          <Box sx={{ marginBottom: '15px', padding: '12px', backgroundColor: 'rgba(0, 0, 0, 0.15)', borderRadius: '4px', border: '1px solid rgba(156, 39, 176, 0.2)' }}>
            <Typography variant="body2" color="text.secondary">Loading configuration...</Typography>
          </Box>
        )}

        {/* Recording Controls */}
        <ButtonGroup variant="contained" sx={{ marginBottom: '10px' }}>
          <Button
            onClick={startRecording}
            disabled={isRecording || isProcessing}
            color="error"
            sx={{ textTransform: 'none' }}
          >
            ⏺ Start Recording (5 min)
          </Button>
          <Button
            onClick={stopRecording}
            disabled={!isRecording}
            sx={{ textTransform: 'none' }}
          >
            ⏹ Stop
          </Button>
          <Button
            onClick={processRecording}
            disabled={isRecording || isProcessing || !recordingFile}
            color="success"
            sx={{ textTransform: 'none' }}
            data-process-button
          >
            🔄 Process & Get Position
          </Button>
        </ButtonGroup>

        {/* Progress Display */}
        {(progressPhase === 'recording' || progressPhase === 'processing') && (
          <Box sx={{ marginTop: '15px', padding: '15px', backgroundColor: 'rgba(33, 150, 243, 0.1)', borderRadius: '4px', border: '2px solid rgba(33, 150, 243, 0.5)' }}>
            <Typography variant="subtitle2" sx={{ marginBottom: '10px', fontWeight: 'bold', color: 'info.main' }}>
              🔄 {progressPhase === 'recording' ? 'Recording in Progress' : 'Processing in Progress'}
            </Typography>
            <LinearProgress
              variant={progressPercent > 0 ? 'determinate' : 'indeterminate'}
              value={progressPercent}
              sx={{ marginBottom: '10px' }}
            />
            <Typography variant="body2" sx={{ color: 'text.secondary' }}>
              {progressMessage}
              {progressElapsed > 0 && ` (${Math.floor(progressElapsed)}s elapsed)`}
            </Typography>
            {recordingFile && (
              <Typography variant="caption" sx={{ display: 'block', marginTop: '5px', fontFamily: 'monospace', color: 'text.secondary' }}>
                File: {recordingFile}
              </Typography>
            )}
          </Box>
        )}

        {/* Spectrum Analysis Results */}
        {spectrumAnalysis && (
          <Box sx={{ marginTop: '20px', padding: '15px', backgroundColor: 'rgba(255, 152, 0, 0.1)', borderRadius: '4px', border: '1px solid rgba(255, 152, 0, 0.3)' }}>
            <Typography variant="subtitle2" sx={{ marginBottom: '15px', fontWeight: 'bold', color: 'warning.main' }}>
              📊 Spectrum Analysis - Jamming Detection
            </Typography>

            {/* Detection Summary */}
            <Box sx={{ marginBottom: '15px', padding: '10px', backgroundColor: 'rgba(0,0,0,0.05)', borderRadius: '4px' }}>
              {spectrumAnalysis.summary?.jamming_detected ? (
                <Typography variant="body2" sx={{ color: 'error.main', fontWeight: 'bold' }}>
                  ⚠️ JAMMING DETECTED: {spectrumAnalysis.summary.primary_threat.toUpperCase()}
                  <br />
                  <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                    Confidence: {(spectrumAnalysis.summary.max_confidence * 100).toFixed(1)}%
                  </Typography>
                </Typography>
              ) : (
                <Typography variant="body2" sx={{ color: 'success.main' }}>
                  ✓ No jamming detected (clean signal)
                </Typography>
              )}
            </Box>

            {/* Detection Details */}
            <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px', marginBottom: '15px' }}>
              {/* Sweep Jammer */}
              <Box sx={{ padding: '10px', backgroundColor: spectrumAnalysis.detections?.sweep?.detected ? 'rgba(244, 67, 54, 0.1)' : 'rgba(0,0,0,0.02)', borderRadius: '4px' }}>
                <Typography variant="caption" sx={{ fontWeight: 'bold', display: 'block' }}>
                  {spectrumAnalysis.detections?.sweep?.detected ? '⚠️ ' : '✓ '}
                  Sweep Jammer
                </Typography>
                <Typography variant="caption" sx={{ color: 'text.secondary', display: 'block' }}>
                  {spectrumAnalysis.detections?.sweep?.detected
                    ? Math.abs(spectrumAnalysis.detections.sweep.sweep_rate_hz_per_sec) > 1000
                      ? `Sweep rate: ${(spectrumAnalysis.detections.sweep.sweep_rate_hz_per_sec / 1e6).toFixed(2)} MHz/s`
                      : `Sweep rate: ${(spectrumAnalysis.detections.sweep.sweep_rate_hz_per_sec).toFixed(0)} Hz/s`
                    : 'Not detected'
                  }
                </Typography>
              </Box>

              {/* Pulse Jammer */}
              <Box sx={{ padding: '10px', backgroundColor: spectrumAnalysis.detections?.pulse?.detected ? 'rgba(244, 67, 54, 0.1)' : 'rgba(0,0,0,0.02)', borderRadius: '4px' }}>
                <Typography variant="caption" sx={{ fontWeight: 'bold', display: 'block' }}>
                  {spectrumAnalysis.detections?.pulse?.detected ? '⚠️ ' : '✓ '}
                  Pulse Jammer
                </Typography>
                <Typography variant="caption" sx={{ color: 'text.secondary', display: 'block' }}>
                  {spectrumAnalysis.detections?.pulse?.detected
                    ? `${spectrumAnalysis.detections.pulse.pulse_rate_hz.toFixed(1)} Hz, ${(spectrumAnalysis.detections.pulse.duty_cycle * 100).toFixed(1)}% duty`
                    : 'Not detected'
                  }
                </Typography>
              </Box>

              {/* Noise Jammer */}
              <Box sx={{ padding: '10px', backgroundColor: spectrumAnalysis.detections?.noise?.detected ? 'rgba(244, 67, 54, 0.1)' : 'rgba(0,0,0,0.02)', borderRadius: '4px' }}>
                <Typography variant="caption" sx={{ fontWeight: 'bold', display: 'block' }}>
                  {spectrumAnalysis.detections?.noise?.detected ? '⚠️ ' : '✓ '}
                  Noise Jammer
                </Typography>
                <Typography variant="caption" sx={{ color: 'text.secondary', display: 'block' }}>
                  {spectrumAnalysis.detections?.noise?.detected
                    ? `Floor: ${spectrumAnalysis.detections.noise.noise_floor_db.toFixed(1)} dBFS`
                    : 'Not detected'
                  }
                </Typography>
              </Box>

              {/* Meaconing */}
              <Box sx={{ padding: '10px', backgroundColor: spectrumAnalysis.detections?.meaconing?.detected ? 'rgba(244, 67, 54, 0.1)' : 'rgba(0,0,0,0.02)', borderRadius: '4px' }}>
                <Typography variant="caption" sx={{ fontWeight: 'bold', display: 'block' }}>
                  {spectrumAnalysis.detections?.meaconing?.detected ? '⚠️ ' : '✓ '}
                  Meaconing/Spoofing
                </Typography>
                <Typography variant="caption" sx={{ color: 'text.secondary', display: 'block' }}>
                  {spectrumAnalysis.detections?.meaconing?.detected
                    ? `${spectrumAnalysis.detections.meaconing.num_signals} suspicious signals`
                    : 'Not detected'
                  }
                </Typography>
              </Box>
            </Box>

            {/* Spectrum Visualization */}
            {spectrumImageUrl && (
              <Box sx={{ marginTop: '15px' }}>
                <Typography variant="caption" sx={{ display: 'block', marginBottom: '10px', color: 'text.secondary' }}>
                  Spectrogram (Time-Frequency Analysis)
                </Typography>
                <img
                  src={spectrumImageUrl}
                  alt="Spectrum Analysis"
                  style={{ width: '100%', maxWidth: '900px', border: '1px solid rgba(0,0,0,0.1)', borderRadius: '4px' }}
                  onError={(e) => {
                    console.log('Spectrum image failed to load');
                    e.currentTarget.style.display = 'none';
                  }}
                />
              </Box>
            )}
          </Box>
        )}

        {/* Status Message */}
        {!isRecording && !isProcessing && recordingFile && (
          <Typography variant="body2" sx={{ marginTop: '10px', color: 'success.main' }}>
            ✅ Recording ready: {recordingFile}
            <br />
            Click "Process & Get Position" to calculate location.
          </Typography>
        )}
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

        {/* Position Fix Display */}
        {decodedItems[0]?.msg?.positionFix && (
          <Box sx={{ marginTop: '15px', padding: '15px', border: '2px solid #4CAF50', borderRadius: '8px', backgroundColor: 'rgba(76, 175, 80, 0.05)' }}>
            <Typography variant="h6" sx={{ marginBottom: '10px', fontSize: '1em', color: '#4CAF50' }}>
              📍 Position Fix
            </Typography>
            <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
              <Typography variant="body2">
                <strong>Latitude:</strong> {decodedItems[0].msg.positionFix.latitude.toFixed(6)}° {decodedItems[0].msg.positionFix.latitude >= 0 ? 'N' : 'S'}
              </Typography>
              <Typography variant="body2">
                <strong>Longitude:</strong> {decodedItems[0].msg.positionFix.longitude.toFixed(6)}° {decodedItems[0].msg.positionFix.longitude >= 0 ? 'E' : 'W'}
              </Typography>
              <Typography variant="body2">
                <strong>Height:</strong> {decodedItems[0].msg.positionFix.height.toFixed(1)} m (above WGS84)
              </Typography>
              <Typography variant="body2">
                <strong>Satellites Used:</strong> {decodedItems[0].msg.positionFix.valid_sats}
              </Typography>
              <Typography variant="body2">
                <strong>HDOP:</strong> {decodedItems[0].msg.positionFix.hdop.toFixed(2)}
                {decodedItems[0].msg.positionFix.hdop < 2 ? ' (Excellent)' :
                 decodedItems[0].msg.positionFix.hdop < 5 ? ' (Good)' :
                 decodedItems[0].msg.positionFix.hdop < 10 ? ' (Moderate)' : ' (Poor)'}
              </Typography>
              <Typography variant="body2">
                <strong>VDOP:</strong> {decodedItems[0].msg.positionFix.vdop.toFixed(2)}
              </Typography>
              {decodedItems[0].msg.positionFix.velocity_east !== undefined && (
                <>
                  <Typography variant="body2">
                    <strong>Velocity:</strong> {Math.sqrt(
                      Math.pow(decodedItems[0].msg.positionFix.velocity_east, 2) +
                      Math.pow(decodedItems[0].msg.positionFix.velocity_north, 2)
                    ).toFixed(2)} m/s
                  </Typography>
                  <Typography variant="body2">
                    <strong>Course:</strong> {decodedItems[0].msg.positionFix.course_over_ground.toFixed(1)}°
                  </Typography>
                </>
              )}
              {decodedItems[0].msg.positionFix.utc_time && (
                <Typography variant="body2" sx={{ gridColumn: '1 / -1' }}>
                  <strong>UTC Time:</strong> {decodedItems[0].msg.positionFix.utc_time}
                </Typography>
              )}
              {decodedItems[0].msg.positionFix.geohash && (
                <Typography variant="body2" sx={{ gridColumn: '1 / -1' }}>
                  <strong>Geohash:</strong> <code>{decodedItems[0].msg.positionFix.geohash}</code>
                </Typography>
              )}
            </Box>
            <Typography variant="caption" sx={{ display: 'block', marginTop: '10px', color: 'text.secondary' }}>
              💡 Open in <a href={`https://www.google.com/maps?q=${decodedItems[0].msg.positionFix.latitude},${decodedItems[0].msg.positionFix.longitude}`} target="_blank" rel="noopener noreferrer" style={{ color: '#2196F3' }}>Google Maps</a>
            </Typography>
          </Box>
        )}

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
                  data: satelliteHistory.slice().reverse().map(p => p.avgCN0),
                  label: 'Avg C/N0 (dB-Hz)',
                  color: '#2196F3',
                  showMark: false
                }
              ]}
              xAxis={[{
                data: satelliteHistory.slice().reverse().map((_, i) => i),
                label: 'Time (recent →)'
              }]}
              yAxis={[{
                label: 'Satellites / C/N0 (dB-Hz)'
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
      {decodedItems.slice(0, 50).map((row, index) => (
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
