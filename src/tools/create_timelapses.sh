#!/bin/bash
# Timelapse creation script for xrit-rx
# This script can be run manually or scheduled via cron

# Configuration
RECEIVED_DIR="/xrit-rx/received"
OUTPUT_DIR="/xrit-rx/received/timelapses"
PYTHON_SCRIPT="/xrit-rx/tools/timelapse.py"

# Create output directory if it doesn't exist
mkdir -p "$OUTPUT_DIR"

# Create 24-hour Full Disk MP4 timelapse
echo "Creating 24h FD MP4 timelapse..."
python3 "$PYTHON_SCRIPT" --received "$RECEIVED_DIR" --hours 24 --type FD --format mp4 --output "$OUTPUT_DIR/latest_24h_FD.mp4"

# Create 3-hour Full Disk MP4 timelapse  
echo "Creating 3h FD MP4 timelapse..."
python3 "$PYTHON_SCRIPT" --received "$RECEIVED_DIR" --hours 3 --type FD --format mp4 --output "$OUTPUT_DIR/latest_3h_FD.mp4"

# Create 24-hour Full Disk GIF timelapse
echo "Creating 24h FD GIF timelapse..."
python3 "$PYTHON_SCRIPT" --received "$RECEIVED_DIR" --hours 24 --type FD --format gif --output "$OUTPUT_DIR/latest_24h_FD.gif"

# Create 3-hour Full Disk GIF timelapse
echo "Creating 3h FD GIF timelapse..."
python3 "$PYTHON_SCRIPT" --received "$RECEIVED_DIR" --hours 3 --type FD --format gif --output "$OUTPUT_DIR/latest_3h_FD.gif"

echo "Timelapse creation completed!"
echo "Files saved to: $OUTPUT_DIR"
