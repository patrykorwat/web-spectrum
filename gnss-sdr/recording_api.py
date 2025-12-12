#!/usr/bin/env python3
"""
Flask API Server for GPS Recording and Processing
Handles UI requests to record SDRplay data and process with GNSS-SDR
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import subprocess
import os
import signal
import time
import json
from datetime import datetime
from pathlib import Path

app = Flask(__name__)
CORS(app)  # Enable CORS for React UI

# Global state
recording_process = None
processing_process = None
current_recording = None
recording_start_time = None

RECORDINGS_DIR = "/Users/patrykorwat/git/web-spectrum/gnss-sdr/recordings"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# Ensure recordings directory exists
os.makedirs(RECORDINGS_DIR, exist_ok=True)


@app.route('/gnss/start-recording', methods=['POST'])
def start_recording():
    """Start GPS data recording from SDRplay"""
    global recording_process, current_recording, recording_start_time

    try:
        data = request.get_json()
        duration = data.get('duration', 300)  # Default 5 minutes

        if recording_process and recording_process.poll() is None:
            return jsonify({
                'success': False,
                'error': 'Recording already in progress'
            }), 400

        # Generate filename with timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"gps_recording_{timestamp}.dat"
        filepath = os.path.join(RECORDINGS_DIR, filename)

        # Start recording using sdrplay_direct.py
        record_script = os.path.join(SCRIPT_DIR, 'sdrplay_direct.py')

        env = os.environ.copy()
        env['DYLD_LIBRARY_PATH'] = '/usr/local/lib:' + env.get('DYLD_LIBRARY_PATH', '')
        env['PYTHONUNBUFFERED'] = '1'

        recording_process = subprocess.Popen(
            [
                'python3', '-u', record_script,
                '--output', filepath,
                '--duration', str(duration),
                '--sample-rate', '2048000',
                '--frequency', '1575420000',
                '--gain-reduction', '30'
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            env=env,
            universal_newlines=True,
            bufsize=1
        )

        current_recording = filepath
        recording_start_time = time.time()

        return jsonify({
            'success': True,
            'filename': filename,
            'filepath': filepath,
            'duration': duration,
            'started_at': timestamp
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/gnss/stop-recording', methods=['POST'])
def stop_recording():
    """Stop current GPS recording"""
    global recording_process, current_recording

    try:
        if not recording_process or recording_process.poll() is not None:
            return jsonify({
                'success': False,
                'error': 'No recording in progress'
            }), 400

        # Send SIGINT to gracefully stop recording
        recording_process.send_signal(signal.SIGINT)
        recording_process.wait(timeout=5)

        file_size = 0
        if current_recording and os.path.exists(current_recording):
            file_size = os.path.getsize(current_recording)

        result = {
            'success': True,
            'filename': os.path.basename(current_recording) if current_recording else None,
            'file_size': file_size,
            'file_size_mb': round(file_size / (1024 * 1024), 2)
        }

        recording_process = None

        return jsonify(result)

    except subprocess.TimeoutExpired:
        recording_process.kill()
        return jsonify({
            'success': True,
            'warning': 'Recording process killed (timeout)'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/gnss/process-recording', methods=['POST'])
def process_recording():
    """Process recorded GPS data with GNSS-SDR"""
    global processing_process

    try:
        data = request.get_json()
        filename = data.get('filename')

        if not filename:
            return jsonify({
                'success': False,
                'error': 'No filename provided'
            }), 400

        filepath = os.path.join(RECORDINGS_DIR, filename)

        if not os.path.exists(filepath):
            return jsonify({
                'success': False,
                'error': f'Recording file not found: {filename}'
            }), 404

        if processing_process and processing_process.poll() is None:
            return jsonify({
                'success': False,
                'error': 'Processing already in progress'
            }), 400

        # Create GNSS-SDR config for this recording
        config_path = os.path.join(RECORDINGS_DIR, f"{filename}.conf")
        output_basename = os.path.join(RECORDINGS_DIR, filename.replace('.dat', ''))

        config_content = f"""; GNSS-SDR Configuration for Recorded File
