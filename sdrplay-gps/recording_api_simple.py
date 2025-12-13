#!/usr/bin/env python3
"""
Simple HTTP API Server for GPS Recording and Processing
Uses Python's built-in http.server - no external dependencies
"""

from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import subprocess
import os
import signal
import time
from datetime import datetime
from pathlib import Path
import threading

# Global state
recording_process = None
processing_process = None
current_recording = None
recording_start_time = None
processing_start_time = None
processing_status = ''

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
RECORDINGS_DIR = os.path.join(SCRIPT_DIR, "recordings")

# Recording configuration
RECORDING_CONFIG = {
    'frequency': 1575420000,  # Hz (GPS L1)
    'frequency_mhz': 1575.42,  # MHz
    'sample_rate': 2048000,  # Hz
    'sample_rate_msps': 2.048,  # MSPS
    'gain_reduction': 30,  # dB - CRITICAL: Lower gain prevents thermal shutdown!
    'actual_gain': 29,  # dB (59 - gain_reduction) - Tested: 5 min recording stable
    'bandwidth_mhz': 2.0,  # MHz
    'format': 'Complex64 (IQ)',
    'duration_default': 300,  # seconds (5 minutes)
    'file_size_per_min_mb': 980,  # MB per minute
    'expected_size_5min_gb': 4.9,  # GB for 5 minutes
    'tuner': 2,  # RSPduo tuner: 1 (Tuner A) or 2 (Tuner B) - SET THIS TO YOUR ANTENNA PORT!
    'bias_tee': 'ENABLED'  # Bias-T for active antenna power
}

# Ensure recordings directory exists
os.makedirs(RECORDINGS_DIR, exist_ok=True)


