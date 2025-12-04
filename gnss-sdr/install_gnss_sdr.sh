#!/bin/bash

################################################################################
# GNSS-SDR Installation Script for macOS
#
# Installs gnss-sdr and all dependencies for professional GNSS signal processing
# with SDRPlay devices.
#
# Requirements:
#   - macOS 10.15+ (Catalina or later)
#   - Homebrew installed
#   - SDRPlay API already installed (run install_sdrplay_macos.sh first)
#   - ~2GB free disk space
#   - ~30-60 minutes installation time
#
# Usage:
#   chmod +x install_gnss_sdr.sh
#   ./install_gnss_sdr.sh
#
################################################################################

set -e  # Exit on error

echo "============================================================"
echo "GNSS-SDR Installation for macOS"
echo "============================================================"
echo ""

# Check if running on macOS
if [[ "$OSTYPE" != "darwin"* ]]; then
    echo "ERROR: This script is for macOS only."
    exit 1
fi

# Check if Homebrew is installed
if ! command -v brew &> /dev/null; then
    echo "ERROR: Homebrew is not installed!"
    echo "Install from: https://brew.sh"
    exit 1
fi

echo "Updating Homebrew..."
brew update

echo ""
echo "============================================================"
echo "Step 1: Installing Dependencies"
echo "============================================================"
echo ""

# Core dependencies
echo "Installing core dependencies..."
brew install cmake pkg-config git

# Math and DSP libraries
echo "Installing math libraries..."
brew install armadillo volk gflags glog

# GNSS-SDR dependencies
echo "Installing GNSS-SDR dependencies..."
brew install gnutls gnuradio libmatio protobuf pugixml

# Python for scripting
echo "Installing Python packages..."
brew install python3
pip3 install --upgrade pip
pip3 install numpy matplotlib

echo ""
echo "============================================================"
echo "Step 2: Checking for SoapySDR and SDRPlay Support"
echo "============================================================"
echo ""

if ! command -v SoapySDRUtil &> /dev/null; then
    echo "Installing SoapySDR..."
    brew install soapysdr
else
    echo "SoapySDR already installed"
fi

# Check for SDRPlay support
echo "Checking for SDRPlay devices..."
if SoapySDRUtil --find="driver=sdrplay" | grep -q "driver=sdrplay"; then
    echo "✓ SDRPlay support detected!"
else
    echo "WARNING: No SDRPlay devices found!"
    echo "Make sure:"
    echo "  1. SDRPlay API is installed (run: ./install_sdrplay_macos.sh)"
    echo "  2. SDRPlay device is connected"
    echo ""
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

echo ""
echo "============================================================"
echo "Step 3: Installing GNSS-SDR"
echo "============================================================"
echo ""

# Try to install via Homebrew first (easiest)
if brew info gnss-sdr &> /dev/null; then
    echo "Installing GNSS-SDR via Homebrew..."
    brew install gnss-sdr
    GNSS_SDR_INSTALLED_VIA_BREW=true
else
    echo "GNSS-SDR not available in Homebrew, building from source..."
    GNSS_SDR_INSTALLED_VIA_BREW=false

    # Clone repository
    GNSS_DIR="$HOME/gnss-sdr-build"
    if [ -d "$GNSS_DIR" ]; then
        echo "Removing old build directory..."
        rm -rf "$GNSS_DIR"
    fi

    mkdir -p "$GNSS_DIR"
    cd "$GNSS_DIR"

    echo "Cloning GNSS-SDR repository..."
    git clone https://github.com/gnss-sdr/gnss-sdr.git
    cd gnss-sdr

    # Use latest stable release
    echo "Checking out latest stable release..."
    git checkout $(git describe --tags `git rev-list --tags --max-count=1`)

    # Build
    echo "Building GNSS-SDR (this will take 20-40 minutes)..."
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
          ..

    make -j$(sysctl -n hw.ncpu)

    echo "Installing GNSS-SDR..."
    sudo make install

    cd ../../..
fi

echo ""
echo "============================================================"
echo "Step 4: Verifying Installation"
echo "============================================================"
echo ""

# Check if gnss-sdr is in PATH
if command -v gnss-sdr &> /dev/null; then
    echo "✓ gnss-sdr executable found"
    gnss-sdr --version || true
else
    echo "ERROR: gnss-sdr not found in PATH!"
    echo "You may need to add it manually:"
    echo "  export PATH=\"/usr/local/bin:\$PATH\""
    exit 1
fi

# Check for volk_gnsssdr_profile
if command -v volk_gnsssdr_profile &> /dev/null; then
    echo ""
    echo "Running VOLK GNSS-SDR profiler (optimizes performance)..."
    echo "This will take a few minutes..."
    volk_gnsssdr_profile
else
    echo "WARNING: volk_gnsssdr_profile not found, skipping optimization"
fi

echo ""
echo "============================================================"
echo "Installation Complete!"
echo "============================================================"
echo ""
echo "GNSS-SDR has been successfully installed!"
echo ""
echo "Next steps:"
echo "  1. Test GNSS-SDR with your SDRPlay:"
echo "     ./run_gnss_sdr_bridge.sh"
echo ""
echo "  2. Or run directly:"
echo "     gnss-sdr --config_file=gnss_sdr_config.conf"
echo ""
echo "Useful commands:"
echo "  - Check version:        gnss-sdr --version"
echo "  - List all options:     gnss-sdr --help"
echo "  - Test configuration:   gnss-sdr --config_file=FILE --log_dir=logs"
echo ""
echo "Documentation:"
echo "  - https://gnss-sdr.org/docs/"
echo "  - https://gnss-sdr.org/my-first-fix/"
echo ""
