#!/usr/bin/env python3
"""
GNSS Data Collection Control API

Simple HTTP API to start/stop/restart GNSS data collection from the web UI.
Runs on port 8767 (bridge is on 8766).
"""

import subprocess
import os
import signal
import json
from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Thread
import time

class GNSSControlHandler(BaseHTTPRequestHandler):
    # Class variable to store the current GNSS process
    gnss_process = None
    gnss_process_pid = None

    def _set_headers(self, status=200):
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def do_OPTIONS(self):
        self._set_headers()

    def do_GET(self):
        if self.path == '/status':
            self._set_headers()

            # Check if SDRplay Direct Mode streamer is running
            direct_mode_active = False
            direct_mode_info = ''
            try:
                result = subprocess.run(['pgrep', '-f', 'sdrplay_soapy_streamer'],
                                      capture_output=True, text=True, timeout=1)
                if result.returncode == 0:
                    direct_mode_active = True
                    direct_mode_info = 'SDRplay streamer is running continuously (Direct Mode)'
            except:
                pass

            status = {
                'running': GNSSControlHandler.gnss_process is not None and GNSSControlHandler.gnss_process.poll() is None,
                'pid': GNSSControlHandler.gnss_process_pid,
                'directMode': direct_mode_active,
                'directModeInfo': direct_mode_info
            }
            self.wfile.write(json.dumps(status).encode())
        else:
            self._set_headers(404)
            self.wfile.write(json.dumps({'error': 'Not found'}).encode())

    def do_POST(self):
        if self.path == '/start':
            self._handle_start()
        elif self.path == '/stop':
            self._handle_stop()
        elif self.path == '/restart':
            self._handle_restart()
        else:
            self._set_headers(404)
            self.wfile.write(json.dumps({'error': 'Not found'}).encode())

    def _handle_start(self):
        # Check if already running
        if GNSSControlHandler.gnss_process is not None and GNSSControlHandler.gnss_process.poll() is None:
            self._set_headers(400)
            self.wfile.write(json.dumps({'error': 'GNSS collection already running', 'pid': GNSSControlHandler.gnss_process_pid}).encode())
            return

        # Start GNSS data collection
        try:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            # Use file-based mode: record samples then process
            start_script = os.path.join(script_dir, 'start_gnss_file.sh')

            # Start the process with proper environment
            env = os.environ.copy()
            env['DYLD_LIBRARY_PATH'] = '/usr/local/lib:' + env.get('DYLD_LIBRARY_PATH', '')
            env['PYTHONPATH'] = '/opt/homebrew/lib/python3.14/site-packages:' + env.get('PYTHONPATH', '')

            process = subprocess.Popen(
                ['/bin/bash', start_script],
                cwd=script_dir,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )

            GNSSControlHandler.gnss_process = process
            GNSSControlHandler.gnss_process_pid = process.pid

            self._set_headers()
            self.wfile.write(json.dumps({
                'status': 'started',
                'pid': process.pid,
                'message': 'GNSS data collection started'
            }).encode())

            print(f"[Control API] Started GNSS collection (PID: {process.pid})")

        except Exception as e:
            self._set_headers(500)
            self.wfile.write(json.dumps({'error': str(e)}).encode())
            print(f"[Control API] Error starting GNSS collection: {e}")

    def _handle_stop(self):
        if GNSSControlHandler.gnss_process is None or GNSSControlHandler.gnss_process.poll() is not None:
            self._set_headers(400)
            self.wfile.write(json.dumps({'error': 'GNSS collection not running'}).encode())
            return

        try:
            # Kill the process group (to kill all child processes too)
            pid = GNSSControlHandler.gnss_process_pid
            try:
                # Send SIGTERM to process group
                os.killpg(os.getpgid(pid), signal.SIGTERM)
                time.sleep(2)
                # If still running, send SIGKILL
                if GNSSControlHandler.gnss_process.poll() is None:
                    os.killpg(os.getpgid(pid), signal.SIGKILL)
            except ProcessLookupError:
                pass  # Process already dead

            # Also kill by name to be sure
            subprocess.run(['pkill', '-9', '-f', 'start_gnss'], capture_output=True)  # Matches both start_gnss.sh and start_gnss_live.sh
            subprocess.run(['pkill', '-9', '-f', 'record_iq'], capture_output=True)
            subprocess.run(['pkill', '-9', '-f', 'gnss-sdr'], capture_output=True)
            subprocess.run(['pkill', '-9', '-f', 'parse_gnss_logs'], capture_output=True)

            GNSSControlHandler.gnss_process = None
            GNSSControlHandler.gnss_process_pid = None

            self._set_headers()
            self.wfile.write(json.dumps({
                'status': 'stopped',
                'message': 'GNSS data collection stopped'
            }).encode())

            print(f"[Control API] Stopped GNSS collection (PID: {pid})")

        except Exception as e:
            self._set_headers(500)
            self.wfile.write(json.dumps({'error': str(e)}).encode())
            print(f"[Control API] Error stopping GNSS collection: {e}")

    def _handle_restart(self):
        # Stop if running
        if GNSSControlHandler.gnss_process is not None and GNSSControlHandler.gnss_process.poll() is None:
            self._handle_stop()
            time.sleep(3)  # Wait for cleanup

        # Start again
        self._handle_start()

    def log_message(self, format, *args):
        # Suppress default logging to reduce noise
        pass

def run_server(port=8767):
    server_address = ('', port)
    httpd = HTTPServer(server_address, GNSSControlHandler)
    print(f"=" * 70)
    print(f"GNSS Data Collection Control API")
    print(f"=" * 70)
    print(f"")
    print(f"Listening on http://localhost:{port}")
    print(f"")
    print(f"Endpoints:")
    print(f"  GET  /status   - Check if GNSS collection is running")
    print(f"  POST /start    - Start GNSS data collection")
    print(f"  POST /stop     - Stop GNSS data collection")
    print(f"  POST /restart  - Restart GNSS data collection")
    print(f"")
    print(f"Press Ctrl+C to stop the API server")
    print(f"=" * 70)
    print(f"")

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n\nShutting down API server...")
        if GNSSControlHandler.gnss_process is not None:
            print("Stopping GNSS collection...")
            GNSSControlHandler._handle_stop(GNSSControlHandler)
        httpd.shutdown()

if __name__ == '__main__':
    run_server()
