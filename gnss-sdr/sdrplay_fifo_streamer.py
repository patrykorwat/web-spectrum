#!/usr/bin/env python3
"""
Stream SDRplay data to FIFO using Direct API
"""
import os
import sys
import time
import numpy as np
import signal

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sdrplay_direct import SDRplayDevice

class FIFOStreamer:
    def __init__(self, fifo_path="/tmp/gnss_fifo"):
        self.fifo_path = fifo_path
        self.fifo_fd = None
        self.sdr = None
        self.samples_written = 0
        self.last_report = time.time()
        self.running = True

    def data_callback(self, samples):
        """Callback from SDRplay - write to FIFO"""
        if self.fifo_fd is not None and self.running:
            # Convert complex64 to interleaved float32 for GNSS-SDR
            interleaved = np.zeros(len(samples) * 2, dtype=np.float32)
            interleaved[0::2] = samples.real
            interleaved[1::2] = samples.imag

            try:
                os.write(self.fifo_fd, interleaved.tobytes())
                self.samples_written += len(samples)

                # Status report every 2 seconds
                if time.time() - self.last_report > 2.0:
                    print(f"[Streamer] {self.samples_written/1e6:.1f}M samples")
                    self.last_report = time.time()
                    self.samples_written = 0
            except BrokenPipeError:
                print("[Streamer] GNSS-SDR disconnected")
                self.running = False
            except Exception as e:
                print(f"[Streamer] Write error: {e}")
                self.running = False

    def run(self):
        # Create FIFO
        if os.path.exists(self.fifo_path):
            os.remove(self.fifo_path)
        os.mkfifo(self.fifo_path)
        print(f"[Streamer] Created FIFO at {self.fifo_path}")

        # Initialize SDRplay
        try:
            print("[Streamer] Initializing SDRplay device...")
            self.sdr = SDRplayDevice()

            # Don't reconfigure - device already has correct defaults
            # Changing parameters after init seems to cause issues
            print("[Streamer] Using default configuration...")

            print("[Streamer] SDRplay ready: 2.048 MHz @ 1575.42 MHz, Gain: 40")
            print("[Streamer] READY - Waiting for GNSS-SDR to connect...")
            sys.stdout.flush()

            # Open FIFO with timeout by trying in a loop
            # This prevents indefinite blocking
            fifo_opened = False
            max_wait = 30  # 30 seconds timeout
            wait_time = 0

            while not fifo_opened and wait_time < max_wait:
                try:
                    # Try to open with non-blocking flag first to check if reader exists
                    import fcntl
                    self.fifo_fd = os.open(self.fifo_path, os.O_WRONLY | os.O_NONBLOCK)
                    # Switch back to blocking mode for writing
                    flags = fcntl.fcntl(self.fifo_fd, fcntl.F_GETFL)
                    fcntl.fcntl(self.fifo_fd, fcntl.F_SETFL, flags & ~os.O_NONBLOCK)
                    fifo_opened = True
                    print("[Streamer] GNSS-SDR connected!")
                except OSError as e:
                    # ENXIO means no reader yet
                    time.sleep(0.5)
                    wait_time += 0.5

            if not fifo_opened:
                print("[Streamer] TIMEOUT: GNSS-SDR did not connect within 30 seconds")
                return

            # Start streaming
            self.sdr.start_streaming(self.data_callback)
            print("[Streamer] Streaming active")
            sys.stdout.flush()

            # Keep running
            try:
                while self.running:
                    time.sleep(0.5)
            except KeyboardInterrupt:
                print("\n[Streamer] Stopping on user request...")

        except Exception as e:
            print(f"[Streamer] ERROR: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self.stop()

    def stop(self):
        print("[Streamer] Shutting down...")
        self.running = False

        if self.sdr:
            try:
                self.sdr.stop_streaming()
                print("[Streamer] Stream stopped")
            except:
                pass

        if self.fifo_fd:
            try:
                os.close(self.fifo_fd)
            except:
                pass

        if os.path.exists(self.fifo_path):
            try:
                os.remove(self.fifo_path)
                print(f"[Streamer] Removed FIFO")
            except:
                pass

def signal_handler(sig, frame):
    print("\n[Streamer] Received signal, exiting...")
    sys.exit(0)

if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    fifo_path = sys.argv[1] if len(sys.argv) > 1 else "/tmp/gnss_fifo"

    streamer = FIFOStreamer(fifo_path)
    streamer.run()