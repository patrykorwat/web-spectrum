#!/usr/bin/env python3
"""
Continuous GNSS Pipeline with SDRplay Direct API
Ensures GNSS-SDR runs continuously and sends data to UI
"""

import os
import sys
import time
import signal
import subprocess
import threading
import asyncio
import websockets
import json
from datetime import datetime

# Add path for local imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

class ContinuousGNSSPipeline:
    def __init__(self):
        self.fifo_path = "/tmp/gnss_fifo"
        self.config_path = "/tmp/gnss_continuous.conf"
        self.streamer_process = None
        self.gnss_process = None
        self.progress_process = None
        self.monitor_thread = None
        self.running = False

        # Setup signal handlers
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)

    def signal_handler(self, sig, frame):
        print("\n\n🛑 Shutting down pipeline...")
        self.cleanup()
        sys.exit(0)

    def write_gnss_config(self):
        """Write GNSS-SDR configuration for continuous operation"""
        config = """; GNSS-SDR Continuous Operation Configuration
[GNSS-SDR]
GNSS-SDR.internal_fs_sps=2048000

; Signal Source - FIFO (special support for named pipes)
SignalSource.implementation=Fifo_Signal_Source
SignalSource.filename=/tmp/gnss_fifo
SignalSource.sample_type=gr_complex
SignalSource.dump=false

; Signal Conditioning - Pass through for now
SignalConditioner.implementation=Pass_Through
DataTypeAdapter.implementation=Pass_Through
InputFilter.implementation=Pass_Through
Resampler.implementation=Pass_Through

; GPS L1 C/A Channel Configuration
Channels_1C.count=12
Channels.in_acquisition=12
Channel.signal=1C

; Acquisition - Ultra-sensitive settings for weak signals
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

; Tracking - Optimized for stability
Tracking_1C.implementation=GPS_L1_CA_DLL_PLL_Tracking
Tracking_1C.item_type=gr_complex
Tracking_1C.pll_bw_hz=35.0
Tracking_1C.dll_bw_hz=2.0
Tracking_1C.dump=false

; Telemetry Decoder
TelemetryDecoder_1C.implementation=GPS_L1_CA_Telemetry_Decoder
TelemetryDecoder_1C.dump=false

; Observables
Observables.implementation=Hybrid_Observables
Observables.dump=false

; PVT Configuration
PVT.implementation=RTKLIB_PVT
PVT.positioning_mode=Single
PVT.output_rate_ms=1000
PVT.display_rate_ms=500
PVT.iono_model=Broadcast
PVT.trop_model=Saastamoinen
PVT.flag_rtcm_server=true
PVT.flag_rtcm_tty_port=false
PVT.rtcm_tcp_port=2101
PVT.rtcm_MT1019_rate_ms=5000
PVT.rtcm_MT1077_rate_ms=1000
PVT.dump=false

; Monitor for real-time updates
Monitor.enable_monitor=true
Monitor.decimation_factor=1
Monitor.client_addresses=127.0.0.1
Monitor.udp_port=1234
"""
        with open(self.config_path, 'w') as f:
            f.write(config)
        return self.config_path

    def start_streamer(self):
        """Start SDRplay FIFO streamer"""
        script_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            'sdrplay_fifo_streamer.py'
        )

        if not os.path.exists(script_path):
            print(f"❌ ERROR: {script_path} not found!")
            return None

        env = os.environ.copy()
        env['PYTHONUNBUFFERED'] = '1'
        env['DYLD_LIBRARY_PATH'] = '/usr/local/lib:' + env.get('DYLD_LIBRARY_PATH', '')

        self.streamer_process = subprocess.Popen(
            [sys.executable, '-u', script_path, self.fifo_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            bufsize=1,
            env=env
        )

        # Read streamer output
        def read_streamer():
            try:
                for line in self.streamer_process.stdout:
                    if line.strip():
                        print(f"[SDRplay] {line.strip()}", flush=True)
            except Exception as e:
                print(f"[SDRplay] Reader error: {e}")

        threading.Thread(target=read_streamer, daemon=True).start()
        time.sleep(0.5)

        if self.streamer_process.poll() is not None:
            print(f"❌ Streamer exited with code {self.streamer_process.returncode}")
            return None

        return self.streamer_process.pid

    def start_gnss_sdr(self):
        """Start GNSS-SDR with proper output handling"""
        env = os.environ.copy()
        env['DYLD_LIBRARY_PATH'] = '/usr/local/lib:' + env.get('DYLD_LIBRARY_PATH', '')
        env['PYTHONUNBUFFERED'] = '1'

        # Use parse_gnss_logs.py to parse and send to WebSocket
        parse_logs_script = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            'parse_gnss_logs.py'
        )

        # Create command that pipes through parse_gnss_logs
        cmd = f"gnss-sdr --config_file={self.config_path} 2>&1 | python3 -u {parse_logs_script}"

        self.gnss_process = subprocess.Popen(
            cmd,
            shell=True,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            bufsize=1
        )

        # Read GNSS-SDR output
        def read_gnss():
            try:
                for line in self.gnss_process.stdout:
                    if line.strip():
                        # Show important messages
                        if any(keyword in line for keyword in ['Tracking', 'Position', 'PRN', 'satellite', 'Fix']):
                            print(f"[GNSS-SDR] {line.strip()}", flush=True)
                        elif 'buffer_double_mapped' not in line:  # Filter out verbose warnings
                            print(f"[GNSS-SDR] {line.strip()}", flush=True)
            except Exception as e:
                print(f"[GNSS-SDR] Reader error: {e}")

        threading.Thread(target=read_gnss, daemon=True).start()
        return self.gnss_process.pid

    def start_progress_reporter(self):
        """Start the progress reporter for UI updates"""
        script_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            'send_continuous_progress.py'
        )

        if os.path.exists(script_path):
            env = os.environ.copy()
            env['PYTHONUNBUFFERED'] = '1'

            self.progress_process = subprocess.Popen(
                [sys.executable, '-u', script_path],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                env=env
            )
            print(f"   ✓ Progress reporter started (PID: {self.progress_process.pid})")

    def monitor_status(self):
        """Monitor and report status periodically"""
        def monitor():
            start_time = time.time()
            last_status = time.time()

            while self.running:
                try:
                    now = time.time()
                    if now - last_status >= 10:  # Every 10 seconds
                        elapsed = int(now - start_time)

                        # Check process status
                        streamer_alive = self.streamer_process and self.streamer_process.poll() is None
                        gnss_alive = self.gnss_process and self.gnss_process.poll() is None

                        print(f"\n📊 Status Update (T+{elapsed}s):")
                        print(f"   • SDRplay Streamer: {'✅ Running' if streamer_alive else '❌ Stopped'}")
                        print(f"   • GNSS-SDR: {'✅ Running' if gnss_alive else '❌ Stopped'}")

                        # Restart if needed
                        if not streamer_alive and self.running:
                            print("   ⚠️  Restarting SDRplay streamer...")
                            self.start_streamer()

                        if not gnss_alive and self.running:
                            print("   ⚠️  Restarting GNSS-SDR...")
                            self.start_gnss_sdr()

                        last_status = now

                    time.sleep(1)
                except Exception as e:
                    print(f"Monitor error: {e}")
                    time.sleep(5)

        self.monitor_thread = threading.Thread(target=monitor, daemon=True)
        self.monitor_thread.start()

    def run(self):
        """Main execution"""
        print("=" * 70)
        print("🛰️  CONTINUOUS GNSS PIPELINE - SDRplay Direct API")
        print("=" * 70)
        print()
        print("This pipeline will:")
        print("  • Stream continuously from SDRplay at 2.048 MSPS")
        print("  • Track GPS satellites in real-time")
        print("  • Send updates to WebSocket (port 8766)")
        print("  • Display tracking information")
        print("  • Restart automatically if components fail")
        print()

        # Clean up any existing FIFO
        if os.path.exists(self.fifo_path):
            os.remove(self.fifo_path)

        # Write configuration
        print("📝 Writing GNSS-SDR configuration...")
        self.write_gnss_config()
        print("   ✓ Configuration ready")

        # Start SDRplay streamer
        print("\n🎯 Starting SDRplay Direct API streamer...")
        streamer_pid = self.start_streamer()
        if not streamer_pid:
            print("   ❌ Failed to start streamer!")
            return
        print(f"   ✓ Streamer started (PID: {streamer_pid})")

        # Wait for FIFO
        print("\n⏳ Waiting for FIFO creation...")
        for i in range(20):
            if os.path.exists(self.fifo_path):
                print(f"   ✓ FIFO created: {self.fifo_path}")
                break
            time.sleep(0.5)
        else:
            print("   ❌ FIFO not created!")
            self.cleanup()
            return

        # Brief pause for initialization
        time.sleep(2)

        # Start GNSS-SDR
        print("\n📡 Starting GNSS-SDR...")
        gnss_pid = self.start_gnss_sdr()
        print(f"   ✓ GNSS-SDR started (PID: {gnss_pid})")

        # Start progress reporter for UI
        print("\n📊 Starting progress reporter for UI...")
        self.start_progress_reporter()

        print("\n" + "=" * 70)
        print("🚀 PIPELINE RUNNING")
        print("=" * 70)
        print()
        print("Data Flow:")
        print("  SDRplay → FIFO → GNSS-SDR → WebSocket → UI")
        print()
        print("Ports:")
        print("  • WebSocket: ws://localhost:8766")
        print("  • RTCM: tcp://localhost:2101")
        print("  • Monitor: udp://localhost:1234")
        print()
        print("Press Ctrl+C to stop")
        print("-" * 70)
        print()

        self.running = True

        # Start monitoring thread
        self.monitor_status()

        try:
            # Keep running until interrupted
            while self.running:
                time.sleep(1)

                # Check critical processes
                if self.streamer_process and self.streamer_process.poll() is not None:
                    print("\n⚠️  SDRplay streamer stopped unexpectedly!")
                    if self.running:
                        # Kill GNSS-SDR first since it can't work without streamer
                        if self.gnss_process:
                            try:
                                self.gnss_process.terminate()
                                self.gnss_process.wait(timeout=2)
                            except:
                                try:
                                    self.gnss_process.kill()
                                except:
                                    pass

                        # Clean up FIFO
                        if os.path.exists(self.fifo_path):
                            os.remove(self.fifo_path)

                        print("   Restarting pipeline in 3 seconds...")
                        time.sleep(3)

                        # Restart streamer first
                        streamer_pid = self.start_streamer()
                        if streamer_pid:
                            # Wait for FIFO
                            for i in range(10):
                                if os.path.exists(self.fifo_path):
                                    break
                                time.sleep(0.5)

                            # Then restart GNSS-SDR
                            time.sleep(1)
                            self.start_gnss_sdr()

                elif self.gnss_process and self.gnss_process.poll() is not None:
                    print("\n⚠️  GNSS-SDR stopped unexpectedly!")
                    if self.running:
                        print("   Restarting GNSS-SDR in 2 seconds...")
                        time.sleep(2)
                        self.start_gnss_sdr()

        except KeyboardInterrupt:
            print("\n\n👋 Shutdown requested by user")
        finally:
            self.cleanup()

    def cleanup(self):
        """Clean up all resources"""
        self.running = False

        # Stop processes gracefully
        for name, proc in [("Progress reporter", self.progress_process),
                          ("SDRplay streamer", self.streamer_process),
                          ("GNSS-SDR", self.gnss_process)]:
            if proc:
                try:
                    proc.terminate()
                    proc.wait(timeout=3)
                    print(f"   ✓ {name} stopped")
                except:
                    try:
                        proc.kill()
                        print(f"   ⚠️  {name} force killed")
                    except:
                        pass

        # Clean up files
        for path in [self.fifo_path, self.config_path]:
            if os.path.exists(path):
                try:
                    os.remove(path)
                except:
                    pass

        print("   ✓ Cleanup complete")
        print("\n👋 Goodbye!")

if __name__ == "__main__":
    pipeline = ContinuousGNSSPipeline()
    pipeline.run()