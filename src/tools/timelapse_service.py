#!/usr/bin/env python3
"""
Timelapse Background Service for xrit-rx
Runs as a separate process to generate timelapses at regular intervals

Original work by sam210723 (https://github.com/sam210723/xrit-rx)
Enhanced version by Zalgar (https://github.com/Zalgar/xrit-rx-docker)
"""

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
        
        # Ensure output directory exists
        os.makedirs(self.output_dir, exist_ok=True)
        
        # Setup logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - Timelapse Service - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)
        
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
            
            # 3h timelapses: regenerate every hour
            # 24h timelapses: regenerate every 3 hours
            max_age_hours = 1 if hours == 3 else 3
            
            if file_age.total_seconds() < max_age_hours * 3600:
                return False  # File is recent enough
        
        # Check if we have enough recent images
        return self.has_sufficient_images(hours)
    
    def has_sufficient_images(self, hours):
        """
        Check if we have enough images in the last N hours to create a meaningful timelapse
        """
        # Import here to avoid circular imports
        import sys
        sys.path.append(os.path.dirname(__file__))
        from timelapse import find_images
        
        try:
            images = find_images(self.received_dir, hours, "FD")
            min_images = 6 if hours == 3 else 12  # Minimum images for a decent timelapse
            
            if len(images) >= min_images:
                self.logger.info(f"Found {len(images)} images for {hours}h timelapse")
                return True
            else:
                self.logger.info(f"Insufficient images for {hours}h timelapse: {len(images)} < {min_images}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error checking images for {hours}h timelapse: {e}")
            return False
    
    def generate_timelapse(self, hours, format_type):
        """
        Generate a single timelapse using the timelapse.py script
        """
        output_file = os.path.join(self.output_dir, f"latest_{hours}h_{format_type}.{format_type}")
        
        cmd = [
            "python3", self.timelapse_script,
            "--received", self.received_dir,
            "--hours", str(hours),
            "--type", "FD",
            "--format", format_type,
            "--output", output_file
        ]
        
        try:
            self.logger.info(f"Starting {hours}h {format_type.upper()} timelapse generation...")
            
            # Run timelapse generation with timeout
            result = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True, 
                timeout=600  # 10 minute timeout
            )
            
            if result.returncode == 0:
                self.logger.info(f"✓ {hours}h {format_type.upper()} timelapse completed: {output_file}")
                self.last_generation[f"{hours}h_{format_type}"] = datetime.datetime.now()
                return True
            else:
                self.logger.error(f"✗ {hours}h {format_type.upper()} timelapse failed: {result.stderr}")
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
        """
        self.logger.info("Performing startup timelapse check...")
        self.generate_all_timelapses()
        self.logger.info("Startup timelapse check completed")
    
    def scheduled_generation(self):
        """
        Scheduled timelapse generation (called hourly)
        """
        self.logger.info("Running scheduled timelapse generation...")
        self.generate_all_timelapses()
    
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
        
        # Schedule hourly generation
        schedule.every().hour.at(":00").do(self.scheduled_generation)
        
        self.logger.info("Timelapse service running - will generate timelapses hourly")
        
        # Main service loop
        while True:
            try:
                schedule.run_pending()
                time.sleep(60)  # Check every minute for scheduled tasks
                
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
    
    args = parser.parse_args()
    
    service = TimelapseService(args.received)
    
    if args.list:
        timelapses = service.list_available_timelapses()
        print("Available timelapses:")
        for tl in timelapses:
            print(f"  {tl['filename']} - {tl['size']} bytes - {tl['age_hours']:.1f}h old")
        return
    
    if args.startup_only:
        service.startup_check()
        return
    
    # Run the full service
    service.run_service()


if __name__ == "__main__":
    main()
