#!/bin/bash
# SDR Device Status Checker

echo "=================================================="
echo "  SDR Device Status Diagnostic"
echo "=================================================="
echo

# Check RTL-SDR
echo "1. RTL-SDR Device Check:"
echo "------------------------"
if command -v rtl_test &> /dev/null; then
    timeout 2 rtl_test -t 2>&1 | head -15
    echo
else
    echo "❌ rtl_test not found - RTL-SDR tools not installed"
    echo
fi

# Check SDRPlay
echo "2. SDRPlay Device Check:"
echo "------------------------"
if [ -d "/Library/SDRplayAPI" ]; then
    echo "✅ SDRPlay API installed:"
    ls -1 /Library/SDRplayAPI/
    echo
else
    echo "❌ SDRPlay API not found"
    echo
fi

# Check running processes
echo "3. Processes Using SDR:"
echo "------------------------"
ps aux | grep -E "(rtl_|sdr)" | grep -v grep | head -10
echo

# Check USB devices
echo "4. USB Device Info:"
echo "-------------------"
system_profiler SPUSBDataType 2>/dev/null | grep -A 10 "RTL\|SDRplay" | head -20
echo

# Check ports
echo "5. Backend Services:"
echo "--------------------"
echo "Port 3001 (HTTP API):"
lsof -i :3001 2>&1 | grep -v COMMAND || echo "  Not listening"
echo
echo "Port 5001 (HTTP API alt):"
lsof -i :5001 2>&1 | grep -v COMMAND || echo "  Not listening"
echo
echo "Port 8766 (WebSocket):"
lsof -i :8766 2>&1 | grep -v COMMAND || echo "  Not listening"
echo

echo "=================================================="
echo "  Recommendations:"
echo "=================================================="
if timeout 2 rtl_test -t 2>&1 | grep -q "claimed"; then
    echo "⚠️  RTL-SDR device is BUSY (claimed by another process)"
    echo
    echo "Solutions:"
    echo "  1. Close browser tab if 'Listen & Decode' is active"
    echo "  2. Kill any rtl_* processes:"
    echo "     pkill rtl_"
    echo "  3. Restart the device (unplug/replug USB)"
    echo
elif timeout 2 rtl_test -t 2>&1 | grep -q "Found"; then
    echo "✅ RTL-SDR device is AVAILABLE and ready to use"
    echo
else
    echo "❌ No RTL-SDR device detected"
    echo
fi

echo "=================================================="
