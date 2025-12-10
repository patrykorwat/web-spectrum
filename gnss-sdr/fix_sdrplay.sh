#!/bin/bash
# Helper script to fix SDRplay API issues
# Run this if you get exit code -11 (segmentation fault)

echo "=========================================="
echo "SDRplay API Fix Helper"
echo "=========================================="
echo ""
echo "The SDRplay API service needs to be restarted."
echo "Please run the following commands:"
echo ""
echo "1. Restart the API service:"
echo "   sudo killall sdrplay_apiService"
echo ""
echo "2. Wait 3 seconds for it to auto-restart, then verify:"
echo "   sleep 3"
echo "   ps aux | grep sdrplay_apiService | grep -v grep"
echo ""
echo "3. If the service is running, test the device:"
echo "   cd $(dirname "$0")"
echo "   python3 -c 'from sdrplay_direct import SDRplayDevice; sdr = SDRplayDevice(); print(\"✓ Device OK\")'"
echo ""
echo "4. If that works, run the pipeline again:"
echo "   ./run_gnss.sh"
echo ""
echo "=========================================="
echo ""

# Check if running as root
if [ "$EUID" -eq 0 ]; then
    echo "You are root, attempting automatic fix..."
    killall sdrplay_apiService
    echo "Waiting for service to restart..."
    sleep 3

    if ps aux | grep -q "[s]drplay_apiService"; then
        echo "✓ Service restarted successfully"
        echo ""
        echo "Now testing device..."
        cd "$(dirname "$0")"
        if python3 -c 'from sdrplay_direct import SDRplayDevice; sdr = SDRplayDevice(); print("✓ Device OK")' 2>/dev/null; then
            echo ""
            echo "✓ All fixed! Run ./run_gnss.sh now"
        else
            echo "✗ Device still has issues. Try unplugging and replugging the USB cable."
        fi
    else
        echo "✗ Service didn't restart. Check SDRplay installation."
    fi
else
    echo "Please run the commands above manually (requires sudo)."
    echo ""
    echo "Quick fix command:"
    echo "sudo killall sdrplay_apiService && sleep 3 && ./run_gnss.sh"
fi