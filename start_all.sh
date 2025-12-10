#!/bin/bash

################################################################################
# Web-Spectrum GNSS Master Startup Script
#
# This ONE script starts EVERYTHING you need:
#   1. Web UI (port 3005)
#   2. GNSS Control API (port 8767) - enables Start/Stop/Restart buttons
#   3. GNSS Bridge (port 8766) - relays satellite data to UI
#
# Usage:
#   ./start_all.sh              # File-based mode (default)
#   ./start_all.sh live         # Direct SDRPlay mode (live streaming via Osmosdr)
#   ./start_all.sh direct       # Direct SDRPlay API (NEW - full control, no Osmosdr)
#
# Then open browser to: http://localhost:3005
# Use the UI buttons to start/stop GPS data collection!
#
################################################################################

# Parse mode argument
MODE="${1:-file}"  # Default to file mode

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║         Web-Spectrum GNSS - Master Startup Script              ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""
echo "Mode: $MODE"
echo ""

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
GNSS_DIR="$SCRIPT_DIR/gnss-sdr"

# Set config file based on mode
case "$MODE" in
    live)
        GNSS_CONFIG="gnss_sdr_sdrplay_direct.conf"
        USE_DIRECT_API=false
        echo "Using direct SDRPlay mode (live streaming via Osmosdr)"
        ;;
    direct)
        GNSS_CONFIG="gnss_sdr_file.conf"
        USE_DIRECT_API=true
        echo "🆕 Using Direct SDRPlay API mode (Python API → file → GNSS-SDR)"
        echo "   ✓ Full control over SDRplay device"
        echo "   ✓ No Osmosdr/SoapySDR compatibility issues"
        echo "   ✓ Access to all device features"
        ;;
    file)
        GNSS_CONFIG="gnss_sdr_file.conf"
        USE_DIRECT_API=false
        echo "Using file-based mode"
        ;;
    *)
        echo "Unknown mode: $MODE"
        echo "Valid modes: file, live, direct"
        exit 1
        ;;
esac
echo ""

# Cleanup function
cleanup() {
    echo ""
    echo "Shutting down all services..."
    pkill -P $$ 2>/dev/null
    pkill -9 -f "npm start" 2>/dev/null
    pkill -9 -f "control_api.py" 2>/dev/null
    pkill -9 -f "gnss_sdr_bridge.py" 2>/dev/null
    pkill -9 -f "gnss-sdr" 2>/dev/null
    pkill -9 -f "sdrplay_soapy_streamer.py" 2>/dev/null
    pkill -9 -f "sdrplay_streamer.py" 2>/dev/null  # Old version
    echo "✓ All services stopped"
    exit 0
}

trap cleanup SIGINT SIGTERM

# Kill ALL previous instances automatically (no questions asked)
echo "Cleaning up previous instances..."

# Kill processes using ports first
lsof -ti :8766 | xargs kill -9 2>/dev/null || true
lsof -ti :8767 | xargs kill -9 2>/dev/null || true
lsof -ti :3005 | xargs kill -9 2>/dev/null || true

# Kill processes by name
pkill -9 -f "npm start" 2>/dev/null || true
pkill -9 -f "control_api.py" 2>/dev/null || true
pkill -9 -f "gnss_sdr_bridge.py" 2>/dev/null || true
pkill -9 -f "gnss-sdr" 2>/dev/null || true
pkill -9 -f "start_gnss.sh" 2>/dev/null || true
pkill -9 -f "record_iq_samples.py" 2>/dev/null || true
pkill -9 -f "parse_gnss_logs.py" 2>/dev/null || true
pkill -9 -f "sdrplay_soapy_streamer.py" 2>/dev/null || true
pkill -9 -f "sdrplay_streamer.py" 2>/dev/null || true  # Old version

sleep 3
echo "✓ Cleanup complete"
echo ""

