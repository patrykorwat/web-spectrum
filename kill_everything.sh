#!/bin/bash
# Nuclear cleanup - kills EVERYTHING related to this app

echo "🧹 NUCLEAR CLEANUP - Killing all processes..."

# Kill by process name patterns
killall -9 Python 2>/dev/null
killall -9 node 2>/dev/null
killall -9 bash 2>/dev/null
killall -9 gnss-sdr 2>/dev/null

# Kill by port
lsof -ti:3005 | xargs kill -9 2>/dev/null
lsof -ti:8766 | xargs kill -9 2>/dev/null
lsof -ti:8767 | xargs kill -9 2>/dev/null
lsof -ti:1234 | xargs kill -9 2>/dev/null

sleep 3

echo "✅ Everything killed"
echo ""
echo "Verification:"
echo "  Processes remaining: $(ps aux | grep -E '(Python|node|bash)' | grep -v grep | wc -l)"
echo "  Port 3005: $(lsof -ti:3005 | wc -l) process(es)"
echo "  Port 8766: $(lsof -ti:8766 | wc -l) process(es)"
echo "  Port 8767: $(lsof -ti:8767 | wc -l) process(es)"
echo ""
echo "Now you can run: ./start_all.sh"
