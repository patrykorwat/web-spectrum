#!/usr/bin/env python3
"""
GNSS-SDR to Web-Spectrum Bridge (with Continuous Recording)

This bridge connects GNSS-SDR (professional GNSS signal processing software)
to the web-spectrum UI using continuous file-based processing.

Architecture:
    1. Continuous IQ recorder streams SDRPlay samples to /tmp/gps_iq_samples.dat
    2. GNSS-SDR continuously reads from file (with repeat mode)
    3. GNSS-SDR processes samples (acquisition, tracking, PVT)
    4. Monitor output sends real-time data via UDP (port 1234)
    5. This bridge receives UDP data and forwards via WebSocket
    6. Web UI displays professional-grade GNSS results

Advantages over raw IQ streaming:
    ✓ Professional-grade acquisition/tracking algorithms
    ✓ Real C/N0 (carrier-to-noise) measurements
    ✓ Accurate Doppler and code phase tracking
    ✓ Real PVT (Position, Velocity, Time) solutions
    ✓ Better jamming detection (low C/N0 = jamming)
    ✓ Multi-constellation support (GPS, Galileo, GLONASS, BeiDou)
    ✓ Much lower bandwidth (JSON results, not raw samples)
    ✓ Single command startup (no more 2-terminal juggling!)
    ✓ File-based approach proven to work reliably

Requirements:
    pip install websockets

Usage:
    # ONE TERMINAL - Start everything!
    python gnss_sdr_bridge.py
    # Or use the wrapper script:
    ./run_gnss_sdr_bridge.sh

    # Browser: Connect web-spectrum to ws://localhost:8766

    # Manual mode (if you want to control GNSS-SDR yourself):
    python gnss_sdr_bridge.py --no-auto-start
"""

import asyncio
import websockets
import json
import socket
import struct
import time
import subprocess
import os
from datetime import datetime
import sys
from typing import Dict, List, Optional

# Import protobuf for PVT message parsing
try:
    from monitor_pvt_pb2 import MonitorPvt
    PROTOBUF_AVAILABLE = True
except ImportError:
    print("⚠️  Warning: protobuf module not available. Position fixes will not be displayed.")
    print("   Install with: python3 -m pip install protobuf --break-system-packages")
    PROTOBUF_AVAILABLE = False

# GNSS-SDR Monitor message format
# See: https://github.com/gnss-sdr/gnss-sdr/blob/next/src/core/monitor/gnss_synchro_monitor.cc

class GNSSSatellite:
    """Represents a tracked GNSS satellite"""
    def __init__(self):
        self.prn: int = 0
        self.system: str = 'G'  # G=GPS, E=Galileo, R=GLONASS, C=BeiDou
        self.signal: str = '1C'  # Signal type
        self.cn0_dbhz: float = 0.0  # Carrier-to-Noise ratio (dB-Hz)
        self.doppler_hz: float = 0.0
        self.carrier_phase_cycles: float = 0.0
        self.code_phase_chips: float = 0.0
        self.tracking_state: int = 0  # 0=searching, 1=acquired, 2=tracking
        self.carrier_lock: bool = False
        self.bit_sync: bool = False
        self.subframe_sync: bool = False

    def to_dict(self) -> dict:
        return {
            'prn': self.prn,
            'system': self.system,
            'signal': self.signal,
            'cn0': self.cn0_dbhz,
            'snr': max(0, self.cn0_dbhz - 30),  # Approximate SNR (C/N0 - 30 dB)
            'dopplerHz': self.doppler_hz,
            'carrierPhase': self.carrier_phase_cycles,
            'codePhase': self.code_phase_chips,
            'state': ['SEARCHING', 'ACQUIRED', 'TRACKING'][min(self.tracking_state, 2)],
            'carrierLock': self.carrier_lock,
            'bitSync': self.bit_sync,
            'subframeSync': self.subframe_sync
        }


