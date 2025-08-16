"""
xrit-rx.py
https://github.com/Zalgar/xrit-rx-docker

Frontend for CCSDS demultiplexer and image generator
Enhanced with real-time monitoring features

Original work by sam210723: https://github.com/sam210723/xrit-rx
"""

import ast
from argparse import ArgumentParser
from collections import namedtuple
import colorama
from colorama import Fore, Back, Style
from configparser import ConfigParser, NoOptionError, NoSectionError
import json
import logging
from os import mkdir, path, makedirs
import os
import socket
from time import time, sleep
import subprocess
from threading import Thread

from demuxer import Demuxer
import ccsds as CCSDS
from dash import Dashboard


# Globals
args = None             # Parsed CLI arguments
config = None           # Config parser object
stime = None            # Processing start time
source = None           # Input source type
spacecraft = None       # Spacecraft name
downlink = None         # Downlink type (LRIT/HRIT)
output = None           # Output path root
output_images = None    # Flag for saving Images to disk
output_xrit = None      # Flag for saving xRIT files to disk
blacklist = []          # VCID blacklist
packetf = None          # Packet file object
keypath = None          # Decryption key file path
keys = {}               # Decryption keys
sck = None              # TCP/UDP socket object
buflen = 892            # Input buffer length (1 VCDU)
demux = None            # Demuxer class object
dash = None             # Dashboard class object
timelapse_process = None  # Timelapse service process
dashe = None            # Dashboard enabled flag
dashp = None            # Dashboard HTTP port
dashi = None            # Dashboard update interval
log_level = None        # Logging level
log_max_size = None     # Log file max size in MB
log_backup_count = None # Number of backup log files
dashp = None            # Dashboard HTTP port
dashi = None            # Dashboard refresh interval (sec)
ver = "2.1.0"           # xrit-rx version


