#!/bin/bash
# SDRPlay Setup for macOS
# This script installs all prerequisites for using SDRPlay RSPdx with web-spectrum

set -e  # Exit on error

echo "============================================================"
echo "SDRPlay RSPdx Setup for macOS"
echo "============================================================"
echo ""

# Check if Homebrew is installed
if ! command -v brew &> /dev/null; then
    echo "❌ Homebrew not found!"
    echo "Please install Homebrew first: https://brew.sh"
    echo ""
    echo "Run this command:"
    echo '/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"'
    exit 1
fi

echo "✅ Homebrew found"
echo ""

# Step 1: Install SoapySDR
echo "📦 Step 1/4: Installing SoapySDR..."
if brew list soapysdr &> /dev/null; then
    echo "   ✅ SoapySDR already installed"
else
    brew install soapysdr
    echo "   ✅ SoapySDR installed"
fi
echo ""

# Step 2: Check for SDRPlay API
echo "📦 Step 2/5: Checking for SDRPlay API..."
if [ -d "/usr/local/include/sdrplay_api.h" ] || [ -d "/Library/Frameworks/iio.framework" ] || [ -f "/usr/local/lib/libsdrplay_api.dylib" ]; then
    echo "   ✅ SDRPlay API appears to be installed"
else
    echo "   ⚠️  SDRPlay API not found!"
    echo ""
    echo "   You need to install SDRPlay API manually:"
    echo "   1. Download from: https://www.sdrplay.com/downloads/"
    echo "   2. Look for 'SDRplay API for Mac'"
    echo "   3. Install the .pkg file"
    echo "   4. Restart your computer"
    echo "   5. Run this script again"
    echo ""
    read -p "   Have you already installed SDRPlay API? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "   Please install SDRPlay API first, then run this script again."
        exit 1
    fi
fi
echo ""

# Step 3: Install SoapySDRPlay3 from source
echo "📦 Step 3/5: Installing SoapySDRPlay3 (SDRPlay support for SoapySDR)..."
if [ -f "/usr/local/lib/SoapySDR/modules0.8/libsdrPlaySupport.so" ] || [ -f "/opt/homebrew/lib/SoapySDR/modules0.8/libsdrPlaySupport.so" ]; then
    echo "   ✅ SoapySDRPlay3 already installed"
else
    echo "   Building SoapySDRPlay3 from source..."

    # Install build dependencies
    brew install cmake pkg-config

    # Clone and build
    TEMP_DIR=$(mktemp -d)
    cd "$TEMP_DIR"
    git clone https://github.com/pothosware/SoapySDRPlay3.git
    cd SoapySDRPlay3
    mkdir build
    cd build
    cmake ..
    make
    sudo make install

    # Clean up
    cd -
    rm -rf "$TEMP_DIR"

    echo "   ✅ SoapySDRPlay3 built and installed"
fi
echo ""

# Step 4: Create virtual environment and install Python dependencies
echo "📦 Step 4/5: Setting up Python virtual environment..."
if [ -d "venv" ]; then
    echo "   ⚠️  Virtual environment already exists, skipping creation"
else
    python3 -m venv venv
    echo "   ✅ Virtual environment created"
fi

echo "   Installing Python dependencies in venv..."
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
echo "   ✅ Python dependencies installed"
echo ""

# Step 5: Verify installation
echo "🔍 Step 5/5: Verifying installation..."
echo ""
echo "Checking for SDRPlay device..."
SoapySDRUtil --find

if [ $? -eq 0 ]; then
    echo ""
    echo "============================================================"
    echo "✅ Installation Complete!"
    echo "============================================================"
    echo ""
    echo "Next steps:"
    echo "1. Connect your SDRPlay RSPdx via USB"
    echo "2. Activate virtual environment: source venv/bin/activate"
    echo "3. Run: python sdrplay_bridge.py --freq 1575.42e6 --rate 2.048e6 --gain 40"
    echo "4. Open web-spectrum and select 'WebSocket' as input source"
    echo ""
    echo "For more info, see SDRPLAY_QUICKSTART.md"
else
    echo ""
    echo "⚠️  Installation complete, but no SDRPlay device detected"
    echo ""
    echo "Make sure:"
    echo "1. SDRPlay RSPdx is connected via USB"
    echo "2. SDRPlay API is installed from: https://www.sdrplay.com/downloads/"
    echo "3. You may need to restart your computer after installing SDRPlay API"
    echo ""
fi