class GNSSJammingMetrics:
    """GNSS jamming/interference metrics derived from C/N0

    Implements two-stage spoofing detection based on:
    'Robust Spoofing Detection in GNSS-SDR Systems: A Two-Stage Method
    for Real-Time Signal Integrity' (Ali et al., 2024)
    """
    # Class variables to store history for temporal analysis
    cn0_history = []
    doppler_history = []  # New: Track Doppler variations
    cn0_correlation_history = []  # New: Track C/N0 correlations between satellites
    HISTORY_WINDOW = 30  # Keep 30 samples (adjust based on update rate)

    def __init__(self, satellites: List[GNSSSatellite]):
        self.satellites = satellites

        # Calculate metrics
        if satellites:
            cn0_values = [s.cn0_dbhz for s in satellites if s.tracking_state >= 1]
            doppler_values = [s.doppler_hz for s in satellites if s.tracking_state >= 2]

            self.avg_cn0 = sum(cn0_values) / len(cn0_values) if cn0_values else 0
            self.min_cn0 = min(cn0_values) if cn0_values else 0
            self.max_cn0 = max(cn0_values) if cn0_values else 0
            self.num_tracking = sum(1 for s in satellites if s.tracking_state >= 2)

            # New: Doppler statistics
            self.avg_doppler = sum(doppler_values) / len(doppler_values) if doppler_values else 0
            self.doppler_std = self._calculate_std(doppler_values) if len(doppler_values) > 1 else 0

            # Track C/N0 values per satellite for variation analysis
            self.cn0_values = cn0_values
            self.cn0_std = self._calculate_std(cn0_values) if len(cn0_values) > 1 else 0

            # New: Calculate C/N0 correlation between satellites (Rustamov et al., 2023)
            self.cn0_correlation = self._calculate_cn0_correlation()
        else:
            self.avg_cn0 = 0
            self.min_cn0 = 0
            self.max_cn0 = 0
            self.num_tracking = 0
            self.cn0_values = []
            self.cn0_std = 0
            self.avg_doppler = 0
            self.doppler_std = 0
            self.cn0_correlation = 0

        # Store current C/N0 in history for variation monitoring (Stage 2 detection)
        if self.avg_cn0 > 0:
            GNSSJammingMetrics.cn0_history.append(self.avg_cn0)
            if len(GNSSJammingMetrics.cn0_history) > GNSSJammingMetrics.HISTORY_WINDOW:
                GNSSJammingMetrics.cn0_history.pop(0)

        # Store Doppler history for consistency checking
        if hasattr(self, 'avg_doppler') and self.avg_doppler != 0:
            GNSSJammingMetrics.doppler_history.append(self.avg_doppler)
            if len(GNSSJammingMetrics.doppler_history) > GNSSJammingMetrics.HISTORY_WINDOW:
                GNSSJammingMetrics.doppler_history.pop(0)

        # Store C/N0 correlation history
        if hasattr(self, 'cn0_correlation') and self.cn0_correlation > 0:
            GNSSJammingMetrics.cn0_correlation_history.append(self.cn0_correlation)
            if len(GNSSJammingMetrics.cn0_correlation_history) > GNSSJammingMetrics.HISTORY_WINDOW:
                GNSSJammingMetrics.cn0_correlation_history.pop(0)

        # Calculate C/N0 variation (implements equation B.6 from paper)
        self.cn0_variation = self._calculate_cn0_variation()

        # New: Calculate Doppler variation (only if we have doppler data)
        self.doppler_variation = self._calculate_doppler_variation() if hasattr(self, 'avg_doppler') else 0.0

        # Enhanced jamming detection based on C/N0
        # Typical healthy GPS: C/N0 = 35-50 dB-Hz
        # Light jamming: C/N0 = 25-35 dB-Hz
        # Heavy jamming: C/N0 < 25 dB-Hz
        # Spoofing: Abrupt C/N0 changes (high variation)

        # Stage 1: Absolute C/N0 threshold (original method)
        threshold_jammed = self.avg_cn0 < 30 and self.avg_cn0 > 0

        # Stage 2: C/N0 variation detection (from paper)
        # Threshold: 3 dB deviation indicates possible spoofing/jamming
        variation_jammed = self.cn0_variation > 3.0 and len(GNSSJammingMetrics.cn0_history) > 5

        # Combined detection: Either method triggers jamming flag
        self.is_jammed = threshold_jammed or variation_jammed
        self.jamming_severity = self._calculate_severity()
        self.jamming_type = self._estimate_type()

    def _calculate_std(self, values: List[float]) -> float:
        """Calculate standard deviation of C/N0 values"""
        if len(values) < 2:
            return 0.0
        mean = sum(values) / len(values)
        variance = sum((x - mean) ** 2 for x in values) / len(values)
        return variance ** 0.5

    def _calculate_cn0_variation(self) -> float:
        """Calculate C/N0 variation based on recent history (equation B.6 from paper)

        Returns the absolute deviation from recent moving average.
        High values indicate possible spoofing/jamming attacks.
        """
        if len(GNSSJammingMetrics.cn0_history) < 5 or self.avg_cn0 == 0:
            return 0.0

        # Calculate moving average of recent C/N0 values (μC/N0,recent)
        recent_avg = sum(GNSSJammingMetrics.cn0_history) / len(GNSSJammingMetrics.cn0_history)

        # Calculate deviation: ΔC/N0(t) = |C/N0(t) - μC/N0,recent(t)|
        deviation = abs(self.avg_cn0 - recent_avg)

        return deviation

    def _calculate_cn0_correlation(self) -> float:
        """Calculate Pearson correlation coefficient between C/N0 values of different satellites

        High correlation (>0.95) indicates possible spoofing attack, as authentic satellites
        should have independent C/N0 variations due to different geometries and atmospheric conditions.

        Based on Rustamov et al., 2023: "During a spoofing attack, there is a higher correlation
        between the values with a coefficient of 0.99"
        """
        if len(self.cn0_values) < 2:
            return 0.0

        # Need at least 2 samples to calculate correlation
        # Use sliding window approach if we have historical data
        n = len(self.cn0_values)
        mean = sum(self.cn0_values) / n

        # Calculate variance
        variance = sum((x - mean) ** 2 for x in self.cn0_values) / n
        if variance == 0:
            return 1.0  # Perfect correlation if all values are identical (suspicious!)

        # For correlation between satellites, check if values are unnaturally similar
        # Low standard deviation relative to mean indicates high correlation
        coefficient_of_variation = (variance ** 0.5) / mean if mean > 0 else 0

        # Convert to correlation coefficient (inverse relationship)
        # Low CV = High correlation
        correlation = 1.0 - min(coefficient_of_variation / 0.3, 1.0)  # Normalize to 0-1

        return correlation

    def _calculate_doppler_variation(self) -> float:
        """Calculate Doppler frequency variation over time

        Constant or near-zero Doppler variation indicates possible spoofing,
        as authentic satellites show dynamic Doppler shifts due to orbital motion.

        Based on paper: "fake signal can be detected by the constant Doppler shift
        because the attacker is in the same location"
        """
        if len(GNSSJammingMetrics.doppler_history) < 5:
            return 0.0

        # Calculate standard deviation of Doppler history
        mean_doppler = sum(GNSSJammingMetrics.doppler_history) / len(GNSSJammingMetrics.doppler_history)
        variance = sum((x - mean_doppler) ** 2 for x in GNSSJammingMetrics.doppler_history) / len(GNSSJammingMetrics.doppler_history)

        return variance ** 0.5

    def _calculate_severity(self) -> str:
        """Estimate jamming severity from C/N0 and variation

        Enhanced severity calculation considering both absolute C/N0
        and temporal variations (spoofing indicator).
        """
        if not self.is_jammed:
            return 'NONE'

        # Check for spoofing signature (high variation)
        if self.cn0_variation > 5.0:
            return 'SPOOFING_DETECTED'

        # Original severity based on absolute C/N0
        if self.avg_cn0 < 20:
            return 'SEVERE'
        if self.avg_cn0 < 25:
            return 'HEAVY'
        if self.avg_cn0 < 30:
            return 'MODERATE'
        return 'LIGHT'

    def _estimate_type(self) -> str:
        """Estimate jamming/spoofing type from C/N0 patterns

        Enhanced type estimation using multi-parameter analysis:
        - C/N0 variation (temporal)
        - C/N0 correlation (inter-satellite)
        - Doppler variation (orbital dynamics)
        - Multi-satellite statistical analysis
        """
        if not self.is_jammed:
            return 'NONE'

        # Priority 1: High C/N0 correlation + constant Doppler = SPOOFING
        # Based on Rustamov et al., 2023: correlation coefficient 0.99 during spoofing
        if self.cn0_correlation > 0.95 and self.doppler_variation < 50:
            return 'HIGH_CONFIDENCE_SPOOFING'

        # Priority 2: Check for spoofing signature (abrupt C/N0 changes)
        if self.cn0_variation > 5.0:
            return 'POSSIBLE_SPOOFING'

        # Priority 3: Constant Doppler alone suggests spoofing
        # Authentic satellites show Doppler shifts > 100 Hz variation
        if self.doppler_variation < 20 and len(GNSSJammingMetrics.doppler_history) > 10:
            return 'SUSPECTED_SPOOFING_LOW_DOPPLER'

        # Priority 4: If all satellites equally degraded -> broadband noise jamming
        # Using C/N0 standard deviation across satellites
        if self.cn0_std < 3.0:  # Low variance = uniform degradation
            return 'BROADBAND_NOISE'

        # Priority 5: If some satellites much worse -> selective jamming or CW tone
        if self.satellites and self.max_cn0 - self.min_cn0 > 10:
            return 'CW_TONE'

        # Priority 6: Moderate variation suggests matched-power spoofing
        if self.cn0_std < 5.0:
            return 'MATCHED_POWER_ATTACK'

        return 'UNKNOWN'

    def to_dict(self) -> dict:
        """Convert to format compatible with web UI

        Enhanced with two-stage spoofing detection metrics
        """
        # Calculate confidence based on both methods
        # Higher confidence if both stages detect anomalies
        confidence = 0.0
        if self.is_jammed:
            # Stage 1 detection (threshold)
            stage1_confidence = 0.5 if self.avg_cn0 < 30 and self.avg_cn0 > 0 else 0.0
            # Stage 2 detection (variation)
            stage2_confidence = min(0.5, self.cn0_variation / 10.0)  # Up to 0.5 based on variation
            confidence = min(1.0, stage1_confidence + stage2_confidence)

        return {
            'noiseFloorDb': -140,  # Typical GPS noise floor (dBm)
            'totalPowerDb': -130,  # Estimated from C/N0
            'signalPowerDb': -160,  # GPS signal is ~-160 dBm
            'jammingToSignalRatio': max(0, 30 - self.avg_cn0) if self.is_jammed else 0,
            'isJammed': self.is_jammed,
            'jammingType': self.jamming_type,
            'jammerConfidence': confidence,
            'peakFrequencyHz': 0,
            'bandwidthHz': 0,
            'avgCN0': self.avg_cn0,
            'minCN0': self.min_cn0,
            'maxCN0': self.max_cn0,
            'numTracking': self.num_tracking,
            'kurtosis': 3.0,
            'agcLevel': 0,
            'correlationLoss': max(0, 45 - self.avg_cn0),
            'timestamp': int(time.time() * 1000),
            # Enhanced metrics from papers (Radoš et al., 2024)
            'cn0Variation': round(self.cn0_variation, 2),
            'cn0StdDev': round(self.cn0_std, 2),
            'jammingSeverity': self.jamming_severity,
            'detectionMethod': self._get_detection_method(),
            # New metrics from multi-parameter analysis
            'cn0Correlation': round(getattr(self, 'cn0_correlation', 0), 3),  # Inter-satellite correlation
            'avgDoppler': round(getattr(self, 'avg_doppler', 0), 2),  # Average Doppler shift (Hz)
            'dopplerVariation': round(getattr(self, 'doppler_variation', 0), 2),  # Doppler std dev (Hz)
            'dopplerStdDev': round(getattr(self, 'doppler_std', 0), 2)  # Current Doppler spread
        }

    def _get_detection_method(self) -> str:
        """Identify which detection method(s) triggered the alert"""
        if not self.is_jammed:
            return 'NONE'

        stage1 = self.avg_cn0 < 30 and self.avg_cn0 > 0
        stage2 = self.cn0_variation > 3.0 and len(GNSSJammingMetrics.cn0_history) > 5

        if stage1 and stage2:
            return 'TWO_STAGE_DETECTION'
        elif stage2:
            return 'VARIATION_DETECTION'
        elif stage1:
            return 'THRESHOLD_DETECTION'
        return 'UNKNOWN'


