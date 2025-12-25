#!/usr/bin/env python3
"""
Simplified Gypsum Wrapper - No Dependencies Version
====================================================

This wrapper provides a simplified interface to Gypsum that doesn't require
modifying radio_input.py dynamically. Instead, it creates a temporary Python
script that sets up the input source directly.

Usage:
    python3 gypsum_simple_wrapper.py --input recording.dat --output results/
"""

import argparse
import subprocess
import os
import sys
from pathlib import Path
from datetime import datetime
import json


def create_gypsum_runner(input_file, gypsum_dir, sample_rate=2046000):
    """
    Create a temporary Python script that runs Gypsum with our input file

    Args:
        input_file: Path to GPS recording file
        gypsum_dir: Path to Gypsum directory
        sample_rate: Sample rate in Hz (default: 2.046 MHz for Gypsum)
    """
    runner_script = f"""
import sys
import datetime
from pathlib import Path

# Add gypsum to path
sys.path.insert(0, '{gypsum_dir}')

import numpy as np
from gypsum.antenna_sample_provider import AntennaSampleProviderBackedByFile
from gypsum.receiver import GpsReceiver
from gypsum.radio_input import InputFileInfo

# Define our input file inline
input_source = InputFileInfo.gnu_radio_recording(
    path=Path('{input_file}'),
    sample_rate={sample_rate},  # Sample rate from recording
    utc_start_time=datetime.datetime.utcnow()
)

# Create receiver
antenna_samples_provider = AntennaSampleProviderBackedByFile(input_source)
print(f"Set up antenna sample stream backed by file: {{input_source.path.as_posix()}}")

# Run receiver
receiver = GpsReceiver(
    antenna_samples_provider,
    only_acquire_satellite_ids=None,  # Try all satellites
    present_matplotlib_satellite_tracker=False,
    present_web_ui=False,
)

# Process samples for up to 2 minutes
import time
start_time = time.time()
steps = 0
max_steps = 1200  # ~2 minutes at 100ms per step
print("Starting GPS signal processing...")

while steps < max_steps:
    receiver.step()
    steps += 1

    # Print progress every 100 steps
    if steps % 100 == 0:
        elapsed = time.time() - start_time
        print(f"Progress: {{steps}}/{{max_steps}} steps ({{elapsed:.1f}}s)")

    # Check if we got a position fix
    if hasattr(receiver, 'world_model') and receiver.world_model:
        if hasattr(receiver.world_model, 'position_fix') and receiver.world_model.position_fix:
            pos = receiver.world_model.position_fix
            print(f"\\nPosition Fix Obtained!")
            print(f"Latitude: {{pos.latitude}}")
            print(f"Longitude: {{pos.longitude}}")
            print(f"Altitude: {{pos.altitude if hasattr(pos, 'altitude') else 0}}")
            break

print(f"\\nCompleted {{steps}} processing steps in {{time.time() - start_time:.1f}}s")
"""

    runner_path = Path('/tmp/gypsum_runner.py')
    with open(runner_path, 'w') as f:
        f.write(runner_script)

    return runner_path


