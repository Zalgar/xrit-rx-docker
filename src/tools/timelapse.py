#!/usr/bin/env python3

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
    
    print(f"Looking for {image_type} images from the last {hours_back} hours (since {cutoff_time.strftime('%Y-%m-%d %H:%M')})...")
    
    # First pass: look for images in the specified timeframe
    image_files = _search_images_in_timeframe(received_path, cutoff_time, now, image_type)
    
    print(f"Found {len(image_files)} images in primary search")
    
    # If we don't have enough images (less than 5), expand search to include yesterday
    if len(image_files) < 5:
        print(f"Not enough images found, expanding search to include yesterday...")
        
        # Search the previous 24 hours before our cutoff
        extended_cutoff = cutoff_time - datetime.timedelta(hours=24)
        yesterday_images = _search_images_in_timeframe(received_path, extended_cutoff, cutoff_time, image_type)
        
        print(f"Found {len(yesterday_images)} additional images from yesterday")
        
        # Combine all images and remove duplicates
        all_images = list(set(image_files + yesterday_images))
        
        # Sort by timestamp
        def get_timestamp(filepath):
            try:
                filename = os.path.basename(filepath)
                parts = filename.split('_')
                if len(parts) >= 6:
                    date_part = parts[4]  # 20250810
                    time_part = parts[5].split('.')[0]  # 075006
                    return datetime.datetime.strptime(f"{date_part}_{time_part}", "%Y%m%d_%H%M%S")
            except:
                pass
            return datetime.datetime.min
        
        all_images.sort(key=get_timestamp)
        
        # Take the most recent images (up to 2 per hour requested)
        max_images = min(len(all_images), hours_back * 2)
        image_files = all_images[-max_images:] if all_images else []
        
        print(f"Final selection: {len(image_files)} images")
    
    return image_files


def _search_images_in_timeframe(received_path, start_time, end_time, image_type):
    """
    Search for images within a specific timeframe
    """
    image_files = []
    
    # Search through date directories
    for date_dir in glob.glob(os.path.join(received_path, "LRIT", "*")):
        if not os.path.isdir(date_dir):
            continue
            
        date_str = os.path.basename(date_dir)
        try:
            date_obj = datetime.datetime.strptime(date_str, "%Y%m%d")
            
            # Skip directories outside our timeframe
            if date_obj.date() < start_time.date() or date_obj.date() > end_time.date():
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
                            
                            # Check if within timeframe
                            if start_time <= file_time <= end_time:
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
    
    print(f"Preparing {len(image_files)} images in {temp_dir}...")
    
    # Create symlinks with sequential names for FFmpeg
    for i, image_file in enumerate(image_files):
        symlink_path = os.path.join(temp_dir, f"frame_{i:06d}.jpg")
        
        # Convert relative path to absolute path
        abs_image_path = os.path.abspath(image_file)
        
        # Remove existing symlink if present
        if os.path.exists(symlink_path):
            os.unlink(symlink_path)
            
        # Verify source image exists
        if not os.path.exists(abs_image_path):
            print(f"Warning: Source image not found: {abs_image_path}")
            continue
            
        try:
            os.symlink(abs_image_path, symlink_path)
            print(f"Created symlink {i+1}/{len(image_files)}: {symlink_path} -> {abs_image_path}")
        except OSError as e:
            print(f"Failed to create symlink for {abs_image_path}: {e}")
            # Fallback: copy the file instead of symlinking
            import shutil
            try:
                shutil.copy2(abs_image_path, symlink_path)
                print(f"Copied file instead: {symlink_path}")
            except Exception as copy_e:
                print(f"Failed to copy file: {copy_e}")
                continue
    
    # Verify we have the expected number of frame files
    frame_files = glob.glob(os.path.join(temp_dir, "frame_*.jpg"))
    print(f"Created {len(frame_files)} frame files for FFmpeg")
    
    if len(frame_files) == 0:
        print("Error: No frame files were created")
        return False
    
    try:
        if format_type.lower() == "gif":
            # Create GIF with palette optimization (two-pass process)
            print("Generating palette for GIF optimization...")
            
            # First pass: generate palette
            palette_cmd = [
                "ffmpeg", "-y",
                "-framerate", str(framerate),
                "-i", f"{temp_dir}/frame_%06d.jpg",
                "-vf", "fps=5,scale=640:-1:flags=lanczos,palettegen=reserve_transparent=0",
                "/tmp/palette.png"
            ]
            subprocess.run(palette_cmd, check=True, capture_output=True)
            
            print("Creating GIF with optimized palette...")
            
            # Second pass: create GIF using palette
            gif_cmd = [
                "ffmpeg", "-y",
                "-framerate", str(framerate),
                "-i", f"{temp_dir}/frame_%06d.jpg",
                "-i", "/tmp/palette.png",
                "-filter_complex", "[0:v]fps=5,scale=640:-1:flags=lanczos[v];[v][1:v]paletteuse=dither=bayer:bayer_scale=5",
                output_path
            ]
            result = subprocess.run(gif_cmd, check=True, capture_output=True, text=True)
        else:
            # Create MP4
            print("Creating MP4 timelapse...")
            mp4_cmd = [
                "ffmpeg", "-y",
                "-framerate", str(framerate),
                "-i", f"{temp_dir}/frame_%06d.jpg",
                "-c:v", "libx264",
                "-pix_fmt", "yuv420p",
                "-crf", "23",
                "-preset", "medium",
                output_path
            ]
            result = subprocess.run(mp4_cmd, check=True, capture_output=True, text=True)
        
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