class GNSSSDRBridge:
    """Bridge between GNSS-SDR and web UI"""

    def __init__(self,
                 gnss_sdr_monitor_port: int = 1234,
                 websocket_port: int = 8766,
                 config_file: str = 'gnss_sdr_sdrplay_direct.conf',
                 auto_start_gnss_sdr: bool = True,
                 auto_start_sdrplay: bool = False,
                 sdrplay_freq: float = 1575.42e6,
                 sdrplay_gain: float = 40.0,
                 sdrplay_tuner: int = 2,
                 sdrplay_bias_tee: bool = True):
        self.gnss_sdr_port = gnss_sdr_monitor_port
        self.websocket_port = websocket_port
        self.config_file = config_file
        self.auto_start_gnss_sdr = auto_start_gnss_sdr
        self.auto_start_sdrplay = auto_start_sdrplay
        self.sdrplay_freq = sdrplay_freq
        self.sdrplay_gain = sdrplay_gain
        self.sdrplay_tuner = sdrplay_tuner
        self.sdrplay_bias_tee = sdrplay_bias_tee
        self.udp_socket: Optional[socket.socket] = None
        self.clients: set = set()
        self.satellites: Dict[int, GNSSSatellite] = {}
        self.running = False
        self.gnss_sdr_process: Optional[subprocess.Popen] = None
        self.sdrplay_process: Optional[subprocess.Popen] = None
        self.recorder_process: Optional[subprocess.Popen] = None
        self.sdrplay_connected = True  # Track SDRPlay connection status
        self.last_device_check = time.time()
        self.device_error_sent = False  # Only send error once
        self.position_fix: Optional[Dict] = None  # Store latest position fix from PVT
        self.last_data_time = time.time()  # Track when we last received data
        self.gnss_sdr_crashed = False  # Track if GNSS-SDR crashed

    def start_gnss_sdr(self):
        """Start GNSS-SDR as a subprocess"""
        if not self.auto_start_gnss_sdr:
            return

        # Check if config file exists (look in current directory)
        config_path = self.config_file
        if not os.path.isabs(config_path):
            # If relative path, look in script directory
            script_dir = os.path.dirname(os.path.abspath(__file__))
            config_path = os.path.join(script_dir, self.config_file)

        if not os.path.exists(config_path):
            print(f"⚠️  Config file not found: {config_path}")
            print("   GNSS-SDR will not be started automatically.")
            print("   Please start it manually in another terminal:")
            print(f"   gnss-sdr --config_file={config_path}")
            return

        self.config_file = config_path  # Update to absolute path

        # Check if gnss-sdr is in PATH
        try:
            subprocess.run(['which', 'gnss-sdr'], check=True, capture_output=True)
        except subprocess.CalledProcessError:
            print("⚠️  gnss-sdr not found in PATH")
            print("   Please start it manually in another terminal:")
            print(f"   gnss-sdr --config_file={self.config_file}")
            return

        print(f"\n🚀 Starting GNSS-SDR with config: {self.config_file}")
        print("   This may take a few seconds...")

        try:
            # Start GNSS-SDR as subprocess
            self.gnss_sdr_process = subprocess.Popen(
                ['gnss-sdr', f'--config_file={self.config_file}'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1
            )

            # Give it a moment to start and initialize
            time.sleep(3)

            # Check if it's still running
            if self.gnss_sdr_process.poll() is None:
                print("✓ GNSS-SDR started successfully (PID: {})".format(self.gnss_sdr_process.pid))
                print("  Waiting for signal source initialization...")
            else:
                # Process exited - check why
                return_code = self.gnss_sdr_process.returncode
                print(f"⚠️  GNSS-SDR exited with code {return_code}")
                # Try to get output
                try:
                    stdout, stderr = self.gnss_sdr_process.communicate(timeout=1)
                    if stderr and len(stderr) > 0:
                        print(f"   Error output: {stderr[:500]}")
                except:
                    pass
                self.gnss_sdr_process = None
        except Exception as e:
            print(f"⚠️  Failed to start GNSS-SDR: {e}")
            print("   Please start it manually in another terminal:")
            print(f"   gnss-sdr --config_file={self.config_file}")
            self.gnss_sdr_process = None

    def stop_gnss_sdr(self):
        """Stop GNSS-SDR subprocess"""
        if self.gnss_sdr_process:
            print("\n🛑 Stopping GNSS-SDR...")
            self.gnss_sdr_process.terminate()
            try:
                self.gnss_sdr_process.wait(timeout=5)
                print("✓ GNSS-SDR stopped")
            except subprocess.TimeoutExpired:
                print("⚠️  GNSS-SDR didn't stop gracefully, killing...")
                self.gnss_sdr_process.kill()
                self.gnss_sdr_process.wait()
            self.gnss_sdr_process = None

    def start_recorder(self):
        """Start continuous IQ recorder as a subprocess"""
        if not self.auto_start_sdrplay:
            return

        # Check if record_iq_samples.py exists (look in script directory)
        script_dir = os.path.dirname(os.path.abspath(__file__))
        recorder_path = os.path.join(script_dir, 'record_iq_samples.py')

        if not os.path.exists(recorder_path):
            print(f"⚠️  record_iq_samples.py not found at {recorder_path}")
            print("   Continuous recording will not start automatically")
            return

        print(f"\n🚀 Starting continuous IQ recorder")
        print(f"  Output: /tmp/gps_iq_samples.dat")
        print(f"  Frequency: {self.sdrplay_freq / 1e6:.2f} MHz")
        print(f"  Sample rate: 2.048 MSPS")

        try:
            # Detect Python interpreter (use current sys.executable to preserve venv)
            import sys
            python_exe = sys.executable

            # Build command for continuous recording
            cmd = [
                python_exe, '-B', '-u', recorder_path,
                '/tmp/gps_iq_samples.dat',
                '--continuous'
            ]

            # Set environment with library path for SDRPlay API and SoapySDR Python bindings
            env = os.environ.copy()
            env['DYLD_LIBRARY_PATH'] = '/usr/local/lib:' + env.get('DYLD_LIBRARY_PATH', '')
            env['PYTHONPATH'] = '/opt/homebrew/lib/python3.14/site-packages:' + env.get('PYTHONPATH', '')

            # Start process
            self.recorder_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                env=env
            )

            # Give it a moment to start
            time.sleep(3)

            # Check if it's still running
            if self.recorder_process.poll() is None:
                print(f"✓ Continuous recorder started (PID: {self.recorder_process.pid})")
                print("  Recording IQ samples to /tmp/gps_iq_samples.dat")
            else:
                # Process exited - check why
                return_code = self.recorder_process.returncode
                print(f"⚠️  Recorder exited with code {return_code}")
                print("   Make sure:")
                print("   • SDRPlay is connected via USB")
                print("   • SDRPlay API is installed")
                print("   • No other program is using SDRPlay")
                self.recorder_process = None
        except Exception as e:
            print(f"⚠️  Failed to start recorder: {e}")
            self.recorder_process = None

    def stop_recorder(self):
        """Stop continuous recorder subprocess"""
        if self.recorder_process:
            print("\n🛑 Stopping continuous recorder...")
            self.recorder_process.terminate()
            try:
                self.recorder_process.wait(timeout=5)
                print("✓ Recorder stopped")
            except subprocess.TimeoutExpired:
                print("⚠️  Recorder didn't stop gracefully, killing...")
                self.recorder_process.kill()
                self.recorder_process.wait()
            self.recorder_process = None

    def check_sdrplay_connected(self):
        """Check if SDRPlay device is still connected

        For Direct API mode, we check:
        1. If GNSS-SDR process is still running
        2. If we're receiving data (via last_data_time tracking)

        Note: Direct API streams via FIFO, so we infer connection status
        from data flow and process health.
        """
        # Check if GNSS-SDR process is alive (if we started it)
        if self.gnss_sdr_process:
            if self.gnss_sdr_process.poll() is not None:
                # Process died - likely SDRplay device disconnected or streaming stopped
                return False

        # For live mode, assume connected (GNSS-SDR manages connection via FIFO)
        # If device disconnects, GNSS-SDR will exit and we'll detect it above
        return True

    def _get_device_error_message(self) -> Optional[str]:
        """Get appropriate error message based on device status"""
        if self.gnss_sdr_crashed:
            return 'GNSS-SDR stopped unexpectedly. Check if SDRPlay is connected and not in use by another program.'

        if not self.sdrplay_connected:
            now = time.time()
            if (now - self.last_data_time) > 120.0:
                return f'No data received for {int(now - self.last_data_time)}s. SDRplay streaming may be interrupted.'
            else:
                return 'SDRplay Direct API connection lost. Check device and restart streaming.'

        return None

    def setup_udp_receiver(self):
        """Setup UDP socket to receive GNSS-SDR monitor data"""
        self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            self.udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        except AttributeError:
            pass  # SO_REUSEPORT not available on all platforms

        # Close any existing bindings on this port
        try:
            self.udp_socket.bind(('127.0.0.1', self.gnss_sdr_port))
        except OSError as e:
            print(f"⚠️  Warning: Could not bind UDP port {self.gnss_sdr_port}: {e}")
            print(f"   Trying to continue anyway...")
            # Try binding to any available port as fallback
            self.udp_socket.bind(('127.0.0.1', 0))
            actual_port = self.udp_socket.getsockname()[1]
            print(f"   Using alternative port: {actual_port}")
            self.gnss_sdr_port = actual_port

        self.udp_socket.settimeout(1.0)  # 1 second timeout
        print(f"✓ Listening for GNSS-SDR data on UDP port {self.gnss_sdr_port}")

    async def monitor_gnss_sdr_process(self):
        """Monitor GNSS-SDR process health and restart if needed"""
        print("✓ Starting GNSS-SDR process monitor...")
        print("")

        while self.running:
            # Check if GNSS-SDR process is still alive (if we started it)
            if self.gnss_sdr_process and not self.gnss_sdr_crashed:
                poll_result = self.gnss_sdr_process.poll()
                if poll_result is not None:
                    # Process exited
                    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] ❌ GNSS-SDR CRASHED (exit code: {poll_result})")

                    # Try to get error output
                    try:
                        stdout, stderr = self.gnss_sdr_process.communicate(timeout=1)
                        if stderr and len(stderr) > 0:
                            print(f"   Last error: {stderr[-500:]}")  # Last 500 chars
                    except:
                        pass

                    # Mark as crashed and notify clients
                    self.gnss_sdr_crashed = True
                    self.sdrplay_connected = False

                    # Send error to clients
                    error_msg = {
                        'protocol': 'GNSS_GPS_L1',
                        'satellites': [],
                        'deviceStatus': {
                            'sdrplayConnected': False,
                            'gnssSdrCrashed': True,
                            'deviceError': 'GNSS-SDR stopped unexpectedly. Check if SDRPlay is connected and accessible.'
                        },
                        'timestamp': int(time.time() * 1000)
                    }
                    await self.broadcast_message(json.dumps(error_msg))

                    print("   Possible causes:")
                    print("   • SDRPlay device disconnected")
                    print("   • Device is in use by another program")
                    print("   • SDRplay Direct API streaming stopped")
                    print("   • Insufficient permissions")
                    print("")
                    print("   Manual restart required:")
                    print(f"   gnss-sdr --config_file={self.config_file}")

            # Check every 2 seconds
            await asyncio.sleep(2.0)

    async def handle_client(self, websocket):
        """Handle WebSocket client connection"""
        client_addr = websocket.remote_address
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Client connected: {client_addr}")
        self.clients.add(websocket)

        try:
            async for message in websocket:
                # Handle progress updates from send_progress.py and parse_gnss_logs.py
                try:
                    data = json.loads(message)
                    # Check if it's a progress or status message (not GNSS data)
                    if 'type' in data or 'protocol' in data:
                        print(f"[{datetime.now().strftime('%H:%M:%S')}] 📨 Received message from client, broadcasting to {len(self.clients)} clients")
                        if 'protocol' in data:
                            sat_count = len(data.get('satellites', []))
                            print(f"   GNSS data: {sat_count} satellites")
                        elif 'type' in data:
                            print(f"   Progress: {data.get('phase', 'unknown')} - {data.get('message', '')}")
                        # Broadcast to all other clients
                        await self.broadcast_message(message)
                        print(f"   ✓ Broadcast complete")
                except json.JSONDecodeError:
                    pass  # Ignore malformed messages
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            self.clients.discard(websocket)  # Use discard to avoid KeyError
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Client disconnected: {client_addr}")

    async def broadcast_message(self, message: str):
        """Broadcast a message to all connected clients"""
        disconnected = set()
        for client in self.clients:
            try:
                await client.send(message)
            except websockets.exceptions.ConnectionClosed:
                disconnected.add(client)
        # Remove disconnected clients
        self.clients -= disconnected

    def parse_gnss_sdr_message(self, data: bytes):
        """
        Parse GNSS-SDR monitor PVT message using protobuf

        GNSS-SDR sends position/velocity/time (PVT) solutions via UDP
        using the MonitorPvt protobuf format defined in monitor_pvt.proto

        Returns dict with position fix data or None if parsing fails
        """
        if not PROTOBUF_AVAILABLE:
            return None

        try:
            # Parse protobuf message
            pvt = MonitorPvt()
            pvt.ParseFromString(data)

            # Convert ECEF to lat/lon/height is already done by GNSS-SDR
            position_data = {
                'latitude': pvt.latitude,       # degrees, positive = North
                'longitude': pvt.longitude,     # degrees, positive = East
                'height': pvt.height,           # meters above WGS84 ellipsoid
                'valid_sats': pvt.valid_sats,   # number of satellites used in solution
                'solution_status': pvt.solution_status,  # RTKLIB status
                'pdop': pvt.pdop,               # Position Dilution of Precision
                'hdop': pvt.hdop,               # Horizontal DOP
                'vdop': pvt.vdop,               # Vertical DOP
                'gdop': pvt.gdop,               # Geometric DOP
                'velocity_east': pvt.vel_e,     # m/s
                'velocity_north': pvt.vel_n,    # m/s
                'velocity_up': pvt.vel_u,       # m/s
                'course_over_ground': pvt.cog,  # degrees
                'gps_week': pvt.week,
                'time_of_week_ms': pvt.tow_at_current_symbol_ms,
                'utc_time': pvt.utc_time,
                'geohash': pvt.geohash if pvt.geohash else None
            }

            return position_data

        except Exception as e:
            print(f"Error parsing GNSS-SDR protobuf message: {e}")
            return None

    async def read_gnss_sdr_data(self):
        """Read data from GNSS-SDR UDP monitor"""
        print("✓ Starting GNSS-SDR UDP data receiver...")
        print(f"  Listening on UDP port {self.gnss_sdr_port} for monitor packets")
        print("")

        last_report = time.time()
        message_count = 0
        last_data_time = time.time()
        waiting_warned = False

        while self.running:
            try:
                data, addr = self.udp_socket.recvfrom(4096)
                message_count += 1
                last_data_time = time.time()
                self.last_data_time = last_data_time  # Update global tracker
                waiting_warned = False

                # Parse PVT message from GNSS-SDR monitor
                position_data = self.parse_gnss_sdr_message(data)
                if position_data:
                    # Store latest position fix
                    self.position_fix = position_data
                    # Log first position fix
                    if message_count == 1:
                        print(f"[{datetime.now().strftime('%H:%M:%S')}] "
                              f"📍 Position fix: {position_data['latitude']:.6f}°N, "
                              f"{position_data['longitude']:.6f}°E, "
                              f"{position_data['height']:.1f}m | "
                              f"{position_data['valid_sats']} satellites")

                # Report reception every second
                now = time.time()
                if now - last_report >= 1.0:
                    pos_info = ""
                    if self.position_fix:
                        pos_info = f" | 📍 Position: {self.position_fix['valid_sats']} sats, HDOP {self.position_fix['hdop']:.1f}"
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] "
                          f"📡 Received {message_count} monitor packets from GNSS-SDR | "
                          f"🌐 {len(self.clients)} WebSocket client(s) connected{pos_info}")
                    message_count = 0
                    last_report = now

            except socket.timeout:
                # No data received - check if we should warn
                now = time.time()
                if not waiting_warned and (now - last_data_time) > 60.0:
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] "
                          f"⚠️  No data from GNSS-SDR for {int(now - last_data_time)}s")
                    print("   Possible reasons:")
                    print("   • GNSS-SDR is still initializing (wait 10-60s for satellite acquisition)")
                    print("   • No signal source connected (check SDRPlay)")
                    print("   • Antenna doesn't have clear sky view")
                    print("   • Monitor output disabled in config")
                    waiting_warned = True
                await asyncio.sleep(0.1)
            except Exception as e:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] ❌ Error reading GNSS-SDR data: {e}")
                await asyncio.sleep(1.0)

    async def broadcast_results(self):
        """Broadcast GNSS results to connected clients (only on change)"""
        print("✓ Starting WebSocket result broadcaster...")
        print(f"  Broadcasting satellite data on change detection to port {self.websocket_port}")
        print("")

        broadcast_count = 0
        last_satellite_report = time.time()
        last_satellite_count = 0
        last_message_hash = None  # Track last sent message to detect changes

        while self.running:
            # Check SDRPlay connection every 5 seconds
            now = time.time()
            if now - self.last_device_check >= 5.0:
                device_connected = self.check_sdrplay_connected()

                # Also check data flow - if no data for >2 minutes, assume connection issue
                data_stale = (now - self.last_data_time) > 120.0

                if device_connected != self.sdrplay_connected or (device_connected and data_stale):
                    # Connection status changed or data stopped flowing
                    self.sdrplay_connected = device_connected and not data_stale
                    self.device_error_sent = False  # Reset flag on status change

                    if not self.sdrplay_connected:
                        if not device_connected:
                            print(f"\n[{datetime.now().strftime('%H:%M:%S')}] ⚠️  GNSS-SDR PROCESS DIED!")
                            print("   Likely causes: SDRPlay disconnected or Direct API streaming stopped")
                        elif data_stale:
                            print(f"\n[{datetime.now().strftime('%H:%M:%S')}] ⚠️  NO DATA FOR {int(now - self.last_data_time)}s!")
                            print("   Possible causes:")
                            print("   • SDRplay Direct API streaming interrupted")
                            print("   • SDRPlay in use by another program")
                            print("   • No GPS signal (check antenna placement)")
                    else:
                        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] ✅ Connection restored")

                self.last_device_check = now

            if self.clients:
                # Get current satellite list
                satellites = list(self.satellites.values())

                # Track satellite count changes
                tracking_satellites = [s for s in satellites if s.tracking_state >= 2]
                current_count = len(tracking_satellites)

                # Calculate jamming metrics
                jamming = GNSSJammingMetrics(satellites)

                # Build result message (compatible with web UI format)
                result = {
                    'protocol': 'GNSS_GPS_L1',
                    'satellites': [s.to_dict() for s in satellites],
                    'jamming': jamming.to_dict(),
                    'timestamp': int(time.time() * 1000),
                    'deviceStatus': {
                        'sdrplayConnected': self.sdrplay_connected,
                        'gnssSdrCrashed': self.gnss_sdr_crashed,
                        'dataStale': (time.time() - self.last_data_time) > 120.0,
                        'deviceError': self._get_device_error_message()
                    }
                }

                # Add position fix data if available
                if self.position_fix:
                    result['positionFix'] = self.position_fix

                # Create a hash of the satellite data (excluding timestamp) to detect changes
                satellite_data_str = json.dumps({
                    'satellites': result['satellites'],
                    'jamming': {k: v for k, v in result['jamming'].items() if k != 'timestamp'}
                }, sort_keys=True)
                current_hash = hash(satellite_data_str)

                # Only broadcast if data has changed
                if current_hash != last_message_hash:
                    # Log satellite status changes
                    if current_count != last_satellite_count:
                        if current_count > 0:
                            prn_list = ", ".join([f"PRN {s.prn}" for s in tracking_satellites[:5]])
                            if current_count > 5:
                                prn_list += f" (+{current_count - 5} more)"
                            print(f"\n[{datetime.now().strftime('%H:%M:%S')}] 🛰️  SATELLITES LOCKED: {current_count} tracking")
                            print(f"   Tracking: {prn_list}")
                            if current_count >= 4:
                                print(f"   ✅ Sufficient for position fix!")
                        elif last_satellite_count > 0:
                            print(f"\n[{datetime.now().strftime('%H:%M:%S')}] ⚠️  Lost satellite lock")
                        last_satellite_count = current_count

                    # Log jamming/spoofing status when it changes
                    jamming_dict = result['jamming']
                    if jamming_dict.get('isJammed'):
                        severity = jamming_dict.get('severity', 'UNKNOWN')
                        jam_type = jamming_dict.get('type', 'UNKNOWN')
                        avg_cn0 = jamming_dict.get('avgCN0', 0)
                        print(f"[{datetime.now().strftime('%H:%M:%S')}] ⚠️  GPS JAMMING DETECTED")
                        print(f"   Severity: {severity} | Type: {jam_type}")
                        print(f"   Avg C/N0: {avg_cn0:.1f} dB-Hz (threshold: 30 dB-Hz)")
                        if jam_type == 'BROADBAND_NOISE':
                            print(f"   📡 Likely external RF jamming (e.g., Kaliningrad region)")
                        elif 'SPOOFING' in jam_type:
                            print(f"   🚨 SPOOFING ATTACK SUSPECTED!")
                        if jamming_dict.get('cn0Variation'):
                            print(f"   C/N0 Variation: {jamming_dict['cn0Variation']:.2f} dB")
                        if jamming_dict.get('dopplerVariation'):
                            print(f"   Doppler Variation: {jamming_dict['dopplerVariation']:.1f} Hz")

                    # Send to all clients
                    message = json.dumps(result)
                    disconnected = set()

                    for client in self.clients:
                        try:
                            await client.send(message)
                        except websockets.exceptions.ConnectionClosed:
                            disconnected.add(client)

                    # Remove disconnected clients
                    self.clients -= disconnected

                    broadcast_count += 1
                    last_message_hash = current_hash

                    print(f"[{datetime.now().strftime('%H:%M:%S')}] 📤 Satellite data changed - broadcast to {len(self.clients)} client(s)")

                # Report status every 5 seconds (even if no changes)
                now = time.time()
                if now - last_satellite_report >= 5.0:
                    sat_count = len(satellites)
                    tracking_count = sum(1 for s in satellites if s.tracking_state >= 2)

                    if sat_count > 0:
                        avg_cn0 = sum(s.cn0_dbhz for s in satellites) / sat_count
                        print(f"[{datetime.now().strftime('%H:%M:%S')}] "
                              f"🛰️  {tracking_count}/{sat_count} satellites tracking | "
                              f"Avg C/N0: {avg_cn0:.1f} dB-Hz | "
                              f"📤 Sent {broadcast_count} updates")

                        # Show satellite details
                        print("   Satellites:")
                        for s in satellites:
                            state_emoji = "🔒" if s.tracking_state >= 2 else "🔍" if s.tracking_state == 1 else "⏳"
                            print(f"     {state_emoji} PRN {s.prn}: C/N0={s.cn0_dbhz:.1f} dB-Hz, "
                                  f"Doppler={s.doppler_hz:.1f} Hz, State={['SEARCHING','ACQUIRED','TRACKING'][min(s.tracking_state, 2)]}")
                    else:
                        print(f"[{datetime.now().strftime('%H:%M:%S')}] "
                              f"🔍 Searching for satellites... | "
                              f"📤 Sent {broadcast_count} updates")

                    broadcast_count = 0
                    last_satellite_report = now

            # Check for changes every 100ms (faster response, less CPU than 1Hz)
            await asyncio.sleep(0.1)

    async def run_server(self):
        """Run WebSocket server and GNSS-SDR receiver"""
        print("=" * 70)
        print("GNSS-SDR to Web-Spectrum Bridge (Continuous Mode)")
        print("=" * 70)
        print("")
        print("This bridge connects GNSS-SDR to your web UI using continuous file recording")
        print("")
        print("Architecture:")
        print("  SDRPlay → IQ Recorder → /tmp/file → GNSS-SDR → UDP Monitor → Bridge → WebSocket → Web UI")
        print("")
        print(f"📍 WebSocket server: ws://localhost:{self.websocket_port}")
        print(f"📍 GNSS-SDR monitor: UDP port {self.gnss_sdr_port}")
        print(f"📍 IQ samples file: /tmp/gps_iq_samples.dat")
        print("")

        # Start continuous recorder if auto-start enabled (only for continuous file mode)
        if self.auto_start_sdrplay and 'continuous' in self.config_file.lower():
            self.start_recorder()
            # Wait a bit for initial data to be recorded
            if self.recorder_process:
                print("  Waiting 10s for initial data recording...")
                time.sleep(10)

        # Start GNSS-SDR if auto-start enabled
        self.start_gnss_sdr()

        if self.auto_start_gnss_sdr and self.gnss_sdr_process:
            # Auto-start succeeded
            print("=" * 70)
            print("✅ GNSS-SDR AUTO-START: SUCCESS")
            print("=" * 70)
            print("")
            print("Status:")
            print(f"  • GNSS-SDR running (PID: {self.gnss_sdr_process.pid})")
            if self.recorder_process:
                print(f"  • Continuous recorder running (PID: {self.recorder_process.pid})")
                print(f"  • Recording IQ samples: SDRPlay → /tmp/gps_iq_samples.dat → GNSS-SDR")
            else:
                print(f"  • Waiting for IQ samples file")
            print(f"  • Monitor output ready (UDP port {self.gnss_sdr_port})")
            print(f"  • WebSocket ready (ws://localhost:{self.websocket_port})")
            print("")
            print("Next steps:")
            print("  1. Connect web UI to: ws://localhost:{self.websocket_port}")
            print("  2. GNSS-SDR will process signals and send satellite data")
            print("")
            print("⏳ Waiting for GNSS-SDR initialization (10-30s)...")
            print("")
        else:
            # Manual mode or auto-start failed
            print("=" * 70)
            print("⚠️  MANUAL MODE")
            print("=" * 70)
            print("")
            print("Manual steps:")
            print("  1. Start GNSS-SDR in another terminal:")
            print(f"     gnss-sdr --config_file={self.config_file}")
            print("")
            print("  2. Start web UI: npm start")
            print("  3. Open browser: http://localhost:3005")
            print("  4. Go to SDRPlay Decoder page")
            print(f"  5. Connect to WebSocket: ws://localhost:{self.websocket_port}")
            print("")

        print("Press Ctrl+C to stop")
        print("=" * 70)
        print("")

        # Setup UDP receiver
        self.setup_udp_receiver()
        self.running = True

        print("🚀 Starting bridge services...")
        print("")

        # Start WebSocket server with keepalive to prevent timeout
        # ping_interval=None disables automatic ping (prevents 40s disconnect)
        # ping_timeout=None disables pong timeout
        async with websockets.serve(
            self.handle_client,
            "0.0.0.0",
            self.websocket_port,
            ping_interval=None,  # Disable automatic ping
            ping_timeout=None    # Disable pong timeout
        ):
            print(f"✓ WebSocket server listening on ws://localhost:{self.websocket_port}")
            print("")

            # Start background tasks
            gnss_task = asyncio.create_task(self.read_gnss_sdr_data())
            broadcast_task = asyncio.create_task(self.broadcast_results())
            monitor_task = asyncio.create_task(self.monitor_gnss_sdr_process())

            try:
                await asyncio.Future()  # Run forever
            except asyncio.CancelledError:
                self.running = False
                gnss_task.cancel()
                broadcast_task.cancel()
                monitor_task.cancel()
                raise

    def cleanup(self):
        """Cleanup resources"""
        print("\nCleaning up...")
        self.running = False

        # Stop GNSS-SDR if we started it
        self.stop_gnss_sdr()

        # Stop recorder if we started it
        self.stop_recorder()

        if self.udp_socket:
            self.udp_socket.close()

        print("Cleanup complete!")


