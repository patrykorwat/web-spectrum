#!/bin/bash
# Install SoapySDRPlay3 support (run AFTER installing SDRPlay API)

set -e

echo "============================================================"
echo "Installing SoapySDRPlay3 Support"
echo "============================================================"
echo ""

# Check if SDRPlay API is installed
if [ ! -f "/usr/local/lib/libsdrplay_api.dylib" ] && [ ! -f "/usr/local/lib/libsdrplay_api.3.dylib" ]; then
    echo "❌ ERROR: SDRPlay API not found!"
    echo ""
    echo "Please install SDRPlay API first:"
    echo "1. Download from: https://www.sdrplay.com/downloads/"
    echo "2. Look for 'SDRplay API for Mac'"
    echo "3. Install the .pkg file"
    echo "4. RESTART your computer"
    echo "5. Run this script again"
    exit 1
fi

echo "✅ SDRPlay API found"
echo ""

# Install build dependencies
echo "📦 Installing build dependencies..."
brew install cmake pkg-config git

# Clone and build SoapySDRPlay3
echo "📦 Building SoapySDRPlay3..."
TEMP_DIR=$(mktemp -d)
echo "Working in: $TEMP_DIR"

cd "$TEMP_DIR"
git clone https://github.com/pothosware/SoapySDRPlay3.git
cd SoapySDRPlay3

# Fix CMake minimum version issue with CMake 4.x
echo "Patching CMakeLists.txt for CMake 4.x compatibility..."
sed -i.bak 's/cmake_minimum_required(VERSION 2.6)/cmake_minimum_required(VERSION 3.5)/' CMakeLists.txt

mkdir build
cd build
cmake .. -DCMAKE_POLICY_VERSION_MINIMUM=3.5
make -j4

echo ""
echo "Installing SoapySDRPlay3 (requires sudo)..."
sudo make install

# Clean up
cd ~
rm -rf "$TEMP_DIR"

echo ""
echo "============================================================"
echo "✅ SoapySDRPlay3 Installed!"
echo "============================================================"
echo ""
echo "Verifying installation..."
SoapySDRUtil --find

echo ""
echo "If you see your RSPduo above, you're ready to go!"
echo ""
echo "Run the bridge with:"
echo "  ./run_sdrplay_bridge.sh --freq 1575.42e6 --rate 2.048e6 --gain 40"
