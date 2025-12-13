#!/bin/bash
################################################################################
# GPS Backend Services Startup Script
#
# Starts all necessary backend services for GPS recording and processing:
# 1. HTTP API Server (port 5001) - handles recording commands
# 2. WebSocket Server (port 8766) - streams GNSS data to UI
#
# Usage:
#   ./start_backend.sh          # Start all services
#   ./start_backend.sh stop     # Stop all services
#   ./start_backend.sh restart  # Restart all services
#   ./start_backend.sh status   # Check service status
################################################################################

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PIDFILE_DIR="$SCRIPT_DIR/.pids"
HTTP_PIDFILE="$PIDFILE_DIR/http_api.pid"
WS_PIDFILE="$PIDFILE_DIR/websocket.pid"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Ensure PID directory exists
mkdir -p "$PIDFILE_DIR"

# Function to print colored status messages
print_status() {
    local color=$1
    local message=$2
    echo -e "${color}${message}${NC}"
}

# Function to check if a process is running
is_running() {
    local pidfile=$1
    if [ -f "$pidfile" ]; then
        local pid=$(cat "$pidfile")
        if ps -p "$pid" > /dev/null 2>&1; then
            return 0  # Running
        else
            rm -f "$pidfile"
            return 1  # Not running
        fi
    fi
    return 1  # PID file doesn't exist
}

# Function to start HTTP API server
start_http_api() {
    if is_running "$HTTP_PIDFILE"; then
        print_status "$YELLOW" "✓ HTTP API Server already running (PID $(cat $HTTP_PIDFILE))"
        return
    fi

    print_status "$BLUE" "Starting HTTP API Server (port 5001)..."
    cd "$SCRIPT_DIR"
    nohup python3 recording_api_simple.py > "$SCRIPT_DIR/logs/http_api.log" 2>&1 &
    echo $! > "$HTTP_PIDFILE"
    sleep 2

    if is_running "$HTTP_PIDFILE"; then
        print_status "$GREEN" "✓ HTTP API Server started (PID $(cat $HTTP_PIDFILE))"
    else
        print_status "$RED" "✗ Failed to start HTTP API Server"
        return 1
    fi
}

# Function to start WebSocket server
start_websocket() {
    if is_running "$WS_PIDFILE"; then
        print_status "$YELLOW" "✓ WebSocket Server already running (PID $(cat $WS_PIDFILE))"
        return
    fi

    print_status "$BLUE" "Starting WebSocket Server (port 8766)..."
    cd "$SCRIPT_DIR"
    nohup python3 gnss_sdr_bridge.py > "$SCRIPT_DIR/logs/websocket.log" 2>&1 &
    echo $! > "$WS_PIDFILE"
    sleep 2

    if is_running "$WS_PIDFILE"; then
        print_status "$GREEN" "✓ WebSocket Server started (PID $(cat $WS_PIDFILE))"
    else
        print_status "$RED" "✗ Failed to start WebSocket Server"
        return 1
    fi
}

# Function to stop a service
stop_service() {
    local name=$1
    local pidfile=$2

    if is_running "$pidfile"; then
        local pid=$(cat "$pidfile")
        print_status "$BLUE" "Stopping $name (PID $pid)..."
        kill "$pid" 2>/dev/null
        sleep 2

        # Force kill if still running
        if ps -p "$pid" > /dev/null 2>&1; then
            print_status "$YELLOW" "Force killing $name..."
            kill -9 "$pid" 2>/dev/null
        fi

        rm -f "$pidfile"
        print_status "$GREEN" "✓ $name stopped"
    else
        print_status "$YELLOW" "✓ $name not running"
    fi
}

# Function to show status
show_status() {
    echo ""
    print_status "$BLUE" "=== GPS Backend Services Status ==="
    echo ""

    # HTTP API Server
    if is_running "$HTTP_PIDFILE"; then
        local pid=$(cat "$HTTP_PIDFILE")
        print_status "$GREEN" "✓ HTTP API Server: RUNNING (PID $pid, port 5001)"
    else
        print_status "$RED" "✗ HTTP API Server: STOPPED"
    fi

    # WebSocket Server
    if is_running "$WS_PIDFILE"; then
        local pid=$(cat "$WS_PIDFILE")
        print_status "$GREEN" "✓ WebSocket Server: RUNNING (PID $pid, port 8766)"
    else
        print_status "$RED" "✗ WebSocket Server: STOPPED"
    fi

    echo ""

    # Show listening ports
    print_status "$BLUE" "Listening ports:"
    lsof -nP -iTCP:5001,8766 -sTCP:LISTEN 2>/dev/null | grep -v COMMAND || echo "  (none)"
    echo ""
}

# Function to start all services
start_all() {
    print_status "$BLUE" "========================================"
    print_status "$BLUE" "  GPS Backend Services Startup"
    print_status "$BLUE" "========================================"
    echo ""

    # Ensure log directory exists
    mkdir -p "$SCRIPT_DIR/logs"

    # Start services
    start_http_api
    start_websocket

    echo ""
    show_status

    echo ""
    print_status "$GREEN" "========================================"
    print_status "$GREEN" "  Backend Ready!"
    print_status "$GREEN" "========================================"
    echo ""
    print_status "$BLUE" "HTTP API:    http://localhost:5001"
    print_status "$BLUE" "WebSocket:   ws://localhost:8766"
    echo ""
    print_status "$YELLOW" "Logs location: $SCRIPT_DIR/logs/"
    print_status "$YELLOW" "To stop: ./start_backend.sh stop"
    echo ""
}

# Function to stop all services
stop_all() {
    print_status "$BLUE" "========================================"
    print_status "$BLUE" "  Stopping GPS Backend Services"
    print_status "$BLUE" "========================================"
    echo ""

    stop_service "HTTP API Server" "$HTTP_PIDFILE"
    stop_service "WebSocket Server" "$WS_PIDFILE"

    echo ""
    print_status "$GREEN" "All services stopped"
    echo ""
}

# Function to restart all services
restart_all() {
    stop_all
    sleep 2
    start_all
}

# Main script logic
case "${1:-start}" in
    start)
        start_all
        ;;
    stop)
        stop_all
        ;;
    restart)
        restart_all
        ;;
    status)
        show_status
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|status}"
        echo ""
        echo "  start   - Start all backend services (default)"
        echo "  stop    - Stop all backend services"
        echo "  restart - Restart all backend services"
        echo "  status  - Show service status"
        echo ""
        exit 1
        ;;
esac

exit 0
