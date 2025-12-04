#!/bin/bash
# Monitor GNSS-SDR processing and show key events

echo "Monitoring GNSS-SDR system..."
echo "Watching /tmp/gnss_system.log for key events"
echo ""

tail -f /tmp/gnss_system.log | while IFS= read -r line; do
    # Highlight important events
    if [[ "$line" =~ "Recording complete" ]]; then
        echo ""
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo "✅ RECORDING COMPLETE - PROCESSING STARTING SOON"
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo ""
    elif [[ "$line" =~ "Processing with GNSS-SDR" ]]; then
        echo ""
        echo "🛰️  GNSS-SDR PROCESSING STARTED"
        echo ""
    elif [[ "$line" =~ "Tracking PRN" ]]; then
        echo "📡 $line"
    elif [[ "$line" =~ "Received message from client" ]]; then
        echo ""
        echo "🔥 BRIDGE RECEIVED MESSAGE FROM PARSE_GNSS_LOGS!"
        echo "$line"
    elif [[ "$line" =~ "GNSS data:" ]]; then
        echo "   $line"
    elif [[ "$line" =~ "Broadcast complete" ]]; then
        echo "   $line"
        echo "   ⚠️  CHECK UI NOW - Data should be visible!"
        echo ""
    elif [[ "$line" =~ "Client connected" ]]; then
        echo "🔌 $line"
    elif [[ "$line" =~ "Connected to WebSocket bridge" ]]; then
        echo "✅ PARSE_GNSS_LOGS CONNECTED TO BRIDGE!"
        echo ""
    elif [[ "$line" =~ "Sent update:" ]]; then
        echo "📤 $line"
    fi
done
