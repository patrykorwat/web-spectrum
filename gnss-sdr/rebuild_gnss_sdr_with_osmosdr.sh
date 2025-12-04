#!/bin/bash

################################################################################
# Rebuild GNSS-SDR with Gr-Osmosdr Support
#
# This script:
#   1. Installs gr-osmosdr from source (for SDRPlay access)
#   2. Rebuilds GNSS-SDR with Osmosdr support enabled
#   3. Verifies the installation
#
# Estimated time: 30-60 minutes
################################################################################

set -e  # Exit on error

echo "============================================================"
echo "Rebuilding GNSS-SDR with Osmosdr Support"
echo "============================================================"
echo ""

# Check dependencies
echo "Checking dependencies..."
if ! command -v cmake &> /dev/null; then
    echo "ERROR: cmake not found. Run: brew install cmake"
    exit 1
fi

if ! command -v git &> /dev/null; then
    echo "ERROR: git not found. Run: brew install git"
    exit 1
fi

# Ensure gnuradio is installed
if ! command -v gnuradio-config-info &> /dev/null; then
    echo "Installing GNU Radio..."
    brew install gnuradio
fi

echo ""
echo "============================================================"
echo "Step 1/3: Building gr-osmosdr from source"
echo "============================================================"
echo ""

BUILD_DIR="$HOME/gnss-sdr-rebuild"
mkdir -p "$BUILD_DIR"
cd "$BUILD_DIR"

# Clone gr-osmosdr
if [ -d "gr-osmosdr" ]; then
    echo "Removing old gr-osmosdr directory..."
    rm -rf gr-osmosdr
fi

echo "Cloning gr-osmosdr repository..."
git clone https://github.com/osmocom/gr-osmosdr.git
cd gr-osmosdr

# Build gr-osmosdr
echo "Building gr-osmosdr..."
mkdir -p build
cd build

cmake -DCMAKE_BUILD_TYPE=Release \
      -DENABLE_SOAPY=ON \
      -DENABLE_PYTHON=ON \
      ..

make -j$(sysctl -n hw.ncpu)

echo "Installing gr-osmosdr..."
sudo make install

cd ../..

echo ""
echo "============================================================"
echo "Step 2/3: Rebuilding GNSS-SDR with Osmosdr support"
echo "============================================================"
echo ""

# Remove old GNSS-SDR build
if [ -d "gnss-sdr" ]; then
    echo "Removing old GNSS-SDR directory..."
    rm -rf gnss-sdr
fi

echo "Cloning GNSS-SDR repository..."
git clone https://github.com/gnss-sdr/gnss-sdr.git
cd gnss-sdr

# Use the next branch (latest development)
echo "Checking out next branch..."
git checkout next

# Build GNSS-SDR
echo "Building GNSS-SDR with Osmosdr support..."
echo "This will take 20-40 minutes..."
mkdir -p build
cd build

cmake -DCMAKE_BUILD_TYPE=Release \
      -DENABLE_OSMOSDR=ON \
      -DENABLE_UHD=OFF \
      -DENABLE_FMCOMMS2=OFF \
      -DENABLE_PLUTOSDR=OFF \
      -DENABLE_AD9361=OFF \
      -DENABLE_RAW_UDP=ON \
      -DENABLE_PACKAGING=OFF \
      -DENABLE_UNIT_TESTING=OFF \
      ..

make -j$(sysctl -n hw.ncpu)

echo "Installing GNSS-SDR..."
sudo make install

cd ../../..

echo ""
echo "============================================================"
echo "Step 3/3: Verifying Installation"
echo "============================================================"
echo ""

# Check gnss-sdr
if command -v gnss-sdr &> /dev/null; then
    echo "✓ gnss-sdr installed successfully"
    gnss-sdr --version
else
    echo "ERROR: gnss-sdr not found in PATH!"
    exit 1
fi

# Run VOLK profiler
if command -v volk_gnsssdr_profile &> /dev/null; then
    echo ""
    echo "Running VOLK GNSS-SDR profiler (optimizes performance)..."
    echo "This will take a few minutes..."
    volk_gnsssdr_profile
fi

echo ""
echo "============================================================"
echo "✅ Installation Complete!"
echo "============================================================"
echo ""
echo "GNSS-SDR has been rebuilt with Osmosdr support!"
echo ""
echo "Next steps:"
echo "  1. Test with SDRPlay direct access:"
echo "     gnss-sdr --config_file=gnss_sdr_sdrplay_direct.conf"
echo ""
echo "  2. Or use the bridge:"
echo "     ./run_gnss_sdr_bridge.sh"
echo ""
