#!/usr/bin/env python3

import os
import sys
import time
import schedule
import datetime
import subprocess
from pathlib import Path
import logging
import threading


class TimelapseService:
    def __init__(self, received_dir="received", check_interval=300):
        """
        Initialize timelapse service
        
        Args:
            received_dir: Path to received images directory
            check_interval: Seconds between file checks (default: 5 minutes)
        """
        self.received_dir = received_dir
        self.output_dir = os.path.join(received_dir, "timelapses")
        self.check_interval = check_interval
        self.timelapse_script = os.path.join(os.path.dirname(__file__), "timelapse.py")
        
        # Setup logging first
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - Timelapse Service - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)
        
        # Log initialization details
        self.logger.info(f"Initializing timelapse service...")
        self.logger.info(f"Received directory: {os.path.abspath(received_dir)}")
        self.logger.info(f"Output directory: {os.path.abspath(self.output_dir)}")
        self.logger.info(f"Timelapse script: {os.path.abspath(self.timelapse_script)}")
        
        # Check if directories exist
        if not os.path.exists(received_dir):
            self.logger.warning(f"Received directory does not exist: {received_dir}")
        
        if not os.path.exists(self.timelapse_script):
            self.logger.error(f"Timelapse script not found: {self.timelapse_script}")
        
        # Ensure output directory exists
        try:
            os.makedirs(self.output_dir, exist_ok=True)
            self.logger.info(f"✓ Timelapses directory created/verified: {self.output_dir}")
        except Exception as e:
            self.logger.error(f"✗ Failed to create timelapses directory: {e}")
            raise
        
        # Track last generation times
        self.last_generation = {
            '3h_mp4': None,
            '3h_gif': None, 
            '24h_mp4': None,
            '24h_gif': None
        }
        
        self.logger.info("Timelapse service initialized")
    
    def should_generate_timelapse(self, hours, format_type):
        """
        Check if a timelapse needs to be generated based on available images
        and last generation time
        """
        key = f"{hours}h_{format_type}"
        output_file = os.path.join(self.output_dir, f"latest_{key}.{format_type}")
        
        # Check if file exists and when it was last modified
        if os.path.exists(output_file):
            file_age = datetime.datetime.now() - datetime.datetime.fromtimestamp(os.path.getmtime(output_file))
            
            # Regeneration intervals based on GK-2A 10-minute image frequency:
            # 3h timelapses: regenerate every 30 minutes (3 new images)
            # 24h timelapses: regenerate every 2 hours (12 new images)
            max_age_hours = 0.5 if hours == 3 else 2
            
            if file_age.total_seconds() < max_age_hours * 3600:
                return False  # File is recent enough
        
        # Check if we have enough recent images
        return self.has_sufficient_images(hours)
    
    def has_sufficient_images(self, hours):
        """
        Check if we have enough images in the last N hours to create a meaningful timelapse
        Uses fallback to yesterday's images if needed
        
        GK-2A downlinks FD images every 10 minutes (6 per hour):
        - 3 hours: expect ~18 images
        - 24 hours: expect ~144 images
        """
        # Import here to avoid circular imports
        import sys
        sys.path.append(os.path.dirname(__file__))
        from timelapse import find_images
        
        try:
            images = find_images(self.received_dir, hours, "FD")
            
            # Expected images based on GK-2A 10-minute interval
            expected_images = hours * 6  # 6 images per hour
            # Minimum threshold: at least 50% of expected images
            min_images = max(5, expected_images // 2)
            
            if len(images) >= min_images:
                coverage_pct = (len(images) / expected_images) * 100
                self.logger.info(f"✓ Found {len(images)} images for {hours}h timelapse (expected: {expected_images}, coverage: {coverage_pct:.1f}%)")
                return True
            else:
                coverage_pct = (len(images) / expected_images) * 100 if expected_images > 0 else 0
                self.logger.warning(f"✗ Insufficient images for {hours}h timelapse: {len(images)} < {min_images} (expected: {expected_images}, coverage: {coverage_pct:.1f}%)")
                
                # If we have at least 5 images, attempt anyway for testing
                if len(images) >= 5:
                    self.logger.info(f"Will attempt timelapse with {len(images)} images anyway")
                    return True
                else:
                    self.logger.error("Too few images to create meaningful timelapse")
                    return False
                
        except Exception as e:
            self.logger.error(f"Error checking images for {hours}h timelapse: {e}")
            return False
    
    def generate_timelapse(self, hours, format_type):
        """
        Generate a single timelapse using the timelapse.py script
        """
        output_file = os.path.join(self.output_dir, f"latest_{hours}h_{format_type}.{format_type}")
        
        # Use the same Python executable that's running this service
        python_exe = sys.executable
        
        cmd = [
            python_exe, self.timelapse_script,
            "--received", self.received_dir,
            "--hours", str(hours),
            "--type", "FD",
            "--format", format_type,
            "--output", output_file
        ]
        
        try:
            self.logger.info(f"Starting {hours}h {format_type.upper()} timelapse generation...")
            self.logger.debug(f"Python executable: {python_exe}")
            self.logger.debug(f"Timelapse script: {self.timelapse_script}")
            self.logger.debug(f"Output file: {output_file}")
            self.logger.debug(f"Command: {' '.join(cmd)}")
            
            # Ensure output directory exists
            os.makedirs(os.path.dirname(output_file), exist_ok=True)
            
            # Run timelapse generation with timeout
            result = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True, 
                timeout=600  # 10 minute timeout
            )
            
            # Log all output for debugging
            if result.stdout:
                self.logger.debug(f"Stdout: {result.stdout}")
            if result.stderr:
                self.logger.debug(f"Stderr: {result.stderr}")
            
            if result.returncode == 0:
                self.logger.info(f"✓ {hours}h {format_type.upper()} timelapse completed: {output_file}")
                self.last_generation[f"{hours}h_{format_type}"] = datetime.datetime.now()
                return True
            else:
                error_msg = result.stderr or result.stdout or f"Process exited with code {result.returncode}"
                self.logger.error(f"✗ {hours}h {format_type.upper()} timelapse failed (code {result.returncode}): {error_msg}")
                
                # Check if FFmpeg is available (common issue)
                if "ffmpeg" in error_msg.lower() or result.returncode == 127:
                    self.logger.error("FFmpeg may not be installed or not in PATH")
                elif "permission" in error_msg.lower():
                    self.logger.error("Permission denied - check file/directory permissions")
                elif "no such file" in error_msg.lower():
                    self.logger.error("File not found - check paths and script availability")
                
                return False
                
        except subprocess.TimeoutExpired:
            self.logger.error(f"✗ {hours}h {format_type.upper()} timelapse timed out")
            return False
        except Exception as e:
            self.logger.error(f"✗ {hours}h {format_type.upper()} timelapse error: {e}")
            return False
    
    def generate_all_timelapses(self):
        """
        Generate all timelapse variants if needed
        """
        timelapses = [
            (3, "mp4"),
            (3, "gif"),
            (24, "mp4"),
            (24, "gif")
        ]
        
        for hours, format_type in timelapses:
            if self.should_generate_timelapse(hours, format_type):
                self.generate_timelapse(hours, format_type)
            else:
                self.logger.debug(f"Skipping {hours}h {format_type.upper()} - not needed")
    
    def startup_check(self):
        """
        Check and generate initial timelapses on startup
        For testing, force generation of at least one timelapse if none exist
        """
        self.logger.info("Performing startup timelapse check...")
        
        # Check if any timelapses exist
        existing_timelapses = self.list_available_timelapses()
        
        if not existing_timelapses:
            self.logger.info("No existing timelapses found - forcing generation of 24h MP4 for testing")
            # Force generation of at least one timelapse for testing
            self.generate_timelapse(24, "mp4")
            
        self.generate_all_timelapses()
        self.logger.info("Startup timelapse check completed")
    
    def scheduled_generation(self):
        """
        Scheduled timelapse generation (called every 30 minutes)
        """
        self.logger.info("=== Running scheduled timelapse generation ===")
        
        # Log current time and next scheduled run
        next_run = schedule.next_run()
        if next_run:
            self.logger.info(f"Next scheduled run: {next_run.strftime('%Y-%m-%d %H:%M:%S')}")
        
        generated_count = 0
        timelapses = [
            (3, "mp4"),
            (3, "gif"),
            (24, "mp4"),
            (24, "gif")
        ]
        
        for hours, format_type in timelapses:
            if self.should_generate_timelapse(hours, format_type):
                success = self.generate_timelapse(hours, format_type)
                if success:
                    generated_count += 1
            else:
                self.logger.debug(f"Skipping {hours}h {format_type.upper()} - not needed")
        
        if generated_count == 0:
            self.logger.info("No timelapses needed regeneration")
        else:
            self.logger.info(f"Generated {generated_count} timelapses")
            
        self.logger.info("=== Scheduled generation completed ===")
    
    def list_available_timelapses(self):
        """
        List all available timelapse files with metadata
        """
        timelapses = []
        
        for filename in os.listdir(self.output_dir):
            if filename.startswith("latest_") and filename.endswith(('.mp4', '.gif')):
                filepath = os.path.join(self.output_dir, filename)
                
                if os.path.isfile(filepath):
                    stat = os.stat(filepath)
                    timelapses.append({
                        'filename': filename,
                        'size': stat.st_size,
                        'created': datetime.datetime.fromtimestamp(stat.st_mtime).isoformat(),
                        'age_hours': (datetime.datetime.now() - datetime.datetime.fromtimestamp(stat.st_mtime)).total_seconds() / 3600
                    })
        
        return sorted(timelapses, key=lambda x: x['created'], reverse=True)
    
    def run_service(self):
        """
        Run the timelapse service with scheduled generation
        """
        self.logger.info("Starting timelapse background service...")
        
        # Perform initial startup check
        self.startup_check()
        
        # Schedule more frequent generation to match GK-2A image frequency
        # Check every 30 minutes for 3h timelapses (when 3 new images arrive)
        schedule.every(30).minutes.do(self.scheduled_generation)
        
        # Also check at the top of every hour for good measure
        schedule.every().hour.at(":00").do(self.scheduled_generation)
        
        self.logger.info("Timelapse service running - checking every 30 minutes")
        
        # Main service loop
        while True:
            try:
                schedule.run_pending()
                time.sleep(30)  # Check every 30 seconds for scheduled tasks
                
            except KeyboardInterrupt:
                self.logger.info("Timelapse service stopping...")
                break
            except Exception as e:
                self.logger.error(f"Service error: {e}")
                time.sleep(60)


