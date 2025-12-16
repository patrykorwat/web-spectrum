#!/bin/bash
# RTL-SDR GPS Quick Start Script
# Records GPS L1 signals, analyzes for jamming, and processes with GNSS-SDR

set -e  # Exit on error

echo "=================================================="
echo "RTL-SDR GPS L1 RECORDING & JAMMING DETECTION"
echo "=================================================="
echo ""

# Default duration: 5 minutes
DURATION=${1:-300}

echo "Configuration:"
echo "  Duration: $DURATION seconds ($(($DURATION / 60)) minutes)"
echo "  Sample Rate: 2.048 MSPS"
echo "  Center Frequency: 1575.42 MHz (GPS L1 C/A)"
echo "  Format: 8-bit IQ (RTL-SDR native)"
echo ""

# Check if rtl_sdr is installed
if ! command -v rtl_sdr &> /dev/null; then
    echo "ERROR: rtl_sdr not found!"
    echo "Install with: brew install librtlsdr"
    exit 1
fi

# Check if gnss-sdr is installed (optional)
if ! command -v gnss-sdr &> /dev/null; then
    echo "WARNING: gnss-sdr not found (GPS processing will be skipped)"
    echo "Install with: brew install gnss-sdr"
    GNSS_SDR_AVAILABLE=false
else
    GNSS_SDR_AVAILABLE=true
fi

echo "Step 1: Recording GPS L1 signals with RTL-SDR..."
echo "=================================================="
python3 rtl_sdr_direct.py --duration $DURATION

# Get the most recent recording file
RECORDING=$(ls -t recordings/gps_recording_*.dat 2>/dev/null | head -1)

if [ -z "$RECORDING" ]; then
    echo "ERROR: No recording file found!"
    exit 1
fi

echo ""
echo "Step 2: Analyzing spectrum for jamming signatures..."
echo "======================================================"
python3 gps_spectrum_analyzer.py "$RECORDING" --duration 60

# Check if spectrum image was generated
SPECTRUM_PNG="${RECORDING%.dat}_spectrum.png"
SPECTRUM_JSON="${RECORDING%.dat}_spectrum_analysis.json"

if [ -f "$SPECTRUM_PNG" ]; then
    echo ""
    echo "✓ Spectrum analysis complete!"
    echo "  Image: $SPECTRUM_PNG"
    echo "  Data:  $SPECTRUM_JSON"

    # Show jamming detection results
    if [ -f "$SPECTRUM_JSON" ]; then
        echo ""
        echo "Jamming Detection Results:"
        echo "=========================="

        # Extract detection results (requires jq for pretty printing, fallback to cat)
        if command -v jq &> /dev/null; then
            cat "$SPECTRUM_JSON" | jq '.detections'
        else
            cat "$SPECTRUM_JSON"
        fi
    fi
else
    echo "WARNING: Spectrum image not generated"
fi

# Step 3: Process with GNSS-SDR (optional)
if [ "$GNSS_SDR_AVAILABLE" = true ]; then
    echo ""
    echo "Step 3: Processing with GNSS-SDR (GPS satellite tracking)..."
    echo "============================================================="

    GNSS_CONFIG="${RECORDING}.conf"

    if [ -f "$GNSS_CONFIG" ]; then
        echo "Running GNSS-SDR (this may take 5-10 minutes)..."
        gnss-sdr --config_file="$GNSS_CONFIG" --signal_source.filename="$RECORDING" 2>&1 | tee "${RECORDING%.dat}_gnss.log"

        echo ""
        echo "✓ GNSS-SDR processing complete!"
        echo "  Log: ${RECORDING%.dat}_gnss.log"
    else
        echo "ERROR: GNSS-SDR config not found: $GNSS_CONFIG"
    fi
else
    echo ""
    echo "Step 3: GNSS-SDR processing skipped (not installed)"
fi

echo ""
echo "=================================================="
echo "ANALYSIS COMPLETE!"
echo "=================================================="
echo ""
echo "Generated Files:"
echo "  Recording:        $RECORDING"
echo "  Spectrum Image:   $SPECTRUM_PNG"
echo "  Spectrum Data:    $SPECTRUM_JSON"
if [ "$GNSS_SDR_AVAILABLE" = true ]; then
    echo "  GNSS-SDR Log:     ${RECORDING%.dat}_gnss.log"
fi
echo ""
echo "Next Steps:"
echo "  1. View spectrum image: open $SPECTRUM_PNG"
echo "  2. Check jamming detection: cat $SPECTRUM_JSON"
if [ "$GNSS_SDR_AVAILABLE" = true ]; then
    echo "  3. Review GPS tracking: less ${RECORDING%.dat}_gnss.log"
fi
echo ""
echo "To analyze a different duration, run:"
echo "  ./quick_start.sh <duration_in_seconds>"
echo "  Example: ./quick_start.sh 600  # 10 minutes"
echo ""
