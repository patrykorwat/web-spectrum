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
#   ./start_all.sh
#
# Then open browser to: http://localhost:3005
# Use the UI buttons to start/stop GPS data collection!
#
################################################################################

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║         Web-Spectrum GNSS - Master Startup Script              ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
GNSS_DIR="$SCRIPT_DIR/gnss-sdr"

# Cleanup function
cleanup() {
    echo ""
    echo "Shutting down all services..."
    pkill -P $$ 2>/dev/null
    pkill -9 -f "npm start" 2>/dev/null
    pkill -9 -f "control_api.py" 2>/dev/null
    pkill -9 -f "gnss_sdr_bridge.py" 2>/dev/null
    pkill -9 -f "gnss-sdr" 2>/dev/null
    echo "✓ All services stopped"
    exit 0
}

trap cleanup SIGINT SIGTERM

# Kill ALL previous instances automatically (no questions asked)
echo "Cleaning up previous instances..."
pkill -9 -f "npm start" 2>/dev/null
pkill -9 -f "control_api.py" 2>/dev/null
pkill -9 -f "gnss_sdr_bridge.py" 2>/dev/null
pkill -9 -f "gnss-sdr" 2>/dev/null
pkill -9 -f "start_gnss.sh" 2>/dev/null
pkill -9 -f "record_iq_samples.py" 2>/dev/null
pkill -9 -f "parse_gnss_logs.py" 2>/dev/null
sleep 3
echo "✓ Cleanup complete"
echo ""

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
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Starting GNSS Bridge (port 8766)..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
cd "$GNSS_DIR"
export DYLD_LIBRARY_PATH="/usr/local/lib:$DYLD_LIBRARY_PATH"
export PYTHONPATH="/opt/homebrew/lib/python3.14/site-packages:$PYTHONPATH"
echo "DEBUG: Starting bridge with verbose output..."
python3 -u gnss_sdr_bridge.py --config gnss_sdr_file.conf --no-auto-start > /tmp/gnss_bridge.log 2>&1 &
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
echo "║                                                                ║"
echo "║  🎮 USAGE:                                                     ║"
echo "║     1. Open http://localhost:3005 in your browser             ║"
echo "║     2. Select 'Professional Mode (GNSS-SDR)'                  ║"
echo "║     3. Click 'Start Collection' to begin GPS recording        ║"
echo "║     4. Click 'Listen&Decode' to see satellite data            ║"
echo "║                                                                ║"
echo "║  🛑 To stop: Press Ctrl+C                                      ║"
echo "║                                                                ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

# Monitor and restart crashed services
while true; do
    sleep 10

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
        python3 -u gnss_sdr_bridge.py --config gnss_sdr_file.conf --no-auto-start > /tmp/gnss_bridge.log 2>&1 &
        sleep 2
        if lsof -i :8766 > /dev/null 2>&1; then
            BRIDGE_PID=$(lsof -ti :8766 | head -1)
            echo "✓ GNSS Bridge restarted (PID $BRIDGE_PID)"
        else
            echo "✗ Failed to restart GNSS Bridge"
        fi
    fi

    # Check if Web UI is still running
    if ! kill -0 $WEBUI_PID 2>/dev/null; then
        echo "⚠️  Web UI crashed! Restarting..."
        cd "$SCRIPT_DIR"
        npm start > /tmp/webui.log 2>&1 &
        WEBUI_PID=$!
        echo "✓ Web UI restarting (PID $WEBUI_PID)"
    fi
done