def start_timelapse_service():
    """
    Start the timelapse background service as a separate process
    """
    global timelapse_process
    
    try:
        timelapse_script = path.join(path.dirname(__file__), "tools", "timelapse_service.py")
        
        if not path.exists(timelapse_script):
            print(Fore.YELLOW + Style.BRIGHT + "TIMELAPSE SERVICE SCRIPT NOT FOUND - SKIPPING")
            return
            
        # Create log file for timelapse service debugging
        logs_dir = path.join(path.dirname(output), "logs")
        log_file = path.join(logs_dir, "timelapse_service.log")
        
        # Ensure the logs directory exists and is writable
        if not path.exists(logs_dir):
            try:
                mkdir(logs_dir)
            except PermissionError:
                print(Fore.YELLOW + Style.BRIGHT + f"PERMISSION DENIED creating logs directory: {logs_dir}")
                log_file = None
        
        # Test if we can write to the log file
        if log_file:
            try:
                with open(log_file, 'w') as test_log:
                    test_log.write(f"Timelapse service starting at {time()}\n")
            except PermissionError:
                print(Fore.YELLOW + Style.BRIGHT + f"PERMISSION DENIED for log file: {log_file}")
                print(Fore.YELLOW + Style.BRIGHT + "Running timelapse service without file logging")
                log_file = None
        
        # Start timelapse service as background process with logging
        if log_file:
            with open(log_file, 'a') as log:  # Use append mode
                timelapse_process = subprocess.Popen([
                    "python3", timelapse_script,
                    "--received", output
                ], stdout=log, stderr=subprocess.STDOUT)
        else:
            # Run without file logging if permissions don't allow it
            timelapse_process = subprocess.Popen([
                "python3", timelapse_script,
                "--received", output
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        print(Fore.GREEN + Style.BRIGHT + f"TIMELAPSE SERVICE STARTED (PID: {timelapse_process.pid})")
        if log_file:
            print(Fore.GREEN + Style.BRIGHT + f"TIMELAPSE LOG: {log_file}")
        else:
            print(Fore.YELLOW + Style.BRIGHT + "TIMELAPSE LOG: Console output disabled due to permissions")
        
    except Exception as e:
        print(Fore.YELLOW + Style.BRIGHT + f"TIMELAPSE SERVICE FAILED TO START: {e}")


def setup_log_cleanup(logs_dir):
    """
    Setup log cleanup to prevent logs from growing indefinitely
    Removes log files older than 30 days and limits total log files
    """
    import glob
    import time
    
    try:
        # Get all log files in the directory (including rotated ones)
        log_pattern = path.join(logs_dir, "*.log*")
        log_files = glob.glob(log_pattern)
        
        current_time = time.time()
        max_age_days = 30
        max_age_seconds = max_age_days * 24 * 60 * 60
        max_log_files = 50
        
        # Remove logs older than max_age_days
        old_files = []
        for log_file in log_files:
            try:
                file_age = current_time - path.getmtime(log_file)
                if file_age > max_age_seconds:
                    old_files.append(log_file)
            except OSError:
                continue
        
        # Remove old files
        for old_file in old_files:
            try:
                os.remove(old_file)
                print(f"Removed old log file: {path.basename(old_file)}")
            except OSError as e:
                print(f"Could not remove old log file {old_file}: {e}")
        
        # If still too many files, remove oldest ones
        remaining_files = [f for f in log_files if f not in old_files]
        if len(remaining_files) > max_log_files:
            # Sort by modification time (oldest first)
            remaining_files.sort(key=lambda x: path.getmtime(x))
            files_to_remove = remaining_files[:-max_log_files]
            
            for file_to_remove in files_to_remove:
                try:
                    os.remove(file_to_remove)
                    print(f"Removed excess log file: {path.basename(file_to_remove)}")
                except OSError as e:
                    print(f"Could not remove excess log file {file_to_remove}: {e}")
                    
    except Exception as e:
        print(f"Warning: Log cleanup failed: {e}")


def init():
    print("┌──────────────────────────────────────────────┐")
    print("│                   xrit-rx                    │")
    print("│         LRIT/HRIT Downlink Processor         │")
    print("├──────────────────────────────────────────────┤")
    print("│     @sam210723         vksdr.com/xrit-rx     │")
    print("└──────────────────────────────────────────────┘\n")
    
    global args
    global config
    global stime
    global output
    global demux
    global dash

    # Initialise Colorama
    colorama.init(autoreset=True)

    # Handle arguments and config file
    args = parse_args()
    config = parse_config(args.config)
    print_config()

    # Setup logging after config is parsed
    # Create logs directory if it doesn't exist
    try:
        logs_dir = path.join(path.dirname(output), "logs")
        if not path.exists(logs_dir):
            makedirs(logs_dir, exist_ok=True)
        
        log_file = path.join(logs_dir, 'xrit-rx.log')
        
        # Setup log rotation and cleanup
        setup_log_cleanup(logs_dir)
        
        # File logging only (no console for API requests)
        from logging.handlers import RotatingFileHandler
        
        # Convert log level string to logging constant
        level_map = {
            'DEBUG': logging.DEBUG,
            'INFO': logging.INFO,
            'WARNING': logging.WARNING,
            'ERROR': logging.ERROR
        }
        log_level_const = level_map.get(log_level, logging.INFO)
        
        # Use rotating file handler to automatically manage log size
        file_handler = RotatingFileHandler(
            log_file, 
            maxBytes=log_max_size*1024*1024,  # Convert MB to bytes
            backupCount=log_backup_count,
            mode='a'
        )
        
        logging.basicConfig(
            level=log_level_const,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[file_handler]
        )
        print(f"Logging configured: {log_file} (Level: {log_level}, {log_max_size}MB max, {log_backup_count} backups)")
        
    except Exception as e:
        # Fallback to console-only logging if file logging fails
        print(f"Warning: Could not setup file logging ({e}), using console only")
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[logging.StreamHandler()]
        )

    # Configure directories and input source
    dirs()
    config_input()

    # Load decryption keys
    load_keys()

    # Create demuxer instance
    demux_config = namedtuple('demux_config', 'spacecraft downlink verbose dump output images xrit blacklist keys')
    output_full_path = path.join(output, downlink)
    demux = Demuxer(
        demux_config(
            spacecraft,
            downlink,
            args.v,
            args.dump,
            output_full_path,
            output_images,
            output_xrit,
            blacklist,
            keys
        )
    )

    # Start dashboard server
    if dashe:
        dash_config = namedtuple('dash_config', 'port interval spacecraft downlink output images xrit blacklist version')
        dash = Dashboard(
            dash_config(
                dashp,
                dashi,
                spacecraft,
                downlink,
                output,
                output_images,
                output_xrit,
                blacklist,
                ver
            ),
            demux
        )

    # Start timelapse background service
    start_timelapse_service()

    # Check demuxer thread is ready
    if not demux.coreReady:
        print(Fore.WHITE + Back.RED + Style.BRIGHT + "DEMUXER CORE THREAD FAILED TO START")
        exit()

    print("──────────────────────────────────────────────────────────────────────────────────\n")

    # Get processing start time
    stime = time()

    # Enter main loop
    loop()


def loop():
    """
    Handles data from the selected input source
    """
    global demux
    global source
    global sck
    global buflen

    while True:
        if source == "GOESRECV":
            try:
                data = sck.recv(buflen + 8)
                # Validate received data
                if len(data) < 8:
                    print(Fore.YELLOW + "Warning: Received incomplete packet, skipping")
                    continue
                if len(data) > buflen + 8:
                    print(Fore.YELLOW + f"Warning: Received oversized packet ({len(data)} bytes), truncating")
                    data = data[:buflen + 8]
            except ConnectionResetError:
                logging.error("Lost connection to goesrecv")
                print(Fore.WHITE + Back.RED + Style.BRIGHT + "LOST CONNECTION TO GOESRECV")
                safe_stop()
            except Exception as e:
                logging.error(f"Error receiving data from goesrecv: {e}")
                print(Fore.RED + f"GOESRECV ERROR: {e}")
                safe_stop()

            if len(data) == buflen + 8:
                demux.push(data[8:])
        
        elif source == "OSP":
            try:
                data = sck.recv(buflen)
                # Validate received data size
                if len(data) == 0:
                    print(Fore.YELLOW + "Warning: Received empty packet from OSP")
                    continue
                if len(data) > buflen:
                    print(Fore.YELLOW + f"Warning: Received oversized OSP packet ({len(data)} bytes), truncating")
                    data = data[:buflen]
            except ConnectionResetError:
                logging.error("Lost connection to Open Satellite Project")
                print(Fore.WHITE + Back.RED + Style.BRIGHT + "LOST CONNECTION TO OPEN SATELLITE PROJECT")
                safe_stop()
            except Exception as e:
                logging.error(f"Error receiving data from OSP: {e}")
                print(Fore.RED + f"OSP ERROR: {e}")
                safe_stop()
            
            demux.push(data)
        
        elif source == "UDP":
            try:
                data, address = sck.recvfrom(buflen)
                # Validate UDP data
                if len(data) == 0:
                    print(Fore.YELLOW + "Warning: Received empty UDP packet")
                    continue
                if len(data) > buflen:
                    print(Fore.YELLOW + f"Warning: Received oversized UDP packet ({len(data)} bytes), truncating")
                    data = data[:buflen]
            except Exception as e:
                logging.error(f"UDP receive error: {e}")
                print(f"UDP receive error: {e}")
                safe_stop()
            
            demux.push(data)

        elif source == "FILE":
            global packetf
            global stime

            if not packetf.closed:
                # Read VCDU from file
                data = packetf.read(buflen)

                # No more data to read from file
                if data == b'':
                    #print("INPUT FILE LOADED")
                    packetf.close()

                    # Append single fill VCDU (VCID 63)
                    # Triggers TP_File processing inside channel handlers
                    demux.push(b'\x70\xFF\x00\x00\x00\x00')

                    continue
                
                # Push VCDU to demuxer
                demux.push(data)
            else:
                # Demuxer has all VCDUs from file, wait for processing
                if demux.complete():
                    runTime = round(time() - stime, 3)
                    print("\nFINISHED PROCESSING FILE ({}s)".format(runTime))
                    safe_stop()
                else:
                    # Limit loop speed when waiting for demuxer to finish processing
                    sleep(0.5)


def config_input():
    """
    Configures the selected input source
    """

    global source
    global sck

    if source == "GOESRECV":
        sck = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        ip = config.get('goesrecv', 'ip')
        port = int(config.get('goesrecv', 'vchan'))
        addr = (ip, port)

        print("Connecting to goesrecv ({})...".format(ip), end='')
        connect_socket(addr)
        nanomsg_init()
    
    elif source == "OSP":
        sck = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        ip = config.get('osp', 'ip')
        port = int(config.get('osp', 'vchan'))
        addr = (ip, port)

        print("Connecting to Open Satellite Project ({})...".format(ip), end='')
        connect_socket(addr)
    
    elif source == "UDP":
        sck = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        ip = config.get('udp', 'ip')
        port = int(config.get('udp', 'vchan'))
        addr = (ip, port)
        
        print("Binding UDP socket ({}:{})...".format(ip, port), end='')
        try:
            sck.bind(addr)
            print(Fore.GREEN + Style.BRIGHT + "SUCCESS")
        except socket.error as e:
            print(Fore.WHITE + Back.RED + Style.BRIGHT + "FAILED")
            print(e)
            safe_stop()

    elif source == "FILE":
        global packetf

        # Check VCDU file exists
        if not path.exists(args.file):
            print(Fore.WHITE + Back.RED + Style.BRIGHT + "INPUT FILE DOES NOT EXIST")
            safe_stop()
        
        packetf = open(args.file, 'rb')
        print(Fore.GREEN + Style.BRIGHT + "OPENED PACKET FILE")

    else:
        print(Fore.WHITE + Back.RED + Style.BRIGHT + "UNKNOWN INPUT MODE: \"{}\"".format(source))
        safe_stop()


def connect_socket(addr):
    """
    Connects TCP socket to address and handle exceptions
    """

    try:
        sck.connect(addr)
        print(Fore.GREEN + Style.BRIGHT + "CONNECTED")
    except socket.error as e:
        if e.errno == 10061:
            print(Fore.WHITE + Back.RED + Style.BRIGHT + "CONNECTION REFUSED")
        else:
            print(e)
    
        safe_stop()


def nanomsg_init():
    """
    Sets up nanomsg publisher in goesrecv to send VCDUs over TCP
    """

    global sck

    sck.send(b'\x00\x53\x50\x00\x00\x21\x00\x00')
    nmres = sck.recv(8)

    # Check nanomsg response
    if nmres != b'\x00\x53\x50\x00\x00\x20\x00\x00':
        print(Fore.WHITE + Back.RED + Style.BRIGHT + "  ERROR CONFIGURING NANOMSG (BAD RESPONSE)")
        safe_stop()


def dirs():
    """
    Configures directories for demuxed files
    """

    global downlink
    global output

    output_path = path.abspath(output)
    
    # Create output directory if it doesn't exist already
    if not path.isdir(output_path):
        try:
            mkdir(output_path)
        except OSError as e:
            print(Fore.WHITE + Back.RED + Style.BRIGHT + "ERROR CREATING OUTPUT FOLDERS\n{}".format(e))
            safe_stop()
    
    downlink_path = path.join(output_path, downlink)
    if not path.isdir(downlink_path):
        try:
            mkdir(downlink_path)

            print(Fore.GREEN + Style.BRIGHT + "CREATED OUTPUT FOLDERS")
        except OSError as e:
            print(Fore.WHITE + Back.RED + Style.BRIGHT + "ERROR CREATING OUTPUT FOLDERS\n{}".format(e))
            safe_stop()


def load_keys():
    """
    Loads key file and parses keys
    """

    global keypath
    global keys
    global output_images
    global output_xrit

    # Check key file exists
    if not path.exists(keypath):
        print(Fore.WHITE + Back.RED + Style.BRIGHT + "KEY FILE NOT FOUND: ONLY ENCRYPTED XRIT FILES WILL BE SAVED")
        
        # Only output xRIT files
        output_images = False
        output_xrit = True
        
        return False

    # Load key file
    keyf = open(keypath, mode='rb')
    fbytes = keyf.read()

    # Parse key count
    count = int.from_bytes(fbytes[:2], byteorder='big')

    # Parse keys
    for i in range(count):
        offset = (i * 10) + 2
        index = fbytes[offset : offset + 2]
        key = fbytes[offset + 2 : offset + 10]

        '''
        # Print keys
        i = hex(int.from_bytes(index, byteorder='big')).upper()[2:]
        k = hex(int.from_bytes(key, byteorder='big')).upper()[2:]
        print("{}: {}".format(i, k))
        '''

        # Add key to dictionary
        keys[index] = key

    print(Fore.GREEN + Style.BRIGHT + "DECRYPTION KEYS LOADED")
    return True


def parse_args():
    """
    Parses command line arguments
    """
    
    argp = ArgumentParser()
    argp.description = "Frontend for CCSDS demultiplexer"
    argp.add_argument("--config", action="store", help="Configuration file path (.ini)", default="xrit-rx.ini")
    argp.add_argument("--file", action="store", help="Path to VCDU packet file", default=None)
    argp.add_argument("-v", action="store_true", help="Enable verbose console output (only useful for debugging)", default=False)
    argp.add_argument("--dump", action="store", help="Dump VCDUs (except fill) to file (only useful for debugging)", default=None)

    return argp.parse_args()


def parse_config(path):
    """
    Parses configuration file
    """

    global source
    global spacecraft
    global downlink
    global output
    global output_images
    global output_xrit
    global blacklist
    global keypath
    global dashe
    global dashp
    global dashi
    global log_level
    global log_max_size
    global log_backup_count

    cfgp = ConfigParser()
    cfgp.read(path)

    if args.file is None:
        source = cfgp.get('rx', 'input').upper()
    else:
        source = "FILE"
    
    try:
        spacecraft = cfgp.get('rx', 'spacecraft').upper()
        downlink = cfgp.get('rx', 'mode').upper()
        output = cfgp.get('output', 'path')
        output_images = cfgp.getboolean('output', 'images')
        output_xrit = cfgp.getboolean('output', 'xrit')
        bl = cfgp.get('output', 'channel_blacklist')
        keypath = cfgp.get('rx', 'keys')
        dashe = cfgp.getboolean('dashboard', 'enabled')
        dashp = cfgp.get('dashboard', 'port')
        dashi = round((float(cfgp.get('dashboard', 'interval'))), 1)
        
        # Parse logging config with defaults
        try:
            log_level = cfgp.get('logging', 'level').upper()
        except (NoSectionError, NoOptionError):
            log_level = 'INFO'
            
        try:
            log_max_size = int(cfgp.get('logging', 'max_size_mb'))
        except (NoSectionError, NoOptionError):
            log_max_size = 10
            
        try:
            log_backup_count = int(cfgp.get('logging', 'backup_count'))
        except (NoSectionError, NoOptionError):
            log_backup_count = 5
    except (NoSectionError, NoOptionError) as e:
        print(Fore.WHITE + Back.RED + Style.BRIGHT + "ERROR PARSING CONFIG FILE: " + str(e).upper())
        safe_stop()

    # Validate configuration values
    try:
        dashp = int(dashp)
        if not (1 <= dashp <= 65535):
            raise ValueError("Dashboard port must be between 1 and 65535")
    except ValueError as e:
        print(Fore.WHITE + Back.RED + Style.BRIGHT + "ERROR: Invalid dashboard port - " + str(e))
        safe_stop()

    # Limit dashboard refresh interval
    if dashi < 1:
        dashi = 1

    # If VCID blacklist is not empty
    if bl != "":
        # Parse blacklist string into int or list using JSON (safer than ast.literal_eval)
        try:
            blacklist = json.loads(bl)
        except json.JSONDecodeError:
            print(Fore.YELLOW + Style.BRIGHT + f"Warning: Invalid blacklist format '{bl}', using empty blacklist")
            blacklist = []

        # If parsed into int, wrap int in list
        if isinstance(blacklist, int):
            blacklist = [blacklist]
        elif not isinstance(blacklist, list):
            print(Fore.YELLOW + Style.BRIGHT + f"Warning: Blacklist must be int or list, got {type(blacklist)}, using empty blacklist")
            blacklist = []

    return cfgp


def print_config():
    """
    Prints configuration information
    """

    print("SPACECRAFT:       {}".format(spacecraft))

    if downlink == "LRIT":
        rate = "64 kbps"
    elif downlink == "HRIT":
        rate = "3 Mbps"
    print("DOWNLINK:         {} ({})".format(downlink, rate))

    if source == "GOESRECV":
        s = "goesrecv (github.com/sam210723/goestools)"
    elif source == "OSP":
        s = "Open Satellite Project (github.com/opensatelliteproject/xritdemod)"
    elif source == "FILE":
        s = "File ({})".format(args.file)
    else:
        s = "UNKNOWN"

    print("INPUT SOURCE:     {}".format(s))
    
    absp = path.abspath(output)
    absp = absp[0].upper() + absp[1:]  # Fix lowercase drive letter
    print("OUTPUT PATH:      {}".format(absp))

    if (len(blacklist) == 0):
        print("IGNORED VCIDs:    None")
    else:
        blacklist_str = ""
        for i, c in enumerate(blacklist):
            if i > 0: blacklist_str += ", "
            blacklist_str += "{} ({})".format(c, CCSDS.VCDU.get_VC(None, int(c)))
        
        print("IGNORED VCIDs:    {}".format(blacklist_str))
    
    print("KEY FILE:         {}".format(keypath))
    
    if dashe:
        print("DASHBOARD:        ENABLED (port {})".format(dashp))
    else:
        print("DASHBOARD:        DISABLED")
    
    print("VERSION:          {}\n".format(ver))
    
    if args.dump:
        print(Fore.GREEN + Style.BRIGHT + "WRITING PACKETS TO: \"{}\"".format(args.dump))


def safe_stop(message=True):
    """
    Safely kill threads and exit
    """
    global timelapse_process

    if demux is not None:
        demux.stop()
    if dash is not None:
        dash.stop()
    if timelapse_process is not None:
        try:
            timelapse_process.terminate()
            timelapse_process.wait(timeout=5)
        except:
            timelapse_process.kill()

    if message:
        print("\nExiting...")
    exit()


try:
    init()
except KeyboardInterrupt:
    safe_stop()
