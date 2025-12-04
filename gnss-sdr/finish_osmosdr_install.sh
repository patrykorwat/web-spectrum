#!/bin/bash

echo "============================================================"
echo "Finishing gr-osmosdr and GNSS-SDR Installation"
echo "============================================================"
echo ""

# Install gr-osmosdr
echo "Step 1: Installing gr-osmosdr..."
cd ~/gnss-sdr-rebuild/gr-osmosdr/build
sudo make install
sudo ldconfig 2>/dev/null || true

echo ""
echo "Step 2: Rebuilding GNSS-SDR with Osmosdr support..."
cd ~/gnss-sdr-rebuild

# Remove old GNSS-SDR if exists
if [ -d "gnss-sdr" ]; then
    rm -rf gnss-sdr
fi

# Clone and build GNSS-SDR
git clone https://github.com/gnss-sdr/gnss-sdr.git
cd gnss-sdr
git checkout next

mkdir -p build
cd build

cmake -DCMAKE_BUILD_TYPE=Release \
      -DENABLE_OSMOSDR=ON \
      -DENABLE_UHD=OFF \
      -DENABLE_FMCOMMS2=OFF \
      -DENABLE_PLUTOSDR=OFF \
      -DENABLE_AD9361=OFF \
      -DENABLE_RAW_UDP=OFF \
      -DENABLE_PACKAGING=OFF \
      -DENABLE_UNIT_TESTING=OFF \
      ..

echo ""
echo "Building GNSS-SDR (this will take 20-40 minutes)..."
make -j$(sysctl -n hw.ncpu)

echo ""
echo "Installing GNSS-SDR..."
sudo make install

echo ""
echo "Running VOLK profiler..."
volk_gnsssdr_profile

echo ""
echo "============================================================"
echo "✅ Installation Complete!"
echo "============================================================"
echo ""
echo "Test with:"
echo "  gnss-sdr --config_file=gnss_sdr_sdrplay_direct.conf"
echo ""