class RecordingAPIHandler(BaseHTTPRequestHandler):
    """HTTP request handler for GPS recording API"""

    def _set_headers(self, status=200, content_type='application/json'):
        """Set HTTP response headers with CORS"""
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def do_OPTIONS(self):
        """Handle CORS preflight"""
        self._set_headers()

    def do_GET(self):
        """Handle GET requests"""
        global recording_process, processing_process, current_recording, recording_start_time, processing_start_time, processing_status

        if self.path == '/gnss/status':
            # Get current status
            recording_active = recording_process and recording_process.poll() is None
            processing_active = processing_process and processing_process.poll() is None

            status = {
                'recording': {
                    'active': recording_active,
                    'filename': os.path.basename(current_recording) if current_recording else None,
                    'duration': int(time.time() - recording_start_time) if recording_active and recording_start_time else 0
                },
                'processing': {
                    'active': processing_active,
                    'duration': int(time.time() - processing_start_time) if processing_active and processing_start_time else 0,
                    'status': processing_status
                },
                'recordings': []
            }

            # List available recordings
            if os.path.exists(RECORDINGS_DIR):
                for f in sorted(Path(RECORDINGS_DIR).glob('*.dat'), key=os.path.getmtime, reverse=True):
                    size = os.path.getsize(f)
                    status['recordings'].append({
                        'filename': f.name,
                        'size': size,
                        'size_mb': round(size / (1024 * 1024), 2),
                        'modified': datetime.fromtimestamp(os.path.getmtime(f)).isoformat()
                    })

            self._set_headers()
            self.wfile.write(json.dumps(status).encode())

        elif self.path == '/gnss/config':
            # Return recording configuration
            self._set_headers()
            self.wfile.write(json.dumps(RECORDING_CONFIG).encode())

        elif self.path == '/gnss/device-info':
            # Detect SDRplay device
            detect_script = os.path.join(SCRIPT_DIR, 'detect_sdrplay.py')
            try:
                result = subprocess.run(
                    ['python3', detect_script],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                device_info = json.loads(result.stdout)
                self._set_headers()
                self.wfile.write(json.dumps(device_info).encode())
            except Exception as e:
                self._set_headers(500)
                self.wfile.write(json.dumps({
                    'error': f'Device detection failed: {str(e)}',
                    'devices': []
                }).encode())

        elif self.path == '/gnss/recordings':
            # List all recordings
            recordings = []
            if os.path.exists(RECORDINGS_DIR):
                for f in sorted(Path(RECORDINGS_DIR).glob('*.dat'), key=os.path.getmtime, reverse=True):
                    size = os.path.getsize(f)
                    recordings.append({
                        'filename': f.name,
                        'filepath': str(f),
                        'size': size,
                        'size_mb': round(size / (1024 * 1024), 2),
                        'modified': datetime.fromtimestamp(os.path.getmtime(f)).isoformat(),
                        'has_nmea': os.path.exists(str(f).replace('.dat', '.nmea')),
                        'has_kml': os.path.exists(str(f).replace('.dat', '.kml'))
                    })

            self._set_headers()
            self.wfile.write(json.dumps({
                'success': True,
                'recordings': recordings,
                'total': len(recordings)
            }).encode())

        else:
            self._set_headers(404)
            self.wfile.write(json.dumps({'error': 'Not found'}).encode())

    def do_POST(self):
        """Handle POST requests"""
        global recording_process, processing_process, current_recording, recording_start_time

        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length).decode('utf-8') if content_length > 0 else '{}'

        try:
            data = json.loads(post_data)
        except:
            data = {}

        if self.path == '/gnss/start-recording':
            # Start recording
            try:
                duration = data.get('duration', RECORDING_CONFIG['duration_default'])
                # Allow tuner selection from request, fallback to config default
                tuner = data.get('tuner', RECORDING_CONFIG['tuner'])

                if recording_process and recording_process.poll() is None:
                    self._set_headers(400)
                    self.wfile.write(json.dumps({
                        'success': False,
                        'error': 'Recording already in progress'
                    }).encode())
                    return

                # Generate filename
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                filename = f"gps_recording_{timestamp}.dat"
                filepath = os.path.join(RECORDINGS_DIR, filename)

                # Start recording
                record_script = os.path.join(SCRIPT_DIR, 'sdrplay_direct.py')
                env = os.environ.copy()
                env['DYLD_LIBRARY_PATH'] = '/usr/local/lib:' + env.get('DYLD_LIBRARY_PATH', '')
                env['PYTHONUNBUFFERED'] = '1'

                recording_process = subprocess.Popen(
                    [
                        'python3', '-u', record_script,
                        '--output', filepath,
                        '--duration', str(duration),
                        '--sample-rate', str(RECORDING_CONFIG['sample_rate']),
                        '--frequency', str(RECORDING_CONFIG['frequency']),
                        '--gain-reduction', str(RECORDING_CONFIG['gain_reduction']),
                        '--tuner', str(tuner)  # Use selected tuner from request
                    ],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    env=env,
                    universal_newlines=True,
                    bufsize=1
                )

                current_recording = filepath
                recording_start_time = time.time()

                self._set_headers()
                self.wfile.write(json.dumps({
                    'success': True,
                    'filename': filename,
                    'filepath': filepath,
                    'duration': duration,
                    'started_at': timestamp
                }).encode())

            except Exception as e:
                self._set_headers(500)
                self.wfile.write(json.dumps({
                    'success': False,
                    'error': str(e)
                }).encode())

        elif self.path == '/gnss/stop-recording':
            # Stop recording
            try:
                if not recording_process or recording_process.poll() is not None:
                    self._set_headers(400)
                    self.wfile.write(json.dumps({
                        'success': False,
                        'error': 'No recording in progress'
                    }).encode())
                    return

                # Send SIGINT
                recording_process.send_signal(signal.SIGINT)
                recording_process.wait(timeout=5)

                file_size = 0
                if current_recording and os.path.exists(current_recording):
                    file_size = os.path.getsize(current_recording)

                recording_process = None

                self._set_headers()
                self.wfile.write(json.dumps({
                    'success': True,
                    'filename': os.path.basename(current_recording) if current_recording else None,
                    'file_size': file_size,
                    'file_size_mb': round(file_size / (1024 * 1024), 2)
                }).encode())

            except subprocess.TimeoutExpired:
                recording_process.kill()
                self._set_headers()
                self.wfile.write(json.dumps({
                    'success': True,
                    'warning': 'Recording process killed (timeout)'
                }).encode())
            except Exception as e:
                self._set_headers(500)
                self.wfile.write(json.dumps({
                    'success': False,
                    'error': str(e)
                }).encode())

        elif self.path == '/gnss/process-recording':
            # Process recording
            global processing_start_time, processing_status
            try:
                filename = data.get('filename')
                if not filename:
                    self._set_headers(400)
                    self.wfile.write(json.dumps({
                        'success': False,
                        'error': 'No filename provided'
                    }).encode())
                    return

                filepath = os.path.join(RECORDINGS_DIR, filename)
                if not os.path.exists(filepath):
                    self._set_headers(404)
                    self.wfile.write(json.dumps({
                        'success': False,
                        'error': f'Recording file not found: {filename}'
                    }).encode())
                    return

                if processing_process and processing_process.poll() is None:
                    self._set_headers(400)
                    self.wfile.write(json.dumps({
                        'success': False,
                        'error': 'Processing already in progress'
                    }).encode())
                    return

                # Create GNSS-SDR config
                config_path = os.path.join(RECORDINGS_DIR, f"{filename}.conf")
                output_basename = os.path.join(RECORDINGS_DIR, filename.replace('.dat', ''))

                config_content = f"""; GNSS-SDR Configuration for Recorded File
; Optimized for stationary receiver with good C/N0
[GNSS-SDR]
GNSS-SDR.internal_fs_sps=2048000

;######### SIGNAL SOURCE CONFIG ############
SignalSource.implementation=File_Signal_Source
SignalSource.filename={filepath}
SignalSource.item_type=gr_complex
SignalSource.sampling_frequency=2048000
SignalSource.freq=1575420000
SignalSource.samples=0
SignalSource.repeat=false
SignalSource.dump=false
SignalSource.enable_throttle_control=true

;######### SIGNAL CONDITIONER CONFIG ############
SignalConditioner.implementation=Signal_Conditioner

;######### DATA TYPE ADAPTER CONFIG ############
DataTypeAdapter.implementation=Pass_Through
DataTypeAdapter.item_type=gr_complex

;######### INPUT FILTER CONFIG ############
InputFilter.implementation=Freq_Xlating_Fir_Filter
InputFilter.input_item_type=gr_complex
InputFilter.output_item_type=gr_complex
InputFilter.taps_item_type=float
InputFilter.number_of_taps=5
InputFilter.number_of_bands=2
InputFilter.band1_begin=0.0
InputFilter.band1_end=0.45
InputFilter.band2_begin=0.55
InputFilter.band2_end=1.0
InputFilter.ampl1_begin=1.0
InputFilter.ampl1_end=1.0
InputFilter.ampl2_begin=0.0
InputFilter.ampl2_end=0.0
InputFilter.band1_error=1.0
InputFilter.band2_error=1.0
InputFilter.filter_type=bandpass
InputFilter.grid_density=16
InputFilter.sampling_frequency=2048000
InputFilter.IF=0

;######### RESAMPLER CONFIG ############
Resampler.implementation=Pass_Through
Resampler.item_type=gr_complex

;######### CHANNELS GLOBAL CONFIG ############
Channels_1C.count=8
Channels.in_acquisition=1

;######### GPS L1 C/A CHANNEL CONFIG ############
Channel0.signal=1C
Channel1.signal=1C
Channel2.signal=1C
Channel3.signal=1C
Channel4.signal=1C
Channel5.signal=1C
Channel6.signal=1C
Channel7.signal=1C

;######### GPS L1 C/A ACQUISITION CONFIG ############
Acquisition_1C.implementation=GPS_L1_CA_PCPS_Acquisition
Acquisition_1C.item_type=gr_complex
Acquisition_1C.coherent_integration_time_ms=1
Acquisition_1C.pfa=0.01
Acquisition_1C.doppler_max=5000
Acquisition_1C.doppler_step=250
Acquisition_1C.threshold=0.008
Acquisition_1C.dump=false

;######### GPS L1 C/A TRACKING CONFIG ############
; Optimized for stationary receiver with good signal
Tracking_1C.implementation=GPS_L1_CA_DLL_PLL_Tracking
Tracking_1C.item_type=gr_complex
Tracking_1C.pll_bw_hz=10.0
Tracking_1C.dll_bw_hz=1.0
Tracking_1C.fll_bw_hz=10.0
Tracking_1C.enable_fll_pull_in=true
Tracking_1C.pll_bw_narrow_hz=5.0
Tracking_1C.dll_bw_narrow_hz=0.5

;######### TELEMETRY DECODER CONFIG ############
TelemetryDecoder_1C.implementation=GPS_L1_CA_Telemetry_Decoder

;######### OBSERVABLES CONFIG ############
Observables.implementation=Hybrid_Observables

;######### PVT CONFIG ############
PVT.implementation=RTKLIB_PVT
PVT.positioning_mode=Single
PVT.output_rate_ms=100
PVT.display_rate_ms=500
PVT.kml_output_enabled=true
PVT.kml_output_path={RECORDINGS_DIR}/
PVT.gpx_output_enabled=true
PVT.gpx_output_path={RECORDINGS_DIR}/
PVT.nmea_dump_filename={output_basename}.nmea
PVT.nmea_dump_devname=/dev/pts/4
PVT.flag_nmea_tty_port=false
PVT.enable_monitor=true
PVT.monitor_udp_port=1234
"""

                with open(config_path, 'w') as f:
                    f.write(config_content)

                # Start GNSS-SDR processing
                env = os.environ.copy()
                env['DYLD_LIBRARY_PATH'] = '/usr/local/lib:' + env.get('DYLD_LIBRARY_PATH', '')
                env['PYTHONUNBUFFERED'] = '1'

                parse_script = os.path.join(SCRIPT_DIR, 'parse_gnss_logs.py')
                cmd = f"gnss-sdr --config_file={config_path} 2>&1 | python3 -u {parse_script}"

                processing_process = subprocess.Popen(
                    cmd,
                    shell=True,
                    env=env,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    universal_newlines=True,
                    bufsize=1
                )

                processing_start_time = time.time()
                processing_status = 'Starting GNSS-SDR processing...'

                self._set_headers()
                self.wfile.write(json.dumps({
                    'success': True,
                    'config': config_path,
                    'output_base': output_basename,
                    'expected_outputs': [
                        f"{output_basename}.nmea",
                        f"{output_basename}.kml",
                        f"{output_basename}.gpx"
                    ]
                }).encode())

            except Exception as e:
                self._set_headers(500)
                self.wfile.write(json.dumps({
                    'success': False,
                    'error': str(e)
                }).encode())

        else:
            self._set_headers(404)
            self.wfile.write(json.dumps({'error': 'Not found'}).encode())

    def log_message(self, format, *args):
        """Custom logging"""
        print(f"[{self.address_string()}] {format % args}")


def run_server(port=3001):
    """Run the HTTP server"""
    server_address = ('', port)
    httpd = HTTPServer(server_address, RecordingAPIHandler)

    print("=" * 70)
    print("🛰️  GPS Recording API Server")
    print("=" * 70)
    print()
    print(f"Recordings directory: {RECORDINGS_DIR}")
    print()
    print("Endpoints:")
    print("  POST /gnss/start-recording   - Start GPS data recording")
    print("  POST /gnss/stop-recording    - Stop current recording")
    print("  POST /gnss/process-recording - Process recorded file")
    print("  GET  /gnss/status            - Get current status")
    print("  GET  /gnss/recordings        - List all recordings")
    print()
    print(f"Server running on http://localhost:{port}")
    print("Press Ctrl+C to stop")
    print("=" * 70)
    print()

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n\n🛑 Shutting down server...")
        httpd.shutdown()


if __name__ == '__main__':
    run_server()