[GNSS-SDR]
GNSS-SDR.internal_fs_sps=2048000

; Signal Source - Recorded File
SignalSource.implementation=File_Signal_Source
SignalSource.filename={filepath}
SignalSource.item_type=gr_complex
SignalSource.sampling_frequency=2048000
SignalSource.samples=0
SignalSource.repeat=false
SignalSource.dump=false
SignalSource.enable_throttle_control=true

; Signal Conditioning
SignalConditioner.implementation=Pass_Through

; GPS L1 C/A Channels
Channels_1C.count=12
Channels.in_acquisition=12
Channel.signal=1C

; Acquisition - Sensitive settings
Acquisition_1C.implementation=GPS_L1_CA_PCPS_Acquisition
Acquisition_1C.item_type=gr_complex
Acquisition_1C.coherent_integration_time_ms=1
Acquisition_1C.pfa=0.0001
Acquisition_1C.doppler_max=10000
Acquisition_1C.doppler_step=500
Acquisition_1C.threshold=0.002
Acquisition_1C.blocking=false
Acquisition_1C.dump=false
Acquisition_1C.max_dwells=2

; Tracking
Tracking_1C.implementation=GPS_L1_CA_DLL_PLL_Tracking
Tracking_1C.item_type=gr_complex
Tracking_1C.pll_bw_hz=50.0
Tracking_1C.dll_bw_hz=4.0
Tracking_1C.early_late_space_chips=0.5
Tracking_1C.dump=false

; Telemetry
TelemetryDecoder_1C.implementation=GPS_L1_CA_Telemetry_Decoder
TelemetryDecoder_1C.dump=false

; Observables
Observables.implementation=Hybrid_Observables
Observables.dump=false

; PVT - Position output
PVT.implementation=RTKLIB_PVT
PVT.positioning_mode=Single
PVT.output_rate_ms=1000
PVT.display_rate_ms=500
PVT.iono_model=Broadcast
PVT.trop_model=Saastamoinen
PVT.flag_rtcm_server=false
PVT.flag_rtcm_tty_port=false
PVT.nmea_dump_filename={output_basename}.nmea
PVT.flag_nmea_tty_port=false
PVT.kml_output_enabled=true
PVT.gpx_output_enabled=true
PVT.rinex_output_enabled=true
PVT.rinex_version=3
PVT.dump=false
PVT.dump_filename={output_basename}_pvt.dat
"""

        with open(config_path, 'w') as f:
            f.write(config_content)

        # Start GNSS-SDR processing
        env = os.environ.copy()
        env['DYLD_LIBRARY_PATH'] = '/usr/local/lib:' + env.get('DYLD_LIBRARY_PATH', '')
        env['PYTHONUNBUFFERED'] = '1'

        # Pipe through parse_gnss_logs.py for real-time updates
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

        return jsonify({
            'success': True,
            'config': config_path,
            'output_base': output_basename,
            'expected_outputs': [
                f"{output_basename}.nmea",
                f"{output_basename}.kml",
                f"{output_basename}.gpx"
            ]
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/gnss/status', methods=['GET'])
def get_status():
    """Get current recording/processing status"""
    global recording_process, processing_process, current_recording, recording_start_time

    recording_active = recording_process and recording_process.poll() is None
    processing_active = processing_process and processing_process.poll() is None

    status = {
        'recording': {
            'active': recording_active,
            'filename': os.path.basename(current_recording) if current_recording else None,
            'duration': int(time.time() - recording_start_time) if recording_active and recording_start_time else 0
        },
        'processing': {
            'active': processing_active
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

    return jsonify(status)


@app.route('/gnss/recordings', methods=['GET'])
def list_recordings():
    """List all available recordings"""
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

    return jsonify({
        'success': True,
        'recordings': recordings,
        'total': len(recordings)
    })


if __name__ == '__main__':
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
    print("Starting server on http://localhost:3001")
    print("=" * 70)
    print()

    app.run(host='0.0.0.0', port=3001, debug=False, threaded=True)