# Start SDRplay Direct API streamer if in direct mode
if [ "$USE_DIRECT_API" = true ]; then
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "Starting SDRplay Direct API Streamer..."
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    # Check if SDRplay API is available
    cd "$GNSS_DIR"
    if ! python3 test_sdrplay_api.py > /dev/null 2>&1; then
        echo "❌ SDRplay API not available!"
        echo ""
        echo "Please check:"
        echo "  1. SDRplay API is installed"
        echo "  2. SDRplay service is running"
        echo "  3. Device is connected via USB"
        echo ""
        echo "Run test manually: cd gnss-sdr && python3 test_sdrplay_api.py"
        exit 1
    fi

    echo "✓ SDRplay API is ready"
    echo "Starting streamer (output: /tmp/gps_iq_samples.dat)..."
    echo "Using SoapySDR-based streamer (more stable than direct API)"

    # Set environment for SoapySDR
    export DYLD_LIBRARY_PATH="/usr/local/lib:$DYLD_LIBRARY_PATH"
    export PYTHONPATH="/opt/homebrew/lib/python3.14/site-packages:$PYTHONPATH"

    python3 -u sdrplay_soapy_streamer.py \
        --output /tmp/gps_iq_samples.dat \
        --frequency 1575.42e6 \
        --sample-rate 2.048e6 \
        --gain 40 \
        --bandwidth 1536000 \
        > /tmp/sdrplay_streamer.log 2>&1 &

    STREAMER_PID=$!
    sleep 3

    # Check if streamer is still running
    if ps -p $STREAMER_PID > /dev/null; then
        echo "✓ SDRplay Direct API Streamer started (PID $STREAMER_PID)"
        echo "  Streaming: SDRplay → Python API → /tmp/gps_iq_samples.dat"
        echo "  Log: tail -f /tmp/sdrplay_streamer.log"
    else
        echo "✗ Failed to start SDRplay streamer"
        echo "Check logs: tail -f /tmp/sdrplay_streamer.log"
        exit 1
    fi
    echo ""

    # Wait for initial data to be written
    echo "Waiting for initial IQ samples to be recorded..."
    sleep 5

    if [ -f /tmp/gps_iq_samples.dat ]; then
        FILE_SIZE=$(stat -f%z /tmp/gps_iq_samples.dat 2>/dev/null || stat -c%s /tmp/gps_iq_samples.dat 2>/dev/null || echo "0")
        echo "✓ IQ sample file created (${FILE_SIZE} bytes)"
    else
        echo "⚠️  Warning: IQ sample file not yet created, will be created when streaming starts"
    fi
    echo ""
fi

# Start Control API (port 8767)
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Starting Control API (port 8767)..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
cd "$GNSS_DIR"
python3 -u control_api.py > /tmp/control_api.log 2>&1 &
sleep 2

if lsof -i :8767 > /dev/null 2>&1; then
    CONTROL_PID=$(lsof -ti :8767 | head -1)
    echo "✓ Control API started (PID $CONTROL_PID)"
else
    echo "✗ Failed to start Control API"
    echo "Check logs: tail -f /tmp/control_api.log"
    exit 1
fi
echo ""

# Start GNSS Bridge (port 8766)
# NOTE: In live mode, bridge auto-starts GNSS-SDR to open signal source
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Starting GNSS Bridge (port 8766)..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
cd "$GNSS_DIR"
export DYLD_LIBRARY_PATH="/usr/local/lib:$DYLD_LIBRARY_PATH"
export PYTHONPATH="/opt/homebrew/lib/python3.14/site-packages:$PYTHONPATH"

# Auto-start GNSS-SDR for live mode, manual start for file mode
if [ "$MODE" = "file" ]; then
    echo "DEBUG: Starting bridge in manual mode (file-based processing)..."
    python3 -u gnss_sdr_bridge.py --config $GNSS_CONFIG --no-auto-start > /tmp/gnss_bridge.log 2>&1 &
else
    echo "DEBUG: Starting bridge with auto-start (will launch GNSS-SDR)..."
    python3 -u gnss_sdr_bridge.py --config $GNSS_CONFIG > /tmp/gnss_bridge.log 2>&1 &
fi
BRIDGE_PID=$!
sleep 2

if lsof -i :8766 > /dev/null 2>&1; then
    # Get the actual Python process PID (not tee)
    BRIDGE_PID=$(lsof -ti :8766 | grep -v grep | head -1)
    echo "✓ GNSS Bridge started (PID $BRIDGE_PID)"
else
    echo "✗ Failed to start GNSS Bridge"
    echo "Check logs: tail -f /tmp/gnss_bridge.log"
    exit 1
fi
echo ""

# Start Web UI (port 3005)
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Starting Web UI (port 3005)..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
cd "$SCRIPT_DIR"
npm start > /tmp/webui.log 2>&1 &
WEBUI_PID=$!
sleep 5

if lsof -i :3005 > /dev/null 2>&1; then
    echo "✓ Web UI started (PID $WEBUI_PID)"
else
    echo "⚠️  Web UI may still be starting..."
