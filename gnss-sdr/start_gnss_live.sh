#!/bin/bash
# Robust GNSS pipeline starter with proper FIFO coordination

set -e

FIFO_PATH="/tmp/gnss_fifo"
CONFIG_PATH="/tmp/gnss_live.conf"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Cleanup function
cleanup() {
    echo ""
    echo "🛑 Shutting down..."

    # Kill all child processes
    jobs -p | xargs -r kill 2>/dev/null || true

    # Kill specific processes
    pkill -f "sdrplay_fifo_streamer" 2>/dev/null || true
    pkill -f "gnss-sdr.*gnss_live" 2>/dev/null || true
    pkill -f "parse_gnss_logs" 2>/dev/null || true
    pkill -f "send_continuous_progress" 2>/dev/null || true

    # Remove FIFO
    rm -f "$FIFO_PATH" 2>/dev/null || true

    echo "✓ Cleanup complete"
    exit 0
}

trap cleanup SIGINT SIGTERM EXIT

# Write GNSS-SDR configuration
cat > "$CONFIG_PATH" << 'EOF'
; GNSS-SDR Live Configuration
[GNSS-SDR]
GNSS-SDR.internal_fs_sps=2048000

; Signal Source - FIFO
SignalSource.implementation=Fifo_Signal_Source
SignalSource.filename=/tmp/gnss_fifo
SignalSource.sample_type=gr_complex
SignalSource.dump=false

; Signal Conditioning
SignalConditioner.implementation=Pass_Through

; GPS L1 C/A Channels
Channels_1C.count=12
Channels.in_acquisition=12
Channel.signal=1C

; Acquisition
Acquisition_1C.implementation=GPS_L1_CA_PCPS_Acquisition
Acquisition_1C.item_type=gr_complex
Acquisition_1C.coherent_integration_time_ms=1
Acquisition_1C.pfa=0.01
Acquisition_1C.doppler_max=10000
Acquisition_1C.doppler_step=250
Acquisition_1C.threshold=0.005

; Tracking
Tracking_1C.implementation=GPS_L1_CA_DLL_PLL_Tracking
Tracking_1C.item_type=gr_complex
Tracking_1C.pll_bw_hz=35.0
Tracking_1C.dll_bw_hz=2.0

; Telemetry
TelemetryDecoder_1C.implementation=GPS_L1_CA_Telemetry_Decoder

; Observables
Observables.implementation=Hybrid_Observables

; PVT
PVT.implementation=RTKLIB_PVT
PVT.positioning_mode=Single
PVT.output_rate_ms=1000
PVT.display_rate_ms=500
PVT.iono_model=Broadcast
PVT.trop_model=Saastamoinen

; Monitor
Monitor.enable_monitor=true
Monitor.decimation_factor=1
Monitor.client_addresses=127.0.0.1
Monitor.udp_port=1234
EOF

echo "========================================"
echo "🛰️  GNSS-SDR Live Pipeline"
echo "========================================"
echo ""
echo "Starting components:"
echo "  1. SDRplay → FIFO streamer"
echo "  2. GNSS-SDR reader"
echo "  3. WebSocket bridge"
echo ""

# Remove old FIFO
rm -f "$FIFO_PATH" 2>/dev/null || true

# Start SDRplay streamer in background (creates FIFO and waits)
echo "Starting SDRplay streamer..."
export DYLD_LIBRARY_PATH="/usr/local/lib:$DYLD_LIBRARY_PATH"
python3 -u "$SCRIPT_DIR/sdrplay_fifo_streamer.py" "$FIFO_PATH" 2>&1 | sed 's/^/[SDR] /' &
STREAMER_PID=$!

# Wait for FIFO to be created
echo "Waiting for FIFO creation..."
for i in {1..20}; do
    if [ -p "$FIFO_PATH" ]; then
        echo "✓ FIFO ready"
        break
    fi
    sleep 0.5
done

if [ ! -p "$FIFO_PATH" ]; then
    echo "❌ FIFO not created after 10 seconds"
    exit 1
fi

# Small delay for streamer initialization
sleep 2

# Start progress reporter
echo "Starting progress reporter..."
python3 -u "$SCRIPT_DIR/send_continuous_progress.py" 2>&1 | sed 's/^/[Progress] /' &

# Start GNSS-SDR with log parser
echo "Starting GNSS-SDR..."
export DYLD_LIBRARY_PATH="/usr/local/lib:$DYLD_LIBRARY_PATH"
gnss-sdr --config_file="$CONFIG_PATH" 2>&1 | python3 -u "$SCRIPT_DIR/parse_gnss_logs.py" &
GNSS_PID=$!

echo ""
echo "========================================"
echo "✅ All components started"
echo "========================================"
echo ""
echo "Processes:"
echo "  • Streamer PID: $STREAMER_PID"
echo "  • GNSS-SDR PID: $GNSS_PID"
echo ""
echo "WebSocket: ws://localhost:8766"
echo ""
echo "Press Ctrl+C to stop"
echo "----------------------------------------"
echo ""

# Wait for all background jobs
wait
