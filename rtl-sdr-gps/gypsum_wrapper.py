#!/usr/bin/env python3
"""
Gypsum GPS Decoder Wrapper
===========================

Wrapper script for running Gypsum GPS decoder and extracting position fixes.

Gypsum is a Python-based GPS receiver that can decode GPS signals and compute positions.
This wrapper:
1. Prepares the input file for Gypsum
2. Runs Gypsum decoder
3. Extracts position fixes from Gypsum output
4. Generates NMEA output for compatibility

Usage:
    python3 gypsum_wrapper.py --input gps_recording.dat --output results
"""

import argparse
import subprocess
import os
import sys
import json
import time
import logging
from pathlib import Path
from datetime import datetime

# Add gypsum to path
GYPSUM_DIR = Path(__file__).parent / "gypsum"
sys.path.insert(0, str(GYPSUM_DIR))


class GypsumDecoder:
    """Wrapper for Gypsum GPS decoder"""

    def __init__(self, input_file, output_dir):
        self.input_file = Path(input_file)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.gypsum_dir = GYPSUM_DIR
        self.vendored_signals_dir = self.gypsum_dir / "vendored_signals"
        self.vendored_signals_dir.mkdir(parents=True, exist_ok=True)

        # Output files
        self.nmea_file = self.output_dir / f"{self.input_file.stem}.nmea"
        self.json_file = self.output_dir / f"{self.input_file.stem}_position.json"

    def prepare_input_file(self):
        """
        Prepare input file for Gypsum by symlinking to vendored_signals
        """
        # Create symlink in vendored_signals
        link_path = self.vendored_signals_dir / self.input_file.name

        if link_path.exists():
            link_path.unlink()

        link_path.symlink_to(self.input_file.resolve())
        print(f"✓ Linked input file to: {link_path}")

        return link_path.name

    def register_input_file(self, filename):
        """
        Register input file with Gypsum's radio_input.py
        This modifies radio_input.py to add our file
        """
        radio_input_file = self.gypsum_dir / "gypsum" / "radio_input.py"

        # Read current content
        with open(radio_input_file, 'r') as f:
            lines = f.readlines()

        # Check if file is already registered
        content = ''.join(lines)
        if filename in content:
            print(f"✓ File already registered in radio_input.py")
            return

        # Find the INPUT_SOURCES list and add our file
        # We'll add it as a 2.048 MHz recording (closest to Gypsum's expected 2.046)
        new_entry = f'''    InputFileInfo.gnu_radio_recording(
        path=_VENDORED_SIGNALS_ROOT / "{filename}",
        sample_rate=2048000,  # RTL-SDR: 2.048 MSPS
        utc_start_time=dateutil.parser.parse("{datetime.utcnow().isoformat()}Z"),
    ),
'''

        # Find the closing bracket of INPUT_SOURCES list
        modified_lines = []
        inserted = False
        for i, line in enumerate(lines):
            if not inserted and line.strip() == ']' and i > 100:  # INPUT_SOURCES closing bracket
                # Insert before the closing bracket
                modified_lines.append(new_entry)
                inserted = True
            modified_lines.append(line)

        if not inserted:
            print("ERROR: Could not find INPUT_SOURCES list closing bracket")
            return

        # Write back
        with open(radio_input_file, 'w') as f:
            f.writelines(modified_lines)

        print(f"✓ Registered file in radio_input.py")

    def run_gypsum(self, filename):
        """
        Run Gypsum GPS decoder

        Returns:
            dict: Position fix data or None
        """
        print(f"\nRunning Gypsum GPS decoder...")
        print(f"  Input: {filename}")
        print(f"  This may take 1-2 minutes...")

        # Run gypsum-cli
        cmd = [
            'python3',
            str(self.gypsum_dir / 'gypsum-cli.py'),
            '--file_name', filename
        ]

        print(f"\nCommand: {' '.join(cmd)}\n")

        try:
            # Run Gypsum and capture output
            start_time = time.time()
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,  # 5 minute timeout
                cwd=str(self.gypsum_dir)
            )

            elapsed = time.time() - start_time

            # Parse Gypsum output for position fixes
            position_data = self.parse_gypsum_output(result.stdout, result.stderr)

            if position_data:
                print(f"\n✓ Gypsum completed in {elapsed:.1f}s")
                print(f"  Position: {position_data['latitude']:.6f}°, {position_data['longitude']:.6f}°")
                print(f"  Altitude: {position_data.get('altitude', 'N/A')} m")
                return position_data
            else:
                print(f"\n⚠ Gypsum completed but no position fix obtained")
                print(f"  Runtime: {elapsed:.1f}s")
                print(f"\nGypsum output:\n{result.stdout}")
                return None

        except subprocess.TimeoutExpired:
            print(f"\n✗ Gypsum timed out after 5 minutes")
            return None
        except Exception as e:
            print(f"\n✗ Error running Gypsum: {e}")
            return None

    def parse_gypsum_output(self, stdout, stderr):
        """
        Parse Gypsum output to extract position fix

        Gypsum logs position fixes in its output.
        We need to extract the final position.

        Returns:
            dict: {'latitude': float, 'longitude': float, 'altitude': float} or None
        """
        # Look for position fix patterns in Gypsum output
        # Gypsum typically logs something like:
        # "Position: lat=37.xxxxx, lon=-122.xxxxx, alt=xxx"

        position = None

        for line in (stdout + stderr).split('\n'):
            # Look for position indicators
            if 'position' in line.lower() or 'lat' in line.lower():
                # Try to extract coordinates
                # This is a simplified parser - may need adjustment based on actual Gypsum output
                try:
                    if 'lat' in line and 'lon' in line:
                        # Extract lat/lon from line
                        parts = line.lower().split()
                        lat = lon = alt = None

                        for i, part in enumerate(parts):
                            if 'lat' in part and i+1 < len(parts):
                                lat = float(parts[i+1].strip(','))
                            if 'lon' in part and i+1 < len(parts):
                                lon = float(parts[i+1].strip(','))
                            if 'alt' in part and i+1 < len(parts):
                                alt = float(parts[i+1].strip(','))

                        if lat and lon:
                            position = {
                                'latitude': lat,
                                'longitude': lon,
                                'altitude': alt or 0.0
                            }
                except:
                    continue

        return position

    def generate_nmea(self, position_data):
        """
        Generate NMEA output file from position data

        Args:
            position_data: dict with latitude, longitude, altitude
        """
        if not position_data:
            return

        lat = position_data['latitude']
        lon = position_data['longitude']
        alt = position_data.get('altitude', 0.0)

        # Convert to NMEA format
        lat_deg = int(abs(lat))
        lat_min = (abs(lat) - lat_deg) * 60
        lat_dir = 'N' if lat >= 0 else 'S'

        lon_deg = int(abs(lon))
        lon_min = (abs(lon) - lon_deg) * 60
        lon_dir = 'E' if lon >= 0 else 'W'

        # Generate GGA sentence (simplified)
        timestamp = datetime.utcnow().strftime("%H%M%S")
        gga = f"$GPGGA,{timestamp},{lat_deg:02d}{lat_min:07.4f},{lat_dir},{lon_deg:03d}{lon_min:07.4f},{lon_dir},1,08,1.0,{alt:.1f},M,0.0,M,,*00"

        # Write NMEA file
        with open(self.nmea_file, 'w') as f:
            f.write(gga + '\n')

        print(f"✓ Generated NMEA: {self.nmea_file}")

    def generate_json(self, position_data):
        """Generate JSON output with position data"""
        if not position_data:
            return

        output = {
            'timestamp': datetime.utcnow().isoformat(),
            'position': position_data,
            'decoder': 'Gypsum',
            'source': str(self.input_file)
        }

        with open(self.json_file, 'w') as f:
            json.dump(output, f, indent=2)

        print(f"✓ Generated JSON: {self.json_file}")

    def decode(self):
        """
        Main decode function

        Returns:
            bool: True if successful, False otherwise
        """
        print("="*60)
        print("Gypsum GPS Decoder")
        print("="*60)

        if not self.input_file.exists():
            print(f"ERROR: Input file not found: {self.input_file}")
            return False

        # Prepare input file
        filename = self.prepare_input_file()

        # Register with Gypsum
        self.register_input_file(filename)

        # Run Gypsum
        position_data = self.run_gypsum(filename)

        if position_data:
            # Generate outputs
            self.generate_nmea(position_data)
            self.generate_json(position_data)

            print(f"\n{'='*60}")
            print("Decoding Complete!")
            print(f"{'='*60}")
            return True
        else:
            print(f"\n{'='*60}")
            print("Decoding Failed - No Position Fix")
            print(f"{'='*60}")
            print("\nPossible reasons:")
            print("  - Recording too short (need 60+ seconds)")
            print("  - Weak GPS signals")
            print("  - Indoor location or obstructed sky view")
            print("  - Sample rate mismatch")
            return False


def main():
    parser = argparse.ArgumentParser(
        description='Gypsum GPS Decoder Wrapper',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument('--input', required=True,
                       help='Input GPS recording file (float32 format)')
    parser.add_argument('--output', default='results',
                       help='Output directory (default: results)')

    args = parser.parse_args()

    decoder = GypsumDecoder(args.input, args.output)
    success = decoder.decode()

    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
