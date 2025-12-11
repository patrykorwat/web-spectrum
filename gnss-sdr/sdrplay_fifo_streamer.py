#!/usr/bin/env python3
"""
Stream SDRplay data to FIFO using Direct API
"""
import os
import sys
import time
import numpy as np
import signal
import queue
import threading

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sdrplay_direct import SDRplayDevice

class FIFOStreamer:
    def __init__(self, fifo_path="/tmp/gnss_fifo"):
        self.fifo_path = fifo_path
        self.fifo_fd = None
        self.sdr = None
        self.samples_written = 0
        self.samples_dropped = 0
        self.last_report = time.time()
        self.running = True
        self.sample_queue = queue.Queue(maxsize=100)  # Buffer up to 100 chunks
        self.writer_thread = None
        self.callback_count = 0
        self.last_callback_time = time.time()
        self.last_diagnostic = time.time()

    def data_callback(self, samples):
        """Callback from SDRplay - put samples in queue (never blocks)"""
        if self.running:
            self.callback_count += 1
            self.last_callback_time = time.time()
            try:
                # Try to put in queue without blocking
                self.sample_queue.put_nowait(samples.copy())
            except queue.Full:
                # Queue full - drop samples
                self.samples_dropped += len(samples)
                if not hasattr(self, 'drop_warned') or time.time() - getattr(self, 'drop_warned', 0) > 5.0:
                    print(f"[Streamer] ⚠️  Queue full - dropping samples")
                    self.drop_warned = time.time()

    def fifo_writer_thread(self):
        """Separate thread that writes to FIFO (can block safely)"""
        while self.running:
            try:
                # Get samples from queue (blocks if empty)
                samples = self.sample_queue.get(timeout=0.5)

                if samples is None:  # Poison pill
                    break

                # Write samples as gr_complex (complex64 = numpy complex64)
                # GNSS-SDR expects gr_complex which is native complex64 format
                # No need to convert to interleaved - numpy complex64 is already interleaved I/Q
                samples_bytes = samples.astype(np.complex64).tobytes()

                # Write to FIFO (blocking is OK in this thread)
                os.write(self.fifo_fd, samples_bytes)
                self.samples_written += len(samples)

                # Status report every 2 seconds
                if time.time() - self.last_report > 2.0:
                    queue_size = self.sample_queue.qsize()
                    print(f"[Streamer] {self.samples_written/1e6:.1f}M samples written, queue: {queue_size}/100")
                    self.last_report = time.time()
                    self.samples_written = 0

            except queue.Empty:
                continue
            except BrokenPipeError:
                print("[Streamer] GNSS-SDR disconnected")
                self.running = False
                break
            except Exception as e:
                print(f"[Streamer] Write error: {e}")
                self.running = False
                break

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
                    # Open FIFO - use standard blocking I/O
                    # The callback happens in a separate thread, so blocking is OK
                    self.fifo_fd = os.open(self.fifo_path, os.O_WRONLY)
                    fifo_opened = True
                    print("[Streamer] GNSS-SDR connected!")
                except OSError as e:
                    # ENXIO means no reader yet
                    time.sleep(0.5)
                    wait_time += 0.5

            if not fifo_opened:
                print("[Streamer] TIMEOUT: GNSS-SDR did not connect within 30 seconds")
                return

            # Start FIFO writer thread
            self.writer_thread = threading.Thread(target=self.fifo_writer_thread, daemon=True)
            self.writer_thread.start()
            print("[Streamer] FIFO writer thread started")

            # Start streaming
            self.sdr.start_streaming(self.data_callback)
            print("[Streamer] Streaming active")
            sys.stdout.flush()

            # Keep running with diagnostic logging
            try:
                while self.running:
                    time.sleep(0.5)

                    # Print diagnostics every 10 seconds
                    if time.time() - self.last_diagnostic > 10.0:
                        queue_size = self.sample_queue.qsize()
                        thread_alive = self.writer_thread.is_alive() if self.writer_thread else False
                        time_since_callback = time.time() - self.last_callback_time

                        print(f"[Streamer] Diagnostic: writer_thread={thread_alive}, queue={queue_size}/100, "
                              f"callbacks={self.callback_count}, last_callback={time_since_callback:.1f}s ago, "
                              f"dropped={self.samples_dropped}")
                        self.last_diagnostic = time.time()
                        self.callback_count = 0  # Reset counter

                        # Check if writer thread died
                        if not thread_alive:
                            print("[Streamer] ⚠️  Writer thread has DIED! FIFO likely broken.")
                            self.running = False
                            break

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