#!/usr/bin/env python3
"""
GK-2A LRIT Timelapse Generator
Creates timelapse videos and GIFs from received satellite images

Original work by sam210723 (https://github.com/sam210723/xrit-rx)
Enhanced version by Zalgar (https://github.com/Zalgar/xrit-rx-docker)
"""

import os
import sys
import glob
import subprocess
import datetime
from pathlib import Path
import argparse


def find_images(received_path, hours_back=24, image_type="FD"):
    """
    Find images from the last N hours for timelapse creation
    
    Args:
        received_path: Path to received images directory
        hours_back: Number of hours to look back
        image_type: Type of images to include (FD, etc.)
    
    Returns:
        List of image file paths sorted by timestamp
    """
    now = datetime.datetime.now()
    cutoff_time = now - datetime.timedelta(hours=hours_back)
    
    image_files = []
    
    # Search through date directories
    for date_dir in glob.glob(os.path.join(received_path, "LRIT", "*")):
        if not os.path.isdir(date_dir):
            continue
            
        date_str = os.path.basename(date_dir)
        try:
            date_obj = datetime.datetime.strptime(date_str, "%Y%m%d")
            
            # Skip directories older than our cutoff
            if date_obj.date() < cutoff_time.date():
                continue
                
            # Look for images in the specified type directory
            type_dir = os.path.join(date_dir, image_type)
            if os.path.exists(type_dir):
                pattern = os.path.join(type_dir, "*IR105*.jpg")
                files = glob.glob(pattern)
                
                for file_path in files:
                    # Extract timestamp from filename
                    filename = os.path.basename(file_path)
                    try:
                        # Extract timestamp from filename like IMG_FD_047_IR105_20250810_075006.jpg
                        parts = filename.split('_')
                        if len(parts) >= 6:
                            date_part = parts[4]  # 20250810
                            time_part = parts[5].split('.')[0]  # 075006
                            
                            timestamp_str = f"{date_part}_{time_part}"
                            file_time = datetime.datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")
                            
                            if file_time >= cutoff_time:
                                image_files.append((file_time, file_path))
                    except (ValueError, IndexError):
                        continue
                        
        except ValueError:
            continue
    
    # Sort by timestamp and return just the file paths
    image_files.sort(key=lambda x: x[0])
    return [f[1] for f in image_files]


def create_timelapse(image_files, output_path, format_type="mp4", framerate=10):
    """
    Create timelapse video or GIF from image files
    
    Args:
        image_files: List of image file paths
        output_path: Output file path
        format_type: Output format ("mp4" or "gif")
        framerate: Frames per second
    
    Returns:
        True if successful, False otherwise
    """
    if not image_files:
        print("No images found for timelapse creation")
        return False
    
    print(f"Creating {format_type.upper()} timelapse from {len(image_files)} images...")
    
    # Create temporary file list for FFmpeg
    temp_dir = "/tmp/timelapse"
    os.makedirs(temp_dir, exist_ok=True)
    
    # Create symlinks with sequential names for FFmpeg
    for i, image_file in enumerate(image_files):
        symlink_path = os.path.join(temp_dir, f"frame_{i:06d}.jpg")
        if os.path.exists(symlink_path):
            os.unlink(symlink_path)
        os.symlink(image_file, symlink_path)
    
    try:
        if format_type.lower() == "gif":
            # Create GIF with palette optimization
            cmd = [
                "ffmpeg", "-y",
                "-framerate", str(framerate),
                "-i", f"{temp_dir}/frame_%06d.jpg",
                "-vf", "fps=5,scale=640:-1:flags=lanczos,palettegen=reserve_transparent=0",
                "-t", "1",
                "/tmp/palette.png"
            ]
            subprocess.run(cmd, check=True, capture_output=True)
            
            cmd = [
                "ffmpeg", "-y",
                "-framerate", str(framerate),
                "-i", f"{temp_dir}/frame_%06d.jpg",
                "-i", "/tmp/palette.png",
                "-vf", "fps=5,scale=640:-1:flags=lanczos [x]; [x][1:v] paletteuse=dither=bayer:bayer_scale=5",
                output_path
            ]
        else:
            # Create MP4
            cmd = [
                "ffmpeg", "-y",
                "-framerate", str(framerate),
                "-i", f"{temp_dir}/frame_%06d.jpg",
                "-c:v", "libx264",
                "-pix_fmt", "yuv420p",
                "-crf", "23",
                "-preset", "medium",
                output_path
            ]
        
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print(f"Timelapse created successfully: {output_path}")
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"FFmpeg error: {e.stderr}")
        return False
    finally:
        # Clean up temporary files
        for temp_file in glob.glob(f"{temp_dir}/frame_*.jpg"):
            os.unlink(temp_file)
        if os.path.exists("/tmp/palette.png"):
            os.unlink("/tmp/palette.png")


def main():
    parser = argparse.ArgumentParser(description="Create timelapse from GK-2A LRIT images")
    parser.add_argument("--received", default="received", help="Path to received images directory")
    parser.add_argument("--hours", type=int, default=24, help="Hours of images to include (default: 24)")
    parser.add_argument("--type", default="FD", help="Image type to include (default: FD)")
    parser.add_argument("--format", choices=["mp4", "gif"], default="mp4", help="Output format (default: mp4)")
    parser.add_argument("--framerate", type=int, default=10, help="Framerate for video (default: 10)")
    parser.add_argument("--output", help="Output file path (auto-generated if not specified)")
    
    args = parser.parse_args()
    
    # Auto-generate output filename if not specified
    if not args.output:
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"timelapse_{args.type}_{args.hours}h_{timestamp}.{args.format}"
        args.output = os.path.join(args.received, "timelapses", filename)
        
        # Create timelapses directory
        os.makedirs(os.path.dirname(args.output), exist_ok=True)
    
    # Find images
    image_files = find_images(args.received, args.hours, args.type)
    
    if not image_files:
        print(f"No {args.type} images found in the last {args.hours} hours")
        return 1
    
    # Create timelapse
    success = create_timelapse(image_files, args.output, args.format, args.framerate)
    
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
