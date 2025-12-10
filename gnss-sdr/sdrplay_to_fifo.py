#!/usr/bin/env python3
"""
Stream SDRplay data directly to a FIFO for GNSS-SDR consumption
"""

import sys
import os
import time
import numpy as np
import signal
import struct
from pathlib import Path

try:
    import SoapySDR
except ImportError:
    print("ERROR: SoapySDR not found. Please install it first.")
    sys.exit(1)

class SDRplayToFIFO:
    def __init__(self, fifo_path="/tmp/gnss_fifo"):
        self.fifo_path = fifo_path
        self.running = False
        self.sdr = None
        self.stream = None
        self.fifo_fd = None

        # SDR parameters for GPS L1
        self.sample_rate = 4e6  # 4 MHz
        self.center_freq = 1575.42e6  # GPS L1
        self.gain = 40

        # Streaming parameters
        self.buffer_size = 65536  # Larger buffer for efficiency

    def setup_fifo(self):
        """Create FIFO if it doesn't exist"""
        if os.path.exists(self.fifo_path):
            try:
                os.remove(self.fifo_path)
            except:
                pass

        try:
            os.mkfifo(self.fifo_path)
            print(f"Created FIFO at {self.fifo_path}")
        except Exception as e:
            print(f"Error creating FIFO: {e}")
            return False

        return True

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
                print("ERROR: No SDRplay device found")
                return False

            # Create device
            self.sdr = SoapySDR.Device(dict(driver="sdrplay"))
            print("SDRplay device initialized")

            # Configure device
            self.sdr.setSampleRate(SoapySDR.SOAPY_SDR_RX, 0, self.sample_rate)
            self.sdr.setFrequency(SoapySDR.SOAPY_SDR_RX, 0, self.center_freq)

            # Set gain
            if self.sdr.hasGainMode(SoapySDR.SOAPY_SDR_RX, 0):
                self.sdr.setGainMode(SoapySDR.SOAPY_SDR_RX, 0, False)  # Manual gain
            self.sdr.setGain(SoapySDR.SOAPY_SDR_RX, 0, self.gain)

            print(f"SDR configured: {self.sample_rate/1e6} MHz sample rate, {self.center_freq/1e6} MHz center freq")

            # Setup stream
            self.stream = self.sdr.setupStream(SoapySDR.SOAPY_SDR_RX, SoapySDR.SOAPY_SDR_CF32)
            self.sdr.activateStream(self.stream)
            print("Stream activated")

            return True

        except Exception as e:
            print(f"Error setting up SDR: {e}")
            return False

    def run(self):
        """Main streaming loop"""
        if not self.setup_fifo():
            return

        if not self.setup_sdr():
            return

        # Open FIFO for writing (will block until reader connects)
        print(f"Waiting for GNSS-SDR to connect to FIFO...")
        try:
            self.fifo_fd = os.open(self.fifo_path, os.O_WRONLY)
            print("GNSS-SDR connected!")
        except Exception as e:
            print(f"Error opening FIFO: {e}")
            return

        self.running = True
        samples_written = 0
        start_time = time.time()

        # Create receive buffer
        buff = np.zeros(self.buffer_size, dtype=np.complex64)

        print("Streaming data to FIFO...")

        try:
            while self.running:
                # Read from SDR
                sr = self.sdr.readStream(self.stream, [buff], self.buffer_size)

                if sr.ret > 0:
                    # Convert complex64 to interleaved float32 for GNSS-SDR
                    # GNSS-SDR expects: I0, Q0, I1, Q1, ...
                    data = buff[:sr.ret]
                    interleaved = np.zeros(sr.ret * 2, dtype=np.float32)
                    interleaved[0::2] = data.real
                    interleaved[1::2] = data.imag

                    # Write to FIFO
                    try:
                        bytes_data = interleaved.tobytes()
                        os.write(self.fifo_fd, bytes_data)
                        samples_written += sr.ret

                        # Status update every second
                        if time.time() - start_time > 1.0:
                            rate = samples_written / (time.time() - start_time)
                            print(f"Streaming: {rate/1e6:.2f} MSps, total: {samples_written/1e6:.1f}M samples")
                            start_time = time.time()
                            samples_written = 0

                    except BrokenPipeError:
                        print("GNSS-SDR disconnected from FIFO")
                        break
                    except Exception as e:
                        print(f"Write error: {e}")
                        break

                elif sr.ret == SoapySDR.SOAPY_SDR_TIMEOUT:
                    print("Stream timeout")
                elif sr.ret == SoapySDR.SOAPY_SDR_OVERFLOW:
                    print("O", end="", flush=True)  # Overflow indicator
                else:
                    print(f"Stream error: {sr.ret}")

        except KeyboardInterrupt:
            print("\nStopping...")
        finally:
            self.cleanup()

    def cleanup(self):
        """Clean up resources"""
        self.running = False

        if self.stream and self.sdr:
            try:
                self.sdr.deactivateStream(self.stream)
                self.sdr.closeStream(self.stream)
                print("Stream closed")
            except:
                pass

        if self.fifo_fd:
            try:
                os.close(self.fifo_fd)
            except:
                pass

        # Remove FIFO
        if os.path.exists(self.fifo_path):
            try:
                os.remove(self.fifo_path)
                print(f"Removed FIFO {self.fifo_path}")
            except:
                pass

    def stop(self):
        """Stop streaming"""
        self.running = False

def signal_handler(sig, frame):
    print("\nReceived signal, stopping...")
    sys.exit(0)

if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Optional: specify custom FIFO path
    fifo_path = sys.argv[1] if len(sys.argv) > 1 else "/tmp/gnss_fifo"

    streamer = SDRplayToFIFO(fifo_path)
    streamer.run()