def run_gypsum(input_file, output_dir, gypsum_dir, sample_rate=2046000):
    """
    Run Gypsum decoder using a temporary runner script

    Args:
        input_file: Path to GPS recording file
        output_dir: Output directory for results
        gypsum_dir: Path to Gypsum directory
        sample_rate: Sample rate in Hz (default: 2.046 MHz)
    """
    print("="*60)
    print("Gypsum GPS Decoder (Simplified)")
    print("="*60)

    input_path = Path(input_file)
    if not input_path.exists():
        print(f"ERROR: Input file not found: {input_file}")
        return False

    print(f"\nInput file: {input_path}")
    print(f"File size: {input_path.stat().st_size / 1e6:.1f} MB")
    print(f"Sample rate: {sample_rate / 1e6:.3f} MHz")
    print(f"Output dir: {output_dir}\n")

    # Create runner script
    print("Creating Gypsum runner script...")
    runner_path = create_gypsum_runner(input_path, gypsum_dir, sample_rate)
    print(f"Runner created: {runner_path}\n")

    # Run Gypsum
    print("Running Gypsum GPS decoder...")
    print("This may take 1-2 minutes...\n")

    try:
        result = subprocess.run(
            ['python3', str(runner_path)],
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout
        )

        print(result.stdout)
        if result.stderr:
            print("Errors/Warnings:")
            print(result.stderr)

        # Parse output for position fix
        if 'Position Fix Obtained!' in result.stdout:
            print("\n" + "="*60)
            print("SUCCESS: Position fix obtained!")
            print("="*60)

            # Extract position from output
            lines = result.stdout.split('\n')
            position = {}
            for line in lines:
                if 'Latitude:' in line:
                    position['latitude'] = float(line.split(':')[1].strip())
                elif 'Longitude:' in line:
                    position['longitude'] = float(line.split(':')[1].strip())
                elif 'Altitude:' in line:
                    position['altitude'] = float(line.split(':')[1].strip())

            # Save to JSON
            output_json = Path(output_dir) / f"{input_path.stem}_position.json"
            with open(output_json, 'w') as f:
                json.dump({
                    'timestamp': datetime.utcnow().isoformat(),
                    'position': position,
                    'decoder': 'Gypsum',
                    'source': str(input_path)
                }, f, indent=2)
            print(f"\nPosition saved to: {output_json}")

            # Generate simple NMEA
            lat = position['latitude']
            lon = position['longitude']
            alt = position.get('altitude', 0)

            lat_deg = int(abs(lat))
            lat_min = (abs(lat) - lat_deg) * 60
            lat_dir = 'N' if lat >= 0 else 'S'

            lon_deg = int(abs(lon))
            lon_min = (abs(lon) - lon_deg) * 60
            lon_dir = 'E' if lon >= 0 else 'W'

            timestamp = datetime.utcnow().strftime("%H%M%S")
            gga = f"$GPGGA,{timestamp},{lat_deg:02d}{lat_min:07.4f},{lat_dir},{lon_deg:03d}{lon_min:07.4f},{lon_dir},1,08,1.0,{alt:.1f},M,0.0,M,,*00"

            nmea_file = Path(output_dir) / f"{input_path.stem}.nmea"
            with open(nmea_file, 'w') as f:
                f.write(gga + '\n')
            print(f"NMEA saved to: {nmea_file}")

            return True
        else:
            print("\n" + "="*60)
            print("No position fix obtained")
            print("="*60)
            print("\nPossible reasons:")
            print("  - Recording too short (need 60+ seconds)")
            print("  - Weak GPS signals")
            print("  - Indoor location")
            return False

    except subprocess.TimeoutExpired:
        print("\nERROR: Gypsum timed out after 5 minutes")
        return False
    except Exception as e:
        print(f"\nERROR: {e}")
        return False
    finally:
        # Cleanup runner script
        if runner_path.exists():
            runner_path.unlink()


def main():
    parser = argparse.ArgumentParser(description='Simplified Gypsum GPS Decoder Wrapper')
    parser.add_argument('--input', required=True, help='Input GPS recording file')
    parser.add_argument('--output', default='results', help='Output directory')
    parser.add_argument('--sample-rate', type=float, default=2.046e6,
                        help='Sample rate in Hz (default: 2.046 MHz for Gypsum)')

    args = parser.parse_args()

    # Find Gypsum directory
    script_dir = Path(__file__).parent
    gypsum_dir = script_dir / 'gypsum'

    if not gypsum_dir.exists():
        print(f"ERROR: Gypsum directory not found: {gypsum_dir}")
        sys.exit(1)

    # Create output directory
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Run Gypsum
    success = run_gypsum(args.input, output_dir, gypsum_dir, int(args.sample_rate))
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
