#!/bin/bash

################################################################################
# Fix SDRplay API Library Path for SoapySDR
#
# Issue: SoapySDR SDRplay module can't find libsdrplay_api.so.3
# Cause: DYLD_LIBRARY_PATH doesn't include /usr/local/lib
# Solution: Add environment variable to shell profile
################################################################################

set -e

echo "========================================================================"
echo "SDRplay API Library Path Fix"
echo "========================================================================"
echo ""

# Detect shell
SHELL_NAME=$(basename "$SHELL")
echo "Detected shell: $SHELL_NAME"
echo ""

# Determine profile file
case "$SHELL_NAME" in
    zsh)
        PROFILE_FILE="$HOME/.zshrc"
        ;;
    bash)
        if [[ "$OSTYPE" == "darwin"* ]]; then
            PROFILE_FILE="$HOME/.bash_profile"
        else
            PROFILE_FILE="$HOME/.bashrc"
        fi
        ;;
    *)
        PROFILE_FILE="$HOME/.profile"
        ;;
esac

echo "Profile file: $PROFILE_FILE"
echo ""

# Check if library exists
if [ ! -f "/usr/local/lib/libsdrplay_api.so.3" ]; then
    echo "❌ ERROR: SDRplay API library not found!"
    echo "   Expected: /usr/local/lib/libsdrplay_api.so.3"
    echo ""
    echo "   Please install SDRplay API first:"
    echo "   https://www.sdrplay.com/api/"
    exit 1
fi

echo "✓ SDRplay API library found: /usr/local/lib/libsdrplay_api.so.3"
echo ""

# Check if already in profile
if grep -q "DYLD_LIBRARY_PATH.*usr/local/lib" "$PROFILE_FILE" 2>/dev/null; then
    echo "✓ DYLD_LIBRARY_PATH already set in $PROFILE_FILE"
    echo ""
else
    echo "Adding DYLD_LIBRARY_PATH to $PROFILE_FILE..."
    echo "" >> "$PROFILE_FILE"
    echo "# SDRplay API library path (for SoapySDR)" >> "$PROFILE_FILE"
    echo "export DYLD_LIBRARY_PATH=\"/usr/local/lib:\$DYLD_LIBRARY_PATH\"" >> "$PROFILE_FILE"
    echo ""
    echo "✓ Added to $PROFILE_FILE"
    echo ""
fi

# Set for current session
export DYLD_LIBRARY_PATH="/usr/local/lib:$DYLD_LIBRARY_PATH"

echo "Testing SoapySDR SDRplay detection..."
echo ""

# Test device detection
if DYLD_LIBRARY_PATH="/usr/local/lib:$DYLD_LIBRARY_PATH" SoapySDRUtil --find="driver=sdrplay" 2>&1 | grep -q "Found device"; then
    echo "✅ SUCCESS! SDRplay device detected"
    echo ""
    DYLD_LIBRARY_PATH="/usr/local/lib:$DYLD_LIBRARY_PATH" SoapySDRUtil --find="driver=sdrplay"
else
    echo "⚠️  No SDRplay devices found"
    echo ""
    echo "Possible reasons:"
    echo "  • SDRplay not connected via USB"
    echo "  • Device in use by another program"
    echo "  • SDRplay API service not running"
    echo ""
    echo "Try:"
    echo "  1. Connect SDRplay via USB"
    echo "  2. Check: lsusb | grep -i sdrplay"
    echo "  3. Restart SDRplay service:"
    echo "     sudo killall sdrplay_apiService"
    echo "     (it will auto-restart)"
fi

echo ""
echo "========================================================================"
echo "IMPORTANT: Restart your terminal for changes to take effect!"
echo "========================================================================"
echo ""
echo "Or run this in your current terminal:"
echo "  export DYLD_LIBRARY_PATH=\"/usr/local/lib:\$DYLD_LIBRARY_PATH\""
echo ""
echo "Then test with:"
echo "  SoapySDRUtil --find=\"driver=sdrplay\""
echo ""