fi
echo ""

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║                   ALL SERVICES STARTED!                        ║"
echo "╠════════════════════════════════════════════════════════════════╣"
echo "║                                                                ║"
echo "║  🌐 Web UI:         http://localhost:3005                      ║"
echo "║  🎛️  Control API:    http://localhost:8767                      ║"
echo "║  📡 GNSS Bridge:    ws://localhost:8766                        ║"
echo "║                                                                ║"
echo "║  📝 Logs:                                                      ║"
echo "║     • tail -f /tmp/webui.log                                  ║"
echo "║     • tail -f /tmp/control_api.log                            ║"
echo "║     • tail -f /tmp/gnss_bridge.log                            ║"
if [ "$USE_DIRECT_API" = true ]; then
echo "║     • tail -f /tmp/sdrplay_streamer.log (Direct API)          ║"
fi
echo "║                                                                ║"
echo "║  🎮 USAGE:                                                     ║"
echo "║     1. Open http://localhost:3005 in your browser             ║"
echo "║     2. Select 'Professional Mode (GNSS-SDR)'                  ║"
if [ "$MODE" = "live" ]; then
echo "║     3. Live mode: Real-time streaming from SDRPlay            ║"
elif [ "$MODE" = "direct" ]; then
echo "║     3. 🆕 Direct API mode: Full control via Python             ║"
echo "║        SDRplay → Direct API → File → GNSS-SDR                ║"
else
echo "║     3. Click 'Start Collection' to begin GPS recording        ║"
fi
echo "║     4. Click 'Listen&Decode' to see satellite data            ║"
echo "║                                                                ║"
echo "║  🛑 To stop: Press Ctrl+C                                      ║"
echo "║                                                                ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

# Monitor and restart crashed services
while true; do
    sleep 10

    # Check if SDRplay Direct API streamer is still running (if enabled)
    if [ "$USE_DIRECT_API" = true ]; then
        if ! pgrep -f "sdrplay_soapy_streamer.py" > /dev/null 2>&1; then
            echo "⚠️  SDRplay Streamer crashed! Restarting..."
            cd "$GNSS_DIR"
            export DYLD_LIBRARY_PATH="/usr/local/lib:$DYLD_LIBRARY_PATH"
            export PYTHONPATH="/opt/homebrew/lib/python3.14/site-packages:$PYTHONPATH"
            python3 -u sdrplay_soapy_streamer.py \
                --output /tmp/gps_iq_samples.dat \
                --frequency 1575.42e6 \
                --sample-rate 2.048e6 \
                --gain 40 \
                --bandwidth 1536000 \
                > /tmp/sdrplay_streamer.log 2>&1 &
            STREAMER_PID=$!
            sleep 2
            if ps -p $STREAMER_PID > /dev/null; then
                echo "✓ SDRplay Streamer restarted (PID $STREAMER_PID)"
            else
                echo "✗ Failed to restart SDRplay Streamer"
                echo "   Check: tail -f /tmp/sdrplay_streamer.log"
            fi
        fi
    fi

    # Check if Control API is still running (check by port, not PID)
    if ! lsof -i :8767 > /dev/null 2>&1; then
        echo "⚠️  Control API crashed! Restarting..."
        cd "$GNSS_DIR"
        python3 -u control_api.py > /tmp/control_api.log 2>&1 &
        sleep 2
        if lsof -i :8767 > /dev/null 2>&1; then
            CONTROL_PID=$(lsof -ti :8767 | head -1)
            echo "✓ Control API restarted (PID $CONTROL_PID)"
        else
            echo "✗ Failed to restart Control API"
        fi
    fi

    # Check if GNSS Bridge is still running (check by port, not PID)
    if ! lsof -i :8766 > /dev/null 2>&1; then
        echo "⚠️  GNSS Bridge crashed! Restarting..."
        cd "$GNSS_DIR"
        export DYLD_LIBRARY_PATH="/usr/local/lib:$DYLD_LIBRARY_PATH"
        export PYTHONPATH="/opt/homebrew/lib/python3.14/site-packages:$PYTHONPATH"

        # Auto-start GNSS-SDR for live mode, manual for file mode
        if [ "$MODE" = "file" ]; then
            python3 -u gnss_sdr_bridge.py --config $GNSS_CONFIG --no-auto-start > /tmp/gnss_bridge.log 2>&1 &
        else
            python3 -u gnss_sdr_bridge.py --config $GNSS_CONFIG > /tmp/gnss_bridge.log 2>&1 &
        fi

        sleep 2
        if lsof -i :8766 > /dev/null 2>&1; then
            BRIDGE_PID=$(lsof -ti :8766 | head -1)
            echo "✓ GNSS Bridge restarted (PID $BRIDGE_PID)"
        else
            echo "✗ Failed to restart GNSS Bridge"
        fi
    fi

    # Check if Web UI is still running (check by port, not PID)
    if ! lsof -i :3005 > /dev/null 2>&1; then
        echo "⚠️  Web UI crashed! Restarting..."
        cd "$SCRIPT_DIR"
        npm start > /tmp/webui.log 2>&1 &
        WEBUI_PID=$!
        sleep 5
        if lsof -i :3005 > /dev/null 2>&1; then
            echo "✓ Web UI restarted (PID $WEBUI_PID)"
        else
            echo "✗ Failed to restart Web UI"
        fi
    fi
done
