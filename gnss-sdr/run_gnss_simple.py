#!/usr/bin/env python3
"""
Simple GNSS Pipeline using direct SDRplay API
"""

import os
import sys
import time
import signal
import subprocess
import threading
import numpy as np
from pathlib import Path

# Add path for local imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

class SimpleGNSSPipeline:
    def __init__(self):
        self.fifo_path = "/tmp/gnss_fifo"
        self.config_path = "/tmp/gnss_fifo.conf"
        self.streamer_process = None
        self.gnss_process = None
        self.running = False

        # Setup signal handlers
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)

    def signal_handler(self, sig, frame):
        print("\n\nShutting down pipeline...")
        self.cleanup()
        sys.exit(0)

    def write_gnss_config(self):
        """Write minimal GNSS-SDR configuration"""
        config = """; GNSS-SDR config for FIFO input from SDRplay
[GNSS-SDR]
GNSS-SDR.internal_fs_sps=2048000

; Use Fifo_Signal_Source (dedicated FIFO support in GNSS-SDR)
SignalSource.implementation=Fifo_Signal_Source
SignalSource.filename=/tmp/gnss_fifo
SignalSource.sample_type=gr_complex
SignalSource.sampling_frequency=2048000
SignalSource.dump=false

SignalConditioner.implementation=Pass_Through
DataTypeAdapter.implementation=Pass_Through
InputFilter.implementation=Pass_Through
Resampler.implementation=Pass_Through

Channels_1C.count=8
Channels.in_acquisition=8
Channel.signal=1C

Acquisition_1C.implementation=GPS_L1_CA_PCPS_Acquisition
Acquisition_1C.item_type=gr_complex
Acquisition_1C.coherent_integration_time_ms=1
Acquisition_1C.pfa=0.01
Acquisition_1C.doppler_max=8000
Acquisition_1C.doppler_step=500
Acquisition_1C.blocking=true
Acquisition_1C.dump=false

Tracking_1C.implementation=GPS_L1_CA_DLL_PLL_Tracking
Tracking_1C.item_type=gr_complex
Tracking_1C.pll_bw_hz=40.0
Tracking_1C.dll_bw_hz=4.0
Tracking_1C.dump=false

TelemetryDecoder_1C.implementation=GPS_L1_CA_Telemetry_Decoder
TelemetryDecoder_1C.dump=false

Observables.implementation=Hybrid_Observables
Observables.dump=false

PVT.implementation=RTKLIB_PVT
PVT.positioning_mode=Single
PVT.output_rate_ms=1000
PVT.display_rate_ms=1000
PVT.nmea_dump_filename=./nmea_pvt.nmea
PVT.flag_rtcm_server=true
PVT.rtcm_tcp_port=2101
PVT.dump=false

Monitor.enable_monitor=true
Monitor.decimation_factor=1
Monitor.client_addresses=127.0.0.1
Monitor.udp_port=2101"""

        with open(self.config_path, 'w') as f:
            f.write(config)
        return self.config_path

    def start_direct_streamer(self):
        """Start the direct API streamer using standalone script"""
        script_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            'sdrplay_fifo_streamer.py'
        )

        if not os.path.exists(script_path):
            print(f"ERROR: {script_path} not found!")
            return None

        # Start the streamer process with explicit environment
        env = os.environ.copy()
        env['PYTHONUNBUFFERED'] = '1'  # Force unbuffered output

        self.streamer_process = subprocess.Popen(
            [sys.executable, '-u', script_path, self.fifo_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            bufsize=1,
            env=env
        )

        # Read output in thread
        def read_output():
            try:
                for line in self.streamer_process.stdout:
                    if line.strip():
                        print(line.strip())
                        sys.stdout.flush()
            except Exception as e:
                print(f"Error reading streamer output: {e}")

        threading.Thread(target=read_output, daemon=True).start()

        # Give it a moment to start
        time.sleep(0.5)

        # Check if process is still running
        if self.streamer_process.poll() is not None:
            print(f"WARNING: Streamer process exited immediately with code {self.streamer_process.returncode}")
            return None

        return self.streamer_process.pid

    def start_direct_streamer_OLD(self):
        """OLD - Start the direct API streamer"""
        script = '''#!/usr/bin/env python3
import os
import sys
import time
import numpy as np
import signal

# Add path for sdrplay_direct import
sys.path.insert(0, '{script_dir}')

from sdrplay_direct import SDRplayDevice

class FIFOStreamer_OLD:
    def __init__(self):
        self.fifo_path = "/tmp/gnss_fifo"
        self.fifo_fd = None
        self.sdr = None
        self.samples_written = 0
        self.last_report = time.time()

    def data_callback(self, samples):
        """Callback from SDRplay - write to FIFO"""
        if self.fifo_fd is not None:
            # Convert complex64 to interleaved float32 for GNSS-SDR
            interleaved = np.zeros(len(samples) * 2, dtype=np.float32)
            interleaved[0::2] = samples.real
            interleaved[1::2] = samples.imag

            try:
                os.write(self.fifo_fd, interleaved.tobytes())
                self.samples_written += len(samples)

                # Status report every 2 seconds
                if time.time() - self.last_report > 2.0:
                    print(f"Streaming: {{self.samples_written/1e6:.1f}}M samples")
                    self.last_report = time.time()
                    self.samples_written = 0
            except BrokenPipeError:
                print("GNSS-SDR disconnected")
                self.stop()
            except Exception as e:
                print(f"Write error: {{e}}")

    def run(self):
        # Create FIFO
        if os.path.exists(self.fifo_path):
            os.remove(self.fifo_path)
        os.mkfifo(self.fifo_path)
        print(f"Created FIFO at {{self.fifo_path}}")

        # Initialize SDRplay
        try:
            self.sdr = SDRplayDevice()
            self.sdr.set_frequency(1575.42e6)  # GPS L1
            self.sdr.set_sample_rate(4e6)      # 4 MHz
            self.sdr.set_gain(40)
            print("SDRplay initialized: 4 MHz @ 1575.42 MHz")

            # Open FIFO (blocks until reader connects)
            print("Waiting for GNSS-SDR to connect...")
            self.fifo_fd = os.open(self.fifo_path, os.O_WRONLY)
            print("GNSS-SDR connected! Starting stream...")

            # Start streaming
            self.sdr.start_streaming(self.data_callback)

            # Keep running
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                pass

        except Exception as e:
            print(f"Error: {{e}}")
        finally:
            self.stop()

    def stop(self):
        if self.sdr:
            self.sdr.stop_streaming()
        if self.fifo_fd:
            try:
                os.close(self.fifo_fd)
            except:
                pass
        if os.path.exists(self.fifo_path):
            try:
                os.remove(self.fifo_path)
            except:
                pass

if __name__ == "__main__":
    signal.signal(signal.SIGINT, lambda s,f: sys.exit(0))
    streamer = FIFOStreamer()
    streamer.run()
'''.format(script_dir=os.path.dirname(os.path.abspath(__file__)))

        script_path = "/tmp/direct_streamer.py"
        with open(script_path, 'w') as f:
            f.write(script)
        os.chmod(script_path, 0o755)

        # Start the streamer process
        self.streamer_process = subprocess.Popen(
            [sys.executable, script_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            bufsize=1
        )

        # Read output in thread
        def read_output():
            for line in self.streamer_process.stdout:
                if line.strip():
                    print(f"[SDRplay] {line.strip()}")

        threading.Thread(target=read_output, daemon=True).start()
        return self.streamer_process.pid

    def start_gnss_sdr(self):
        """Start GNSS-SDR process"""
        env = os.environ.copy()
        env['DYLD_LIBRARY_PATH'] = '/usr/local/lib:' + env.get('DYLD_LIBRARY_PATH', '')

        self.gnss_process = subprocess.Popen(
            ['gnss-sdr', '--config_file=' + self.config_path],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            bufsize=1
        )

        # Read output in thread
        def read_output():
            for line in self.gnss_process.stdout:
                if line.strip():
                    # Filter out verbose messages
                    if not any(skip in line for skip in ['Tracking_1C', 'Telemetry', 'dll_pll']):
                        print(f"[GNSS-SDR] {line.strip()}")

        threading.Thread(target=read_output, daemon=True).start()
        return self.gnss_process.pid

    def run(self):
        """Main execution"""
        print("=" * 60)
        print("GNSS Pipeline - Direct SDRplay API")
        print("=" * 60)

        # Check for sdrplay_direct.py
        if not os.path.exists(os.path.join(os.path.dirname(__file__), 'sdrplay_direct.py')):
            print("ERROR: sdrplay_direct.py not found!")
            print("This script requires the direct API implementation.")
            return

        # Clean up any existing FIFO
        if os.path.exists(self.fifo_path):
            os.remove(self.fifo_path)

        # Prepare config
        print("\nPreparing configuration...")
        self.write_gnss_config()
        print("✓ Configuration ready")

        # Start direct API streamer
        print("\nStarting SDRplay (Direct API)...")
        streamer_pid = self.start_direct_streamer()
        if streamer_pid is None:
            print("ERROR: Failed to start streamer!")
            self.cleanup()
            return
        print(f"✓ SDRplay streamer started (PID: {streamer_pid})")

        # Wait for FIFO to be created
        print("Waiting for FIFO creation...")
        fifo_created = False
        for i in range(20):  # 10 seconds max
            if os.path.exists(self.fifo_path):
                fifo_created = True
                break
            time.sleep(0.5)

        if not fifo_created:
            print("ERROR: FIFO was not created!")
            self.cleanup()
            return

        print("✓ FIFO created")

        # Wait a bit more for SDRplay to initialize
        print("Waiting for SDRplay initialization...")
        time.sleep(2)

        # Start GNSS-SDR (it will open the FIFO for reading)
        print("\nStarting GNSS-SDR...")
        gnss_pid = self.start_gnss_sdr()
        print(f"✓ GNSS-SDR started (PID: {gnss_pid})")

        print("\n" + "=" * 60)
        print("Pipeline Running")
        print("=" * 60)
        print("\nSDRplay (Direct API) → FIFO → GNSS-SDR")
        print("Monitor: port 2101")
        print("\nPress Ctrl+C to stop\n")

        self.running = True

        try:
            while self.running:
                # Check processes
                if self.streamer_process and self.streamer_process.poll() is not None:
                    print("\nSDRplay streamer stopped")
                    break

                if self.gnss_process and self.gnss_process.poll() is not None:
                    print("\nGNSS-SDR stopped")
                    break

                time.sleep(1)

        except KeyboardInterrupt:
            pass
        finally:
            self.cleanup()

    def cleanup(self):
        """Clean up"""
        self.running = False

        if self.streamer_process:
            try:
                self.streamer_process.terminate()
                self.streamer_process.wait(timeout=3)
                print("✓ Streamer stopped")
            except:
                try:
                    self.streamer_process.kill()
                except:
                    pass

        if self.gnss_process:
            try:
                self.gnss_process.terminate()
                self.gnss_process.wait(timeout=3)
                print("✓ GNSS-SDR stopped")
            except:
                try:
                    self.gnss_process.kill()
                except:
                    pass

        # Clean up files
        for path in [self.fifo_path, self.config_path, "/tmp/direct_streamer.py"]:
            if os.path.exists(path):
                try:
                    os.remove(path)
                except:
                    pass

        print("✓ Cleanup complete")

if __name__ == "__main__":
    pipeline = SimpleGNSSPipeline()
    pipeline.run()