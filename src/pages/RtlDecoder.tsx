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
import MuiFormControl from '@mui/material/FormControl';
import LinearProgress from '@mui/material/LinearProgress';
import CircularProgress from '@mui/material/CircularProgress';

import { LineChart } from '@mui/x-charts/LineChart';

import MenuItem from '@mui/material/MenuItem';
import Select from '@mui/material/Select';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';
import MuiRadio from '@mui/material/Radio';
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

import { RTL2832U_Provider } from "../device/rtlsdr/rtl2832u.ts";
import { Radio } from '../device/radio.ts';
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

function RtlDecoder() {
  const [radio, setRadio] = useState<Radio>();
  const [protocol, setProtocol] = useState<Protocol>(Protocol.ADSB);
  const [frequency, setFrequency] = useState<number>(1090);
  const [frequencyMag, setFrequencyMag] = useState<number>(1000000);
  const [biasTEnabled, setBiasTEnabled] = useState<boolean>(false);

  // Bridge mode selection
  const [bridgeMode, setBridgeMode] = useState<'rtlsdr' | 'gnss-sdr'>('gnss-sdr');

  // Input source selection
  const [inputSource, setInputSource] = useState<'USB' | 'WebSocket'>('USB');
  const defaultWebSocketUrl = bridgeMode === 'gnss-sdr' ? 'ws://localhost:8766' : 'ws://localhost:8765';
  const [websocketUrl, setWebsocketUrl] = useState<string>(defaultWebSocketUrl);
  const [websocketReceiver, setWebsocketReceiver] = useState<WebSocketReceiver | null>(null);

  // Interference mitigation filter state
  const [filterEnabled, setFilterEnabled] = useState<boolean>(false);
  const [notchFrequency, setNotchFrequency] = useState<number>(0); // Auto-detect
  const [filterReceiver, setFilterReceiver] = useState<FilteringSampleReceiver | null>(null);

  const [decodedItems, setDecodedItems] = useState<any>([]);

  const [powerLevels, setPowerLevels] = useState([]);

  // GPS Recording state (RTL-SDR)
  const [isRecording, setIsRecording] = useState<boolean>(false);
  const [isProcessing, setIsProcessing] = useState<boolean>(false);
  const [recordingFile, setRecordingFile] = useState<string>('');
  const [recordingDuration, setRecordingDuration] = useState<number>(60); // Default 60 seconds
  const [progressPhase, setProgressPhase] = useState<string>('');
  const [progressPercent, setProgressPercent] = useState<number>(0);
  const [progressMessage, setProgressMessage] = useState<string>('');
  const [recordingConfig, setRecordingConfig] = useState<any>(null);
  const [deviceInfo, setDeviceInfo] = useState<any>(null);

  // Spectrum analysis results
  const [spectrumAnalysis, setSpectrumAnalysis] = useState<any>(null);
  const [spectrumImageUrl, setSpectrumImageUrl] = useState<string | null>(null);
  const [waitingForSpectrum, setWaitingForSpectrum] = useState<boolean>(false);

  // Jamming status
  const [jammingStatus, setJammingStatus] = useState<any>(null);

  // Decoder selection (GNSS-SDR vs Gypsum)
  const [selectedDecoder, setSelectedDecoder] = useState<'gnss-sdr' | 'gypsum'>('gnss-sdr');

  const pointsBatch = 10000;

  const xPoints: Array<number> = [];
  for (let i = 0; i < pointsBatch; i++) {
    xPoints.push(i);
  }

  const ismDemodulator = new IsmDemodulator();
  const [gnssDemodulator] = useState(() => new GNSSDemodulator());

  // Fetch RTL-SDR GPS recording configuration on mount
  React.useEffect(() => {
    const fetchConfig = async () => {
      try {
        const response = await fetch('http://localhost:3001/gnss/config');
        if (response.ok) {
          const config = await response.json();
          setRecordingConfig(config);
        }
      } catch (error) {
        console.error('Failed to fetch RTL-SDR recording config:', error);
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
        console.error('Failed to fetch RTL-SDR device info:', error);
      }
    };

    fetchConfig();
    fetchDeviceInfo();
  }, []);

  // Update WebSocket URL when bridge mode changes
  React.useEffect(() => {
    if (!websocketReceiver?.isConnected()) {
      const newUrl = bridgeMode === 'gnss-sdr' ? 'ws://localhost:8766' : 'ws://localhost:8765';
      setWebsocketUrl(newUrl);
    }
  }, [bridgeMode, websocketReceiver]);

  // RTL-SDR GPS Recording control functions
  const startRecording = async () => {
    try {
      setIsRecording(true);
      setProgressPhase('recording');
      setProgressPercent(0);
      setProgressMessage('Starting RTL-SDR GPS recording...');

      // Reset spectrum analysis state
      setSpectrumAnalysis(null);
      setSpectrumImageUrl(null);
      setWaitingForSpectrum(false);

      const response = await fetch('http://localhost:3001/gnss/start-recording', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          duration: recordingDuration,  // Use configured duration
          device_type: 'rtlsdr',  // Explicitly use RTL-SDR device
          decoder: selectedDecoder  // Pass decoder selection for sample rate adjustment
        })
      });

      if (!response.ok) throw new Error('Failed to start RTL-SDR recording');
      const data = await response.json();
      setRecordingFile(data.filename || '');
      const durationMinutes = Math.floor(recordingDuration / 60);
      const durationSeconds = recordingDuration % 60;
      const durationText = durationMinutes > 0
        ? `${durationMinutes}m ${durationSeconds}s`
        : `${durationSeconds}s`;
      setProgressMessage(`Recording GPS data with RTL-SDR (${durationText})...`);

      // Auto-stop and process after recording duration
      setTimeout(async () => {
        setIsRecording(false);
        setProgressPhase('');
        setProgressMessage('✅ Recording complete! Starting processing...');

        setTimeout(() => {
          document.querySelector('[data-process-button]')?.click();
        }, 2000);
      }, (recordingDuration + 5) * 1000); // Duration + 5 seconds buffer
    } catch (error) {
      console.error('RTL-SDR recording error:', error);
      setIsRecording(false);
      setProgressMessage(`Error: ${error}`);
      alert(`❌ Failed to start RTL-SDR recording!\n\n${error}\n\nMake sure RTL-SDR is connected and not in use by another application.`);
    }
  };

  const stopRecording = async () => {
    try {
      await fetch('http://localhost:3001/gnss/stop-recording', { method: 'POST' });
      setIsRecording(false);
      setProgressPhase('');
      setProgressMessage('Recording stopped. Starting processing...');

      setTimeout(() => {
        document.querySelector('[data-process-button]')?.click();
      }, 2000);
    } catch (error) {
      console.error('Stop RTL-SDR recording error:', error);
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
      const decoderName = selectedDecoder === 'gnss-sdr' ? 'GNSS-SDR' : 'Gypsum';
      setProgressMessage(`Processing GPS data with ${decoderName}...`);
      setWaitingForSpectrum(true);  // Show waiting for spectrum message

      const response = await fetch('http://localhost:3001/gnss/process-recording', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          filename: recordingFile,
          decoder: selectedDecoder  // Pass decoder selection to backend
        })
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));

        // Check if another processing is in progress
        if (errorData.error?.includes('Processing already in progress')) {
          setProgressMessage('⏳ Waiting for previous processing to complete...');

          // Poll until previous processing completes, then retry
          const waitForProcessing = setInterval(async () => {
            try {
              const statusResponse = await fetch('http://localhost:3001/gnss/status');
              const status = await statusResponse.json();

              // Check if processing finished
              if (!status.processing.active || status.processing.error) {
                clearInterval(waitForProcessing);

                // Wait 2 seconds for cleanup, then retry
                setTimeout(() => {
                  console.log('Previous processing finished, retrying...');
                  processRecording();
                }, 2000);
              }
            } catch (err) {
              console.error('Status check error:', err);
            }
          }, 5000);

          return; // Exit without throwing error
        }

        throw new Error(errorData.error || 'Failed to start processing');
      }

      setProgressMessage(`${decoderName} processing in progress (${selectedDecoder === 'gypsum' ? '1-2 minutes' : '5-10 minutes'})...`);

      // Poll for completion and spectrum results
      const pollProcessing = setInterval(async () => {
        try {
          const statusResponse = await fetch('http://localhost:3001/gnss/status');
          if (statusResponse.ok) {
            const status = await statusResponse.json();

            // Check for spectrum analysis results
            if (recordingFile && !spectrumAnalysis) {
              const spectrumJsonUrl = `http://localhost:3001/gnss/recordings/${recordingFile.replace('.dat', '_spectrum_analysis.json')}`;
              fetch(spectrumJsonUrl)
                .then(res => res.ok ? res.json() : null)
                .then(data => {
                  if (data) {
                    console.log('Spectrum analysis loaded:', data);
                    setSpectrumAnalysis(data);
                    setWaitingForSpectrum(false);

                    // Load spectrum image
                    const imageUrl = `http://localhost:3001/gnss/recordings/${recordingFile.replace('.dat', '_spectrum.png')}?t=${Date.now()}`;
                    setSpectrumImageUrl(imageUrl);
                    console.log('Spectrum image URL set:', imageUrl);

                    // Clear processing indicators since spectrum is complete
                    setIsProcessing(false);
                    setProgressPhase('');
                    setProgressMessage('✅ Processing complete!');
                  }
                })
                .catch(err => console.log('Spectrum not ready yet:', err));
            }

            if (status.processing && status.processing.complete) {
              clearInterval(pollProcessing);
              setIsProcessing(false);
              setProgressPhase('');
              setProgressMessage('✅ Processing complete!');
            }
          }
        } catch (err) {
          console.error('Processing status poll error:', err);
        }
      }, 5000);

      // Timeout after 15 minutes
      setTimeout(() => {
        clearInterval(pollProcessing);
        setIsProcessing(false);
        setProgressPhase('');
      }, 900000);
    } catch (error) {
      console.error('Processing error:', error);
      setIsProcessing(false);
      setProgressPhase('');
      setProgressMessage('');
      setWaitingForSpectrum(false);

      // Show detailed error message with retry instructions
      const errorMsg = error instanceof Error ? error.message : String(error);
      alert(`❌ Failed to start GNSS-SDR processing!\n\nError: ${errorMsg}\n\nFile: ${recordingFile}\n\nPlease try clicking "🔄 Process & Get Position" again to retry.`);
    }
  };

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
    {/* Bridge Mode Selector */}
    <Box sx={{ marginBottom: '20px', marginTop: '20px' }}>
      <MuiFormControl>
        <FormLabel id="bridge-mode-label">Signal Processing Mode</FormLabel>
        <RadioGroup
          row
          aria-labelledby="bridge-mode-label"
          name="bridge-mode-group"
          value={bridgeMode}
          onChange={(event) => setBridgeMode(event.target.value as 'rtlsdr' | 'gnss-sdr')}
        >
          <FormControlLabel
            value="rtlsdr"
            control={<MuiRadio />}
            label="Browser Processing (Raw IQ)"
            disabled={websocketReceiver?.isConnected() || radio?.isPlaying()}
          />
          <FormControlLabel
            value="gnss-sdr"
            control={<MuiRadio />}
            label="Professional Mode (GNSS-SDR)"
            disabled={websocketReceiver?.isConnected() || radio?.isPlaying()}
          />
        </RadioGroup>
        <Typography variant="caption" color="text.secondary" sx={{ marginTop: '5px' }}>
          {bridgeMode === 'rtlsdr'
            ? '⚠️ Browser Processing: Simplified algorithms, high bandwidth, real-time correlation'
            : '✅ Professional: Uses GNSS-SDR for accurate GPS tracking, C/N0 measurements, and jamming detection'
          }
        </Typography>
      </MuiFormControl>
    </Box>

    {/* Browser Processing Controls - Only show in rtlsdr mode */}
    {bridgeMode === 'rtlsdr' && (
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
          onChange={(_, val) => setFrequency(val)}
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
  )}

  {/* RTL-SDR GPS Recording & Position Fix - Professional Mode Only */}
  {bridgeMode === 'gnss-sdr' && (
    <Box sx={{ marginBottom: '20px', marginTop: '20px', padding: '20px', backgroundColor: 'rgba(156, 39, 176, 0.08)', borderRadius: '8px', border: '1px solid rgba(156, 39, 176, 0.3)' }}>
      <Typography variant="h6" sx={{ marginBottom: '15px', color: 'secondary.main' }}>
        🎙️ RTL-SDR GPS Recording & Position Fix
      </Typography>

      <Typography variant="body2" sx={{ marginBottom: '15px', color: 'text.secondary' }}>
        Record GPS L1 signals with RTL-SDR (8-bit IQ), then process with GNSS-SDR for position fix.
        <br />
        RTL-SDR provides 80% of professional capability at $30-40 (vs $200-300 SDRplay).
      </Typography>

      {/* Device Info */}
      {deviceInfo && deviceInfo.detected && (
        <Box sx={{ marginBottom: '15px', padding: '12px', backgroundColor: 'rgba(33, 150, 243, 0.1)', borderRadius: '4px', border: '1px solid rgba(33, 150, 243, 0.3)' }}>
          <Typography variant="subtitle2" sx={{ marginBottom: '8px', fontWeight: 'bold', color: 'info.main' }}>
            📡 RTL-SDR Device Detected
          </Typography>
          <Typography variant="body2">
            <strong>Model:</strong> {deviceInfo.model || 'RTL2832U'}
            <br />
            <strong>Tuner:</strong> {deviceInfo.tuner || 'R820T2'}
            <br />
            <strong>Bias-T:</strong> {deviceInfo.has_bias_t ? 'Available' : 'Not available'}
          </Typography>
        </Box>
      )}

      {/* Recording Configuration */}
      {recordingConfig ? (
        <Box sx={{ marginBottom: '15px', padding: '12px', backgroundColor: 'rgba(0, 0, 0, 0.15)', borderRadius: '4px', border: '1px solid rgba(156, 39, 176, 0.2)' }}>
          <Typography variant="subtitle2" sx={{ marginBottom: '8px', fontWeight: 'bold', color: 'secondary.main' }}>
            📋 Recording Configuration
          </Typography>
          <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px', fontSize: '0.875rem' }}>
            <Box><strong>Frequency:</strong> {recordingConfig.frequency_mhz || 1575.42} MHz (GPS L1)</Box>
            <Box><strong>Sample Rate:</strong> {recordingConfig.sample_rate_msps || 2.048} MSPS</Box>
            <Box><strong>Format:</strong> 8-bit IQ (RTL-SDR native)</Box>
            <Box><strong>Bandwidth:</strong> ~{recordingConfig.bandwidth_mhz || 2} MHz</Box>
            <Box><strong>Duration:</strong> 1 minute (default)</Box>
            <Box><strong>File Size:</strong> ~{recordingConfig.file_size_mb || 1230} MB</Box>
            <Box><strong>Bias-T:</strong> {recordingConfig.bias_tee || 'ENABLED'}</Box>
            <Box><strong>Active Antenna:</strong> Required (powered)</Box>
          </Box>
        </Box>
      ) : (
        <Box sx={{ marginBottom: '15px', padding: '12px', backgroundColor: 'rgba(0, 0, 0, 0.15)', borderRadius: '4px', border: '1px solid rgba(156, 39, 176, 0.2)' }}>
          <Typography variant="body2" color="text.secondary">Loading RTL-SDR configuration...</Typography>
        </Box>
      )}

      {/* Recording Duration Configuration */}
      <Box sx={{ marginBottom: '15px' }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '8px' }}>
          <Typography variant="body2" sx={{ fontWeight: 'bold' }}>
            Recording Duration:
          </Typography>
          <TextField
            type="number"
            value={recordingDuration}
            onChange={(e) => setRecordingDuration(Math.max(5, Math.min(600, parseInt(e.target.value) || 60)))}
            disabled={isRecording || isProcessing}
            size="small"
            sx={{ width: '100px' }}
            inputProps={{ min: 5, max: 600, step: 5 }}
          />
          <Typography variant="body2" color="text.secondary">
            seconds (~{Math.round(recordingDuration * 15.6)} MB)
          </Typography>
        </Box>
        <Box sx={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
          <Typography variant="caption" color="text.secondary" sx={{ lineHeight: '32px' }}>
            Quick select:
          </Typography>
          {[30, 60, 120, 300].map((duration) => (
            <Button
              key={duration}
              size="small"
              variant="outlined"
              onClick={() => setRecordingDuration(duration)}
              disabled={isRecording || isProcessing}
              sx={{
                textTransform: 'none',
                minWidth: '60px',
                backgroundColor: recordingDuration === duration ? 'rgba(156, 39, 176, 0.1)' : 'transparent'
              }}
            >
              {duration < 60 ? `${duration}s` : `${duration / 60}m`}
            </Button>
          ))}
        </Box>
      </Box>

      {/* Decoder Selection */}
      <Box sx={{ marginBottom: '15px' }}>
        <Typography variant="body2" sx={{ fontWeight: 'bold', marginBottom: '8px' }}>
          GPS Decoder:
        </Typography>
        <MuiFormControl fullWidth size="small">
          <Select
            value={selectedDecoder}
            onChange={(event) => setSelectedDecoder(event.target.value as 'gnss-sdr' | 'gypsum')}
            disabled={isRecording || isProcessing}
          >
            <MenuItem value="gnss-sdr">
              <Box>
                <Typography variant="body2" sx={{ fontWeight: 'bold' }}>
                  GNSS-SDR (Professional)
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  C++ implementation, high accuracy, full NMEA/KML/GPX output
                </Typography>
              </Box>
            </MenuItem>
            <MenuItem value="gypsum">
              <Box>
                <Typography variant="body2" sx={{ fontWeight: 'bold' }}>
                  Gypsum (Python-based)
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  Faster processing, educational, minimal dependencies
                </Typography>
              </Box>
            </MenuItem>
          </Select>
        </MuiFormControl>
        <Typography variant="caption" color="text.secondary" display="block" sx={{ marginTop: '5px' }}>
          {selectedDecoder === 'gnss-sdr'
            ? '✅ Best for: Production use, research, accurate position fixes'
            : '🚀 Best for: Quick tests, learning GPS signal processing, lighter system load'
          }
        </Typography>
      </Box>

      {/* Recording Controls */}
      <ButtonGroup variant="contained" sx={{ marginBottom: '10px' }}>
        <Button
          onClick={startRecording}
          disabled={isRecording || isProcessing}
          color="error"
          sx={{ textTransform: 'none' }}
        >
          ⏺ Start Recording ({recordingDuration < 60 ? `${recordingDuration}s` : `${Math.floor(recordingDuration / 60)}m ${recordingDuration % 60}s`})
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
            🔄 {progressPhase === 'recording' ? 'RTL-SDR Recording' : 'GNSS-SDR Processing'}
          </Typography>
          <LinearProgress
            variant={progressPercent > 0 ? 'determinate' : 'indeterminate'}
            value={progressPercent}
            sx={{ marginBottom: '10px' }}
          />
          <Typography variant="body2" sx={{ color: 'text.secondary' }}>
            {progressMessage}
          </Typography>
          {recordingFile && (
            <Typography variant="caption" sx={{ display: 'block', marginTop: '5px', fontFamily: 'monospace', color: 'text.secondary' }}>
              File: {recordingFile}
            </Typography>
          )}
        </Box>
      )}

      {/* Waiting for Spectrum */}
      {waitingForSpectrum && !spectrumImageUrl && (
        <Box sx={{ marginTop: '15px', padding: '15px', backgroundColor: 'rgba(255, 165, 0, 0.1)', borderRadius: '4px', border: '1px solid rgba(255, 165, 0, 0.3)' }}>
          <Box sx={{ display: 'flex', alignItems: 'center' }}>
            <CircularProgress size={30} sx={{ color: 'orange', marginRight: '15px' }} />
            <Box>
              <Typography variant="body2" sx={{ fontWeight: 'bold', color: 'warning.main' }}>
                Generating Spectrum Analysis...
              </Typography>
              <Typography variant="caption" color="text.secondary">
                This may take up to 10 minutes. Please wait...
              </Typography>
            </Box>
          </Box>
        </Box>
      )}

      {/* Spectrum Image */}
      {spectrumImageUrl && (
        <Box sx={{ marginTop: '15px' }}>
          <Typography variant="subtitle2" sx={{ marginBottom: '10px', fontWeight: 'bold' }}>
            📊 GPS L1 Spectrum (Jamming Detection)
          </Typography>
          <img
            src={spectrumImageUrl}
            alt="GPS Spectrum"
            style={{ width: '100%', maxWidth: '1000px', borderRadius: '4px', border: '1px solid rgba(156, 39, 176, 0.3)' }}
            onLoad={() => console.log('RTL-SDR spectrum image loaded')}
            onError={(e) => console.error('RTL-SDR spectrum image failed to load:', e)}
          />
          <Typography variant="caption" color="text.secondary" display="block" sx={{ marginTop: '5px' }}>
            Horizontal lines = Jamming bursts | Vertical lines = GPS satellites (Doppler-shifted)
          </Typography>
        </Box>
      )}

      {/* Spectrum Analysis Results */}
      {spectrumAnalysis && (
        <Box sx={{ marginTop: '15px', padding: '15px', backgroundColor: 'rgba(156, 39, 176, 0.05)', borderRadius: '4px', border: '1px solid rgba(156, 39, 176, 0.3)' }}>
          <Typography variant="subtitle2" sx={{ marginBottom: '10px', fontWeight: 'bold' }}>
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
                  ? `Rate: ${spectrumAnalysis.detections.pulse.pulse_rate_hz.toFixed(1)} Hz, Duty: ${(spectrumAnalysis.detections.pulse.duty_cycle * 100).toFixed(1)}%`
                  : 'Not detected'
                }
              </Typography>
            </Box>

            {/* Broadband Noise */}
            <Box sx={{ padding: '10px', backgroundColor: spectrumAnalysis.detections?.noise?.detected ? 'rgba(244, 67, 54, 0.1)' : 'rgba(0,0,0,0.02)', borderRadius: '4px' }}>
              <Typography variant="caption" sx={{ fontWeight: 'bold', display: 'block' }}>
                {spectrumAnalysis.detections?.noise?.detected ? '⚠️ ' : '✓ '}
                Broadband Noise
              </Typography>
              <Typography variant="caption" sx={{ color: 'text.secondary', display: 'block' }}>
                {spectrumAnalysis.detections?.noise?.detected
                  ? `Floor: ${spectrumAnalysis.detections.noise.noise_floor_db.toFixed(1)} dB, BW: ${(spectrumAnalysis.detections.noise.bandwidth_hz / 1e6).toFixed(2)} MHz`
                  : 'Not detected'
                }
              </Typography>
            </Box>

            {/* Narrowband CW */}
            <Box sx={{ padding: '10px', backgroundColor: spectrumAnalysis.detections?.narrowband?.detected ? 'rgba(244, 67, 54, 0.1)' : 'rgba(0,0,0,0.02)', borderRadius: '4px' }}>
              <Typography variant="caption" sx={{ fontWeight: 'bold', display: 'block' }}>
                {spectrumAnalysis.detections?.narrowband?.detected ? '⚠️ ' : '✓ '}
                Narrowband CW
              </Typography>
              <Typography variant="caption" sx={{ color: 'text.secondary', display: 'block' }}>
                {spectrumAnalysis.detections?.narrowband?.detected
                  ? `${spectrumAnalysis.detections.narrowband.num_signals} signal(s) detected`
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
                  ? `${spectrumAnalysis.detections.meaconing.num_signals} suspicious signal(s)`
                  : 'Not detected'
                }
              </Typography>
            </Box>
          </Box>

          {/* Location Info */}
          {spectrumAnalysis.analysis?.location && (
            <Box sx={{ padding: '10px', backgroundColor: 'rgba(0,0,0,0.02)', borderRadius: '4px' }}>
              <Typography variant="caption" sx={{ color: 'text.secondary', display: 'block' }}>
                <strong>Recording Location:</strong> {spectrumAnalysis.analysis.location}
              </Typography>
            </Box>
          )}
        </Box>
      )}

      {/* Position Fix Display */}
      {decodedItems[0]?.msg?.positionFix && (
        <Box sx={{ marginTop: '15px', padding: '15px', border: '2px solid #4CAF50', borderRadius: '8px', backgroundColor: 'rgba(76, 175, 80, 0.05)' }}>
          <Typography variant="h6" sx={{ marginBottom: '10px', fontSize: '1em', color: '#4CAF50' }}>
            📍 Position Fix (RTL-SDR + GNSS-SDR)
          </Typography>
          <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
            <Box>
              <strong>Latitude:</strong> {decodedItems[0].msg.positionFix.lat.toFixed(6)}°
            </Box>
            <Box>
              <strong>Longitude:</strong> {decodedItems[0].msg.positionFix.lon.toFixed(6)}°
            </Box>
            <Box>
              <strong>Altitude:</strong> {decodedItems[0].msg.positionFix.alt.toFixed(1)} m
            </Box>
            <Box>
              <strong>Accuracy:</strong> {decodedItems[0].msg.positionFix.accuracy ? decodedItems[0].msg.positionFix.accuracy.toFixed(1) : 'N/A'} m
            </Box>
            <Box>
              <strong>Satellites:</strong> {decodedItems[0].msg.positionFix.numSatellites || 'N/A'}
            </Box>
            <Box>
              <strong>Fix Type:</strong> {decodedItems[0].msg.positionFix.fixType || '3D'}
            </Box>
          </Box>
        </Box>
      )}
    </Box>
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
</Container>
);
}

export default RtlDecoder;