def main():
    """
    Main entry point for timelapse service
    """
    import argparse
    
    parser = argparse.ArgumentParser(description="xrit-rx Timelapse Background Service")
    parser.add_argument("--received", default="received", help="Path to received images directory")
    parser.add_argument("--startup-only", action="store_true", help="Run startup check only, don't start service")
    parser.add_argument("--list", action="store_true", help="List available timelapses and exit")
    parser.add_argument("--test", action="store_true", help="Run a single test timelapse generation")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    parser.add_argument("--status", action="store_true", help="Show service status and schedule info")
    
    args = parser.parse_args()
    
    # Set debug logging if requested
    if args.debug:
        logging.basicConfig(level=logging.DEBUG, force=True)
    
    service = TimelapseService(args.received)
    
    if args.status:
        print("=== Timelapse Service Status ===")
        print(f"Current time: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        timelapses = service.list_available_timelapses()
        print(f"\nAvailable timelapses: {len(timelapses)}")
        for tl in timelapses:
            print(f"  {tl['filename']} - {tl['size']} bytes - {tl['age_hours']:.1f}h old")
        
        # Check image availability
        from timelapse import find_images
        for hours in [3, 24]:
            images = find_images(args.received, hours, "FD")
            expected = hours * 6
            coverage = (len(images) / expected * 100) if expected > 0 else 0
            print(f"\n{hours}h images: {len(images)}/{expected} ({coverage:.1f}% coverage)")
            
        return
    
    if args.list:
        timelapses = service.list_available_timelapses()
        print("Available timelapses:")
        for tl in timelapses:
            print(f"  {tl['filename']} - {tl['size']} bytes - {tl['age_hours']:.1f}h old")
        return
    
    if args.test:
        print("Running test timelapse generation...")
        service.logger.info("=== MANUAL TEST MODE ===")
        
        # Test image finding first
        from timelapse import find_images
        images = find_images(args.received, 24, "FD")
        print(f"Found {len(images)} images for testing")
        
        if len(images) > 0:
            print(f"Sample images: {images[:3]}...")
            success = service.generate_timelapse(24, "mp4")
            print(f"Test timelapse generation: {'SUCCESS' if success else 'FAILED'}")
        else:
            print("No images found for testing")
        return
    
    if args.startup_only:
        service.startup_check()
        return
    
    # Run the full service
    service.run_service()


if __name__ == "__main__":
    main()
