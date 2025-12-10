#!/usr/bin/env python3
"""
Unified GNSS pipeline - manages SDRplay streaming and GNSS-SDR as separate processes
This avoids library loading issues by running each component in its own process
"""

import os
import sys
import time
import signal
import subprocess
import threading
from pathlib import Path

class GNSSPipelineManager:
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
        print("\n\n🛑 Shutting down pipeline...")
        self.cleanup()
        sys.exit(0)

    def write_streamer_script(self):
        """Write the SDRplay streamer script"""
        script = '''#!/usr/bin/env python3
import sys
import os
import time
import numpy as np
import struct

os.environ['DYLD_LIBRARY_PATH'] = '/usr/local/lib:' + os.environ.get('DYLD_LIBRARY_PATH', '')

import SoapySDR

fifo_path = sys.argv[1] if len(sys.argv) > 1 else "/tmp/gnss_fifo"

# Setup FIFO
if os.path.exists(fifo_path):
    os.remove(fifo_path)
os.mkfifo(fifo_path)
print(f"Created FIFO at {fifo_path}")

# Setup SDRplay
sdr = SoapySDR.Device(dict(driver="sdrplay"))
sdr.setSampleRate(SoapySDR.SOAPY_SDR_RX, 0, 4e6)
sdr.setFrequency(SoapySDR.SOAPY_SDR_RX, 0, 1575.42e6)
if sdr.hasGainMode(SoapySDR.SOAPY_SDR_RX, 0):
    sdr.setGainMode(SoapySDR.SOAPY_SDR_RX, 0, False)
sdr.setGain(SoapySDR.SOAPY_SDR_RX, 0, 40)

stream = sdr.setupStream(SoapySDR.SOAPY_SDR_RX, SoapySDR.SOAPY_SDR_CF32)
sdr.activateStream(stream)

print("Waiting for GNSS-SDR to connect...")
fifo = os.open(fifo_path, os.O_WRONLY)
print("GNSS-SDR connected! Streaming...")

buff = np.zeros(65536, dtype=np.complex64)
samples = 0
last_report = time.time()

try:
    while True:
        sr = sdr.readStream(stream, [buff], 65536)
        if sr.ret > 0:
            data = buff[:sr.ret]
            interleaved = np.zeros(sr.ret * 2, dtype=np.float32)
            interleaved[0::2] = data.real
            interleaved[1::2] = data.imag
            os.write(fifo, interleaved.tobytes())
            samples += sr.ret

            if time.time() - last_report > 2:
                print(f"Streaming: {samples/1e6:.1f}M samples")
                last_report = time.time()
                samples = 0
except:
    pass
finally:
    sdr.deactivateStream(stream)
    sdr.closeStream(stream)
    os.close(fifo)
    if os.path.exists(fifo_path):
        os.remove(fifo_path)
'''
        script_path = "/tmp/sdrplay_streamer.py"
        with open(script_path, 'w') as f:
            f.write(script)
        os.chmod(script_path, 0o755)
        return script_path

    def write_gnss_config(self):
        """Write GNSS-SDR configuration"""
        config = """; GNSS-SDR configuration for FIFO input
[GNSS-SDR]
GNSS-SDR.internal_fs_sps=4000000

SignalSource.implementation=File_Signal_Source
SignalSource.filename=/tmp/gnss_fifo
SignalSource.item_type=gr_complex
SignalSource.sampling_frequency=4000000
SignalSource.samples=0
SignalSource.repeat=false
SignalSource.enable_throttle_control=false

SignalConditioner.implementation=Signal_Conditioner
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

Tracking_1C.implementation=GPS_L1_CA_DLL_PLL_Tracking
Tracking_1C.item_type=gr_complex
Tracking_1C.pll_bw_hz=40.0
Tracking_1C.dll_bw_hz=4.0

TelemetryDecoder_1C.implementation=GPS_L1_CA_Telemetry_Decoder
Observables.implementation=Hybrid_Observables

PVT.implementation=RTKLIB_PVT
PVT.positioning_mode=Single
PVT.output_rate_ms=1000
PVT.display_rate_ms=1000
PVT.nmea_dump_filename=./nmea_pvt.nmea
PVT.flag_rtcm_server=true
PVT.rinex_output_enabled=true
PVT.gpx_output_enabled=true
PVT.geojson_output_enabled=true
PVT.kml_output_enabled=true

Monitor.enable_monitor=true
Monitor.client_addresses=127.0.0.1
Monitor.udp_port=2101"""

        with open(self.config_path, 'w') as f:
            f.write(config)
        return self.config_path

    def check_sdrplay(self):
        """Check if SDRplay is available"""
        env = os.environ.copy()
        env['DYLD_LIBRARY_PATH'] = '/usr/local/lib:' + env.get('DYLD_LIBRARY_PATH', '')

        try:
            result = subprocess.run(
                ['SoapySDRUtil', '--find=driver=sdrplay'],
                env=env,
                capture_output=True,
                text=True,
                timeout=5
            )
            return 'sdrplay' in result.stdout.lower()
        except:
            return False

    def start_streamer(self, script_path):
        """Start SDRplay streamer process"""
        env = os.environ.copy()
        env['DYLD_LIBRARY_PATH'] = '/usr/local/lib:' + env.get('DYLD_LIBRARY_PATH', '')
        env['PYTHONPATH'] = '/opt/homebrew/lib/python3.14/site-packages:' + env.get('PYTHONPATH', '')

        self.streamer_process = subprocess.Popen(
            [sys.executable, script_path, self.fifo_path],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            bufsize=1
        )

        # Start thread to read output
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

        # Start thread to read output
        def read_output():
            for line in self.gnss_process.stdout:
                if line.strip():
                    print(f"[GNSS-SDR] {line.strip()}")

        threading.Thread(target=read_output, daemon=True).start()
        return self.gnss_process.pid

    def run(self):
        """Main execution"""
        print("=" * 60)
        print("🚀 GNSS-SDR Pipeline Manager")
        print("=" * 60)

        # Check SDRplay
        print("Checking SDRplay device...")
        if not self.check_sdrplay():
            print("❌ SDRplay device not found!")
            print("Please ensure:")
            print("  1. SDRplay device is connected")
            print("  2. SDRplay API service is running")
            return

        print("✅ SDRplay device detected")

        # Clean up any existing FIFO
        if os.path.exists(self.fifo_path):
            os.remove(self.fifo_path)

        # Prepare scripts and config
        print("\nPreparing pipeline...")
        streamer_script = self.write_streamer_script()
        self.write_gnss_config()
        print("✅ Configuration ready")

        # Start streamer
        print("\nStarting SDRplay streamer...")
        streamer_pid = self.start_streamer(streamer_script)
        print(f"✅ SDRplay streamer started (PID: {streamer_pid})")

        # Wait for FIFO to be created
        for i in range(10):
            if os.path.exists(self.fifo_path):
                break
            time.sleep(0.5)

        if not os.path.exists(self.fifo_path):
            print("❌ FIFO was not created!")
            self.cleanup()
            return

        # Start GNSS-SDR
        time.sleep(1)
        print("\nStarting GNSS-SDR...")
        gnss_pid = self.start_gnss_sdr()
        print(f"✅ GNSS-SDR started (PID: {gnss_pid})")

        print("\n" + "=" * 60)
        print("🟢 Pipeline Running")
        print("=" * 60)
        print("\nSDRplay → FIFO → GNSS-SDR")
        print(f"Monitor available on port 2101")
        print("\nPress Ctrl+C to stop\n")

        self.running = True

        try:
            # Monitor processes
            while self.running:
                # Check if processes are still running
                if self.streamer_process and self.streamer_process.poll() is not None:
                    print("\n❌ SDRplay streamer stopped unexpectedly!")
                    break

                if self.gnss_process and self.gnss_process.poll() is not None:
                    print("\n❌ GNSS-SDR stopped unexpectedly!")
                    break

                time.sleep(1)

        except KeyboardInterrupt:
            pass
        finally:
            self.cleanup()

    def cleanup(self):
        """Clean up all resources"""
        self.running = False

        print("\nCleaning up...")

        # Stop streamer
        if self.streamer_process:
            try:
                self.streamer_process.terminate()
                self.streamer_process.wait(timeout=3)
                print("✅ SDRplay streamer stopped")
            except:
                try:
                    self.streamer_process.kill()
                except:
                    pass

        # Stop GNSS-SDR
        if self.gnss_process:
            try:
                self.gnss_process.terminate()
                self.gnss_process.wait(timeout=3)
                print("✅ GNSS-SDR stopped")
            except:
                try:
                    self.gnss_process.kill()
                except:
                    pass

        # Clean up files
        for path in [self.fifo_path, self.config_path, "/tmp/sdrplay_streamer.py"]:
            if os.path.exists(path):
                try:
                    os.remove(path)
                except:
                    pass

        print("✅ Cleanup complete")

if __name__ == "__main__":
    manager = GNSSPipelineManager()
    manager.run()