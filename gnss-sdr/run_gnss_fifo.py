#!/usr/bin/env python3
"""
Unified script to run SDRplay -> FIFO -> GNSS-SDR pipeline
Everything in one script - just run it!
"""

import sys
import os

# Set library paths BEFORE any imports that might need them
if 'DYLD_LIBRARY_PATH' not in os.environ or '/usr/local/lib' not in os.environ['DYLD_LIBRARY_PATH']:
    print("Setting up library paths...")
    os.environ['DYLD_LIBRARY_PATH'] = '/usr/local/lib:' + os.environ.get('DYLD_LIBRARY_PATH', '')
    os.environ['PYTHONPATH'] = '/opt/homebrew/lib/python3.14/site-packages:' + os.environ.get('PYTHONPATH', '')

    # Re-execute with proper environment
    import subprocess
    env = os.environ.copy()
    result = subprocess.run([sys.executable] + sys.argv, env=env)
    sys.exit(result.returncode)

import time
import numpy as np
import signal
import subprocess
import threading
from pathlib import Path

try:
    import SoapySDR
except ImportError:
    print("ERROR: SoapySDR not found. Please install it first.")
    sys.exit(1)

class GNSSPipeline:
    def __init__(self):
        self.fifo_path = "/tmp/gnss_fifo"
        self.running = False
        self.sdr = None
        self.stream = None
        self.fifo_fd = None
        self.gnss_process = None

        # SDR parameters for GPS L1
        self.sample_rate = 4e6  # 4 MHz
        self.center_freq = 1575.42e6  # GPS L1
        self.gain = 40

        # Streaming parameters
        self.buffer_size = 65536

        # Setup signal handlers
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)

    def signal_handler(self, sig, frame):
        print("\nShutting down pipeline...")
        self.cleanup()
        sys.exit(0)

    def setup_fifo(self):
        """Create FIFO if it doesn't exist"""
        if os.path.exists(self.fifo_path):
            try:
                os.remove(self.fifo_path)
            except:
                pass

        try:
            os.mkfifo(self.fifo_path)
            print(f"✓ Created FIFO at {self.fifo_path}")
            return True
        except Exception as e:
            print(f"✗ Error creating FIFO: {e}")
            return False

    def write_gnss_config(self):
        """Write GNSS-SDR configuration file"""
        config = """; Auto-generated GNSS-SDR configuration for FIFO input
[GNSS-SDR]
GNSS-SDR.internal_fs_sps=4000000
GNSS-SDR.use_acquisition_resampler=false

; Signal Source - FIFO
SignalSource.implementation=File_Signal_Source
SignalSource.filename=/tmp/gnss_fifo
SignalSource.item_type=gr_complex
SignalSource.sampling_frequency=4000000
SignalSource.samples=0
SignalSource.repeat=false
SignalSource.enable_throttle_control=false

; Signal Conditioner
SignalConditioner.implementation=Signal_Conditioner
DataTypeAdapter.implementation=Pass_Through
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
InputFilter.sampling_frequency=4000000
InputFilter.IF=0
Resampler.implementation=Pass_Through
Resampler.sample_freq_in=4000000
Resampler.sample_freq_out=4000000

; Channels - GPS L1 C/A
Channels_1C.count=8
Channels.in_acquisition=8
Channel.signal=1C

; Acquisition
Acquisition_1C.implementation=GPS_L1_CA_PCPS_Acquisition
Acquisition_1C.item_type=gr_complex
Acquisition_1C.coherent_integration_time_ms=1
Acquisition_1C.pfa=0.01
Acquisition_1C.doppler_max=8000
Acquisition_1C.doppler_step=500
Acquisition_1C.bit_transition_flag=false
Acquisition_1C.max_dwells=1
Acquisition_1C.threshold=0.01
Acquisition_1C.blocking=true

; Tracking
Tracking_1C.implementation=GPS_L1_CA_DLL_PLL_Tracking
Tracking_1C.item_type=gr_complex
Tracking_1C.pll_bw_hz=40.0
Tracking_1C.dll_bw_hz=4.0
Tracking_1C.order=3
Tracking_1C.early_late_space_chips=0.5

; Telemetry Decoder
TelemetryDecoder_1C.implementation=GPS_L1_CA_Telemetry_Decoder

; Observables
Observables.implementation=Hybrid_Observables

; PVT
PVT.implementation=RTKLIB_PVT
PVT.positioning_mode=Single
PVT.iono_model=Broadcast
PVT.trop_model=Saastamoinen
PVT.output_rate_ms=1000
PVT.display_rate_ms=1000
PVT.nmea_dump_filename=./nmea_pvt.nmea
PVT.flag_rtcm_server=true
PVT.dump=false
PVT.dump_filename=./pvt.dat
PVT.rinex_version=3
PVT.rinex_output_enabled=true
PVT.gpx_output_enabled=true
PVT.geojson_output_enabled=true
PVT.kml_output_enabled=true

; Monitor
Monitor.enable_monitor=true
Monitor.decimation_factor=1
Monitor.client_addresses=127.0.0.1
Monitor.udp_port=2101

GNSS-SDR.enable_monitor=true"""

        config_path = "/tmp/gnss_fifo.conf"
        with open(config_path, 'w') as f:
            f.write(config)
        print(f"✓ Written GNSS-SDR config to {config_path}")
        return config_path

    def start_gnss_sdr(self, config_path):
        """Start GNSS-SDR process"""
        env = os.environ.copy()
        env['DYLD_LIBRARY_PATH'] = '/usr/local/lib:' + env.get('DYLD_LIBRARY_PATH', '')

        try:
            self.gnss_process = subprocess.Popen(
                ['gnss-sdr', '--config_file=' + config_path],
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                bufsize=1
            )

            # Start thread to read GNSS-SDR output
            threading.Thread(target=self.read_gnss_output, daemon=True).start()
            print(f"✓ Started GNSS-SDR (PID: {self.gnss_process.pid})")
            return True
        except Exception as e:
            print(f"✗ Failed to start GNSS-SDR: {e}")
            return False

    def read_gnss_output(self):
        """Read and display GNSS-SDR output"""
        if self.gnss_process:
            for line in self.gnss_process.stdout:
                if line.strip():
                    print(f"[GNSS-SDR] {line.strip()}")

    def setup_sdr(self):
        """Initialize SDRplay device"""
        try:
            # Find SDRplay device
            results = SoapySDR.Device.enumerate()
            sdrplay_found = False

            for result in results:
                if 'driver' in result and 'sdrplay' in result['driver'].lower():
                    sdrplay_found = True
                    break

            if not sdrplay_found:
                print("✗ No SDRplay device found")
                return False

            # Create device
            self.sdr = SoapySDR.Device(dict(driver="sdrplay"))
            print("✓ SDRplay device initialized")

            # Configure device
            self.sdr.setSampleRate(SoapySDR.SOAPY_SDR_RX, 0, self.sample_rate)
            self.sdr.setFrequency(SoapySDR.SOAPY_SDR_RX, 0, self.center_freq)

            # Set gain
            if self.sdr.hasGainMode(SoapySDR.SOAPY_SDR_RX, 0):
                self.sdr.setGainMode(SoapySDR.SOAPY_SDR_RX, 0, False)
            self.sdr.setGain(SoapySDR.SOAPY_SDR_RX, 0, self.gain)

            print(f"✓ SDR configured: {self.sample_rate/1e6} MHz @ {self.center_freq/1e6} MHz")

            # Setup stream
            self.stream = self.sdr.setupStream(SoapySDR.SOAPY_SDR_RX, SoapySDR.SOAPY_SDR_CF32)
            self.sdr.activateStream(self.stream)
            print("✓ SDR stream activated")

            return True

        except Exception as e:
            print(f"✗ Error setting up SDR: {e}")
            return False

    def run(self):
        """Main execution"""
        print("=" * 60)
        print("GNSS-SDR Pipeline - All-in-One")
        print("=" * 60)

        # Check SDRplay availability first
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
            if 'sdrplay' not in result.stdout.lower():
                print("✗ SDRplay not detected. Check API service and device connection.")
                return
        except Exception as e:
            print(f"✗ Could not check SDRplay: {e}")
            return

        print("✓ SDRplay device available")

        # Setup everything
        if not self.setup_fifo():
            return

        config_path = self.write_gnss_config()

        if not self.setup_sdr():
            return

        # Start GNSS-SDR
        if not self.start_gnss_sdr(config_path):
            return

        # Wait a bit for GNSS-SDR to initialize
        time.sleep(3)

        # Open FIFO for writing
        print("Opening FIFO for writing...")
        try:
            self.fifo_fd = os.open(self.fifo_path, os.O_WRONLY)
            print("✓ FIFO connected to GNSS-SDR")
        except Exception as e:
            print(f"✗ Error opening FIFO: {e}")
            return

        # Start streaming
        self.running = True
        samples_written = 0
        start_time = time.time()
        status_time = time.time()

        # Create receive buffer
        buff = np.zeros(self.buffer_size, dtype=np.complex64)

        print("\n" + "=" * 60)
        print("STREAMING ACTIVE - Press Ctrl+C to stop")
        print("=" * 60 + "\n")

        try:
            while self.running:
                # Read from SDR
                sr = self.sdr.readStream(self.stream, [buff], self.buffer_size)

                if sr.ret > 0:
                    # Convert complex64 to interleaved float32
                    data = buff[:sr.ret]
                    interleaved = np.zeros(sr.ret * 2, dtype=np.float32)
                    interleaved[0::2] = data.real
                    interleaved[1::2] = data.imag

                    # Write to FIFO
                    try:
                        bytes_data = interleaved.tobytes()
                        os.write(self.fifo_fd, bytes_data)
                        samples_written += sr.ret

                        # Status update every 2 seconds
                        if time.time() - status_time > 2.0:
                            rate = samples_written / (time.time() - start_time)
                            print(f"[Streamer] {rate/1e6:.2f} MSps | Total: {samples_written/1e6:.1f}M samples")
                            status_time = time.time()

                    except BrokenPipeError:
                        print("\n✗ GNSS-SDR disconnected from FIFO")
                        break
                    except Exception as e:
                        print(f"\n✗ Write error: {e}")
                        break

                elif sr.ret == SoapySDR.SOAPY_SDR_TIMEOUT:
                    print("T", end="", flush=True)
                elif sr.ret == SoapySDR.SOAPY_SDR_OVERFLOW:
                    print("O", end="", flush=True)
                else:
                    print(f"\n✗ Stream error: {sr.ret}")

                # Check if GNSS-SDR is still running
                if self.gnss_process and self.gnss_process.poll() is not None:
                    print("\n✗ GNSS-SDR process terminated")
                    break

        except KeyboardInterrupt:
            print("\n\nStopping pipeline...")
        finally:
            self.cleanup()

    def cleanup(self):
        """Clean up all resources"""
        self.running = False

        # Close SDR stream
        if self.stream and self.sdr:
            try:
                self.sdr.deactivateStream(self.stream)
                self.sdr.closeStream(self.stream)
                print("✓ SDR stream closed")
            except:
                pass

        # Close FIFO
        if self.fifo_fd:
            try:
                os.close(self.fifo_fd)
            except:
                pass

        # Stop GNSS-SDR
        if self.gnss_process:
            try:
                self.gnss_process.terminate()
                self.gnss_process.wait(timeout=5)
                print("✓ GNSS-SDR stopped")
            except subprocess.TimeoutExpired:
                self.gnss_process.kill()
                print("✓ GNSS-SDR killed")
            except:
                pass

        # Remove FIFO
        if os.path.exists(self.fifo_path):
            try:
                os.remove(self.fifo_path)
                print("✓ FIFO removed")
            except:
                pass

        # Remove temp config
        if os.path.exists("/tmp/gnss_fifo.conf"):
            try:
                os.remove("/tmp/gnss_fifo.conf")
            except:
                pass

        print("✓ Cleanup complete")

if __name__ == "__main__":
    # Set library paths
    os.environ['DYLD_LIBRARY_PATH'] = '/usr/local/lib:' + os.environ.get('DYLD_LIBRARY_PATH', '')
    os.environ['PYTHONPATH'] = '/opt/homebrew/lib/python3.14/site-packages:' + os.environ.get('PYTHONPATH', '')

    pipeline = GNSSPipeline()
    pipeline.run()