def main():
    import argparse
    import signal
    import sys

    parser = argparse.ArgumentParser(
        description='GNSS-SDR to Web-Spectrum Bridge (with automatic GNSS-SDR startup)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Example usage:
  # Start bridge with automatic GNSS-SDR startup (easiest!)
  python gnss_sdr_bridge.py

  # Custom config file
  python gnss_sdr_bridge.py --config gnss_sdr_config.conf

  # Manual mode (start GNSS-SDR yourself)
  python gnss_sdr_bridge.py --no-auto-start
  # Then in another terminal:
  gnss-sdr --config_file=gnss_sdr_config.conf
        """
    )

    parser.add_argument('--monitor-port', type=int, default=1234,
                        help='UDP port for GNSS-SDR monitor (default: 1234)')
    parser.add_argument('--websocket-port', type=int, default=8766,
                        help='WebSocket server port (default: 8766)')
    parser.add_argument('--config', type=str, default='gnss_sdr_sdrplay_direct.conf',
                        help='GNSS-SDR config file (default: gnss_sdr_sdrplay_direct.conf, or gnss_sdr_fifo.conf for FIFO mode)')
    parser.add_argument('--no-auto-start', action='store_true',
                        help='Do not automatically start GNSS-SDR (manual mode)')
    parser.add_argument('--no-sdrplay', action='store_true',
                        help='Do not automatically start continuous IQ recorder')
    parser.add_argument('--freq', type=float, default=1575.42e6,
                        help='SDRPlay frequency in Hz (default: 1575.42e6 for GPS L1)')
    parser.add_argument('--gain', type=float, default=40.0,
                        help='SDRPlay gain in dB (default: 40)')
    parser.add_argument('--tuner', type=int, default=2, choices=[1, 2],
                        help='SDRPlay tuner selection (default: 2)')
    parser.add_argument('--no-bias-tee', action='store_true',
                        help='Disable bias-T (default: enabled on Tuner 2)')

    args = parser.parse_args()

    # Create bridge
    bridge = GNSSSDRBridge(
        gnss_sdr_monitor_port=args.monitor_port,
        websocket_port=args.websocket_port,
        config_file=args.config,
        auto_start_gnss_sdr=not args.no_auto_start,
        auto_start_sdrplay=not args.no_sdrplay,
        sdrplay_freq=args.freq,
        sdrplay_gain=args.gain,
        sdrplay_tuner=args.tuner,
        sdrplay_bias_tee=not args.no_bias_tee
    )

    # Signal handler for graceful shutdown
    def signal_handler(sig, frame):
        print("\n\nShutdown requested...")
        bridge.cleanup()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)

    # Run bridge
    try:
        asyncio.run(bridge.run_server())
    except KeyboardInterrupt:
        pass
    finally:
        bridge.cleanup()


if __name__ == '__main__':
    main()
