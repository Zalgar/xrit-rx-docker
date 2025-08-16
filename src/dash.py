"""
dash.py
https://github.com/Zalgar/xrit-rx-docker

Dashboard HTTP server
Enhanced with real-time progress tracking and partial image features

Original work by sam210723: https://github.com/sam210723/xrit-rx
"""

from colorama import Fore, Back, Style
import http.server
import json
import logging
import mimetypes
import os
import socketserver
import subprocess
from threading import Thread
import time

dash_config = None
demuxer_instance = None

class Dashboard:
    def __init__(self, config, demuxer):
        global dash_config
        global demuxer_instance

        dash_config = config
        demuxer_instance = demuxer

        self.socket = None
        max_retries = 10  # Maximum number of retry attempts
        retry_delay = 2   # Delay in seconds between retries
        
        for attempt in range(max_retries):
            try:
                self.socket = socketserver.TCPServer(("", int(dash_config.port)), Handler)
                print(Fore.GREEN + Style.BRIGHT + "DASHBOARD STARTED ON PORT {}".format(dash_config.port))
                break  # Success, exit the retry loop
            except OSError as e:
                if e.errno == 10048 or "Address already in use" in str(e):
                    if attempt < max_retries - 1:  # Not the last attempt
                        print(Fore.YELLOW + Style.BRIGHT + "DASHBOARD PORT {} IN USE, RETRYING IN {}s (ATTEMPT {}/{})".format(
                            dash_config.port, retry_delay, attempt + 1, max_retries))
                        time.sleep(retry_delay)
                    else:  # Last attempt failed
                        print("\n" + Fore.WHITE + Back.RED + Style.BRIGHT + 
                              "DASHBOARD NOT STARTED: PORT {} STILL IN USE AFTER {} ATTEMPTS".format(
                                  dash_config.port, max_retries))
                        return
                else:
                    # Different error, don't retry
                    print("\n" + Fore.WHITE + Back.RED + Style.BRIGHT + "DASHBOARD NOT STARTED: {}".format(str(e)))
                    return
        
        # If we get here without a socket, something went wrong
        if self.socket is None:
            return

        # Start HTTP server thread
        self.httpd_thread = Thread()
        self.httpd_thread.name = "HTTP SERVER"
        self.httpd_thread.run = self.http_server
        self.httpd_thread.start()


    def http_server(self):
        """
        HTTP server and request handler thread
        """

        self.socket.serve_forever()
    

    def stop(self):
        """
        Stops the HTTP server thread
        """

        try:
            if self.socket is not None:
                self.socket.shutdown()
        except AttributeError:
            return


class Handler(http.server.SimpleHTTPRequestHandler):
    """
    Custom HTTP request handler
    """

    def __init__(self, request, client_address, server):
        try:
            super().__init__(request, client_address, server)
        except ConnectionResetError:
            return


    def do_GET(self):
        """
        Respond to GET requests
        """
        # Log the request for security monitoring
        client_ip = self.client_address[0]
        
        # Use different log levels: DEBUG for API requests, INFO for others
        if self.path.startswith("/api/") or self.path == "/api":
            logging.debug(f"API request from {client_ip}: {self.path}")
        else:
            logging.info(f"HTTP GET request from {client_ip}: {self.path}")

        # Respond with index.html content on root path requests
        if self.path == "/": self.path = "index.html"
        
        try:
            if self.path.startswith("/api/") or self.path == "/api":    # API endpoint requests
                content, status, mime = self.handle_api(self.path)

                self.send_response(status)
                self.send_header('Content-type', mime)
                self.end_headers()
                self.wfile.write(content)
            else:                                                       # Local file requests
                self.path = "html/{}".format(self.path)

                if os.path.isfile(self.path):                           # Requested file exists (HTTP 200)
                    self.send_response(200)
                    mime = mimetypes.guess_type(self.path)[0]
                    self.send_header('Content-type', mime)
                    self.end_headers()

                    self.wfile.write(
                        open(self.path, 'rb').read()
                    )
                else:                                                   # Requested file not found (HTTP 404)
                    self.send_response(404)
                    self.end_headers()
        except (ConnectionAbortedError, ConnectionResetError, BrokenPipeError):
            # Client disconnected, nothing we can do
            return
        except Exception as e:
            # Log other exceptions but don't crash
            print(f"HTTP Server Error: {e}")
            return
    

    def do_HEAD(self):
        """
        Respond to HEAD requests (same as GET but without body)
        """
        # Log the request for security monitoring
        client_ip = self.client_address[0]
        
        # Use different log levels: DEBUG for API requests, INFO for others
        if self.path.startswith("/api/") or self.path == "/api":
            logging.debug(f"API HEAD request from {client_ip}: {self.path}")
        else:
            logging.info(f"HTTP HEAD request from {client_ip}: {self.path}")
        
        # Respond with index.html content on root path requests
        if self.path == "/": self.path = "index.html"
        
        try:
            if self.path.startswith("/api/") or self.path == "/api":    # API endpoint requests
                content, status, mime = self.handle_api(self.path)

                self.send_response(status)
                self.send_header('Content-type', mime)
                self.send_header('Content-Length', str(len(content) if isinstance(content, bytes) else len(str(content).encode('utf-8'))))
                self.end_headers()
                # Don't send body for HEAD requests
            else:                                                       # Local file requests
                # Sanitize and validate file path
                requested_path = self.path.lstrip('/')
                safe_path = self.sanitize_file_path(requested_path)
                if safe_path is None:
                    self.send_response(403)
                    self.end_headers()
                    return
                
                self.path = safe_path

                if os.path.isfile(self.path):                           # Requested file exists (HTTP 200)
                    self.send_response(200)
                    mime = mimetypes.guess_type(self.path)[0]
                    self.send_header('Content-type', mime)
                    
                    # Get file size for Content-Length header
                    file_size = os.path.getsize(self.path)
                    self.send_header('Content-Length', str(file_size))
                    self.end_headers()
                    # Don't send body for HEAD requests
                else:                                                   # Requested file not found (HTTP 404)
                    self.send_response(404)
                    self.end_headers()
        except (ConnectionAbortedError, ConnectionResetError, BrokenPipeError):
            # Client disconnected, nothing we can do
            return
        except Exception as e:
            # Log other exceptions but don't crash
            print(f"HTTP HEAD Server Error: {e}")
            return


    def handle_api(self, path):
        """
        Handle API endpoint request
        """

        # Base response object
        content = b''
        status = 404
        mime = "application/json"

        # Requested endpoint path
        path = path.replace("/api", "").split("/")
        path = None if len(path) == 1 else path[1:]

        # Validate path components
        if path is not None:
            for component in path:
                if not self.is_valid_path_component(component):
                    logging.warning(f"Invalid path component detected: {component}")
                    status = 400
                    content = {'error': 'Invalid path component'}
                    return json.dumps(content).encode('utf-8'), status, mime

        if path is None:                                        # Root API endpoint
            content = {
                'version': dash_config.version,
                'spacecraft': dash_config.spacecraft,
                'downlink': dash_config.downlink,
                'vcid_blacklist': dash_config.blacklist,
                'output_path': dash_config.output,
                'images': dash_config.images,
                'xrit': dash_config.xrit,
                'interval': int(dash_config.interval)
            }
        
        elif path[0] == "docs":                                 # API documentation endpoint
            content = {
                'endpoints': {
                    '/api': 'System configuration and status information',
                    '/api/docs': 'This API documentation',
                    '/api/current/vcid': 'Currently processing Virtual Channel ID',
                    '/api/current/progress': 'Current download progress for active products',
                    '/api/latest/image': 'Metadata for the most recent image of any type',
                    '/api/latest/{type}': 'Metadata for the most recent image of specific type',
                    '/api/latest/{type}/image': 'Actual image file for the most recent image of specific type',
                    '/api/latest/{type}/partial': 'Partial/preview image for actively downloading products',
                    '/api/latest/xrit': 'Metadata for the most recent xRIT file'
                },
                'image_types': {
                    'FD': {
                        'name': 'Full Disk',
                        'description': 'Full disk imagery covering the entire Earth hemisphere',
                        'typical_size': 'Large (multiple MB)',
                        'format': 'PNG/JPEG'
                    },
                    'SICEF24': {
                        'name': 'Sea Ice and Cloud Edge Forecast',
                        'description': 'Sea Ice and Cloud Edge Forecast (24-hour)',
                        'typical_size': 'Medium (1-2 MB)',
                        'format': 'PNG/JPEG'
                    },
                    'ADD': {
                        'name': 'Additional Data',
                        'description': 'Additional data products and supplementary imagery',
                        'typical_size': 'Variable',
                        'format': 'Various formats'
                    }
                },
                'response_formats': {
                    'metadata_endpoints': 'JSON with image path, hash, and type information',
                    'image_endpoints': 'Raw image data with appropriate MIME type',
                    'error_responses': 'JSON with error message when resource not found'
                },
                'example_usage': {
                    'get_latest_fd_metadata': '/api/latest/fd',
                    'get_latest_fd_image': '/api/latest/fd/image',
                    'get_system_info': '/api',
                    'get_current_vcid': '/api/current/vcid',
                    'list_timelapses': '/api/timelapses',
                    'get_timelapse_file': '/api/timelapses/{filename}'
                }
            }
        
        elif path[0] == "timelapse":                           # Timelapse endpoints
            if len(path) == 2 and path[1] == "list":
                # /api/timelapse/list - list available timelapses
                content = self.list_timelapses()
        
        elif path[0] == "timelapses":                          # Direct timelapse file serving from sibling directory
            # /api/timelapses/{filename} - serve timelapse files from timelapses/ directory
            if len(path) >= 2:
                filename = "/".join(path[1:])
                timelapses_dir = os.path.join(os.path.dirname(dash_config.output), "timelapses")
                # Normalize and resolve symlinks
                timelapses_dir_real = os.path.realpath(timelapses_dir)
                timelapse_path = os.path.normpath(os.path.join(timelapses_dir_real, filename))
                timelapse_path_real = os.path.realpath(timelapse_path)
                # Ensure the normalized path is within the timelapses_dir and is not absolute
                if (
                    os.path.isfile(timelapse_path_real)
                    and timelapse_path_real.startswith(timelapses_dir_real + os.sep)
                    and not os.path.isabs(filename)
                ):
                    mime = mimetypes.guess_type(timelapse_path_real)[0] or 'application/octet-stream'
                    content = open(timelapse_path_real, 'rb').read()
                else:
                    status = 404
                    content = {'error': 'Timelapse file not found'}
            else:
                # List available timelapses when no filename specified
                content = self.list_timelapses()
        
        elif "/".join(path).startswith(dash_config.output):     # Endpoint starts with demuxer output root path
            path = "/".join(path)
            if (os.path.isfile(path)):
                mime = mimetypes.guess_type(path)[0]
                content = open(path, 'rb').read()

        elif path[0] == "current" and len(path) == 2:
            if path[1] == "vcid":
                content = {
                    'vcid': demuxer_instance.currentVCID
                }
            elif path[1] == "progress":
                content = {
                    'active_downloads': demuxer_instance.currentProgress
                }
            elif path[1] == "partial":
                content = {
                    'partial_images': demuxer_instance.partialImages
                }

        elif path[0] == "latest":
            if len(path) == 2 and path[1] == "image":
                # /api/latest/image - latest image of any type (metadata)
                content = {
                    'image': demuxer_instance.lastImage,
                    'hash': demuxer_instance.lastImageHash,
                    'type': demuxer_instance.lastImageType
                }
            elif len(path) == 2 and path[1] == "xrit":
                # /api/latest/xrit - latest xRIT file
                content = {
                    'xrit': demuxer_instance.lastXRIT 
                }
            elif len(path) == 2:
                # /api/latest/{type} - latest image of specific type (metadata)
                image_type = path[1].upper()  # Convert to uppercase for consistency
                if image_type in demuxer_instance.lastImageByType:
                    type_data = demuxer_instance.lastImageByType[image_type]
                    content = {
                        'image': type_data['path'],
                        'hash': type_data['hash'],
                        'type': image_type
                    }
                else:
                    # No image of this type found
                    content = {
                        'image': None,
                        'hash': None,
                        'type': image_type,
                        'error': f'No {image_type} image available'
                    }
            elif len(path) == 3 and path[2] == "image":
                # /api/latest/{type}/image - serve actual image file
                image_type = path[1].upper()
                if image_type in demuxer_instance.lastImageByType:
                    image_path = demuxer_instance.lastImageByType[image_type]['path']
                    if image_path and os.path.isfile(image_path):
                        mime = mimetypes.guess_type(image_path)[0] or 'application/octet-stream'
                        content = open(image_path, 'rb').read()
                    else:
                        status = 404
                        content = {'error': f'Image file not found for type {image_type}'}
                else:
                    status = 404
                    content = {'error': f'No {image_type} image available'}
            elif len(path) == 3 and path[2] == "partial":
                # /api/latest/{type}/partial - serve partial/preview image file
                image_type = path[1].upper()
                if image_type in demuxer_instance.partialImages:
                    partial_path = demuxer_instance.partialImages[image_type]['path']
                    if partial_path and os.path.isfile(partial_path):
                        mime = mimetypes.guess_type(partial_path)[0] or 'application/octet-stream'
                        content = open(partial_path, 'rb').read()
                    else:
                        status = 404
                        content = {'error': f'Partial image file not found for type {image_type}'}
                else:
                    status = 404
                    content = {'error': f'No partial {image_type} image available'}
        
        # Send HTTP 200 OK if content has been updated
        if content != b'': status = 200

        # Convert Python dict into JSON string
        if type(content) is dict:
            content = json.dumps(content, sort_keys=False).encode('utf-8')

        # Return response bytes, HTTP status code and content MIME type
        return content, status, mime

    def list_timelapses(self):
        """
        List available timelapse files
        """
        timelapses_dir = os.path.join(os.path.dirname(dash_config.output), "timelapses")
        if not os.path.exists(timelapses_dir):
            return {'timelapses': []}
        
        timelapses = []
        for filename in os.listdir(timelapses_dir):
            if filename.endswith(('.mp4', '.gif')):
                filepath = os.path.join(timelapses_dir, filename)
                stat = os.stat(filepath)
                timelapses.append({
                    'filename': filename,
                    'size': stat.st_size,
                    'created': stat.st_mtime,
                    'url': f'/api/timelapses/{filename}'
                })
        
        return {'timelapses': sorted(timelapses, key=lambda x: x['created'], reverse=True)}

    def is_safe_path(self, path):
        """
        Check if path is safe (within output directory or timelapses directory)
        """
        try:
            # Check if path is within the output directory (received)
            output_abs = os.path.abspath(dash_config.output)
            path_abs = os.path.abspath(path)
            
            # Allow files within the output directory
            try:
                if os.path.commonpath([output_abs, path_abs]) == output_abs:
                    return True
            except ValueError:
                pass
            
            # Allow files within the timelapses directory (sibling to output)
            timelapses_abs = os.path.abspath(os.path.join(os.path.dirname(dash_config.output), "timelapses"))
            try:
                if os.path.commonpath([timelapses_abs, path_abs]) == timelapses_abs:
                    return True
            except ValueError:
                pass
            
            return False
        except ValueError:
            return False

    def sanitize_file_path(self, requested_path):
        """
        Sanitize and validate file path to prevent directory traversal
        """
        # Remove any path traversal attempts
        if '..' in requested_path or requested_path.startswith('/'):
            return None
        
        # Build safe path within html directory
        html_dir = os.path.abspath("html")
        full_path = os.path.join(html_dir, requested_path)
        
        # Ensure the resolved path is within html directory
        try:
            if os.path.commonpath([html_dir, os.path.abspath(full_path)]) != html_dir:
                return None
        except ValueError:
            return None
        
        return full_path

    def is_valid_path_component(self, component):
        """
        Validate individual path components for API security
        """
        # Check for common attack patterns
        if not component or component in ['.', '..']:
            return False
        
        # Check for null bytes and control characters
        if '\x00' in component or any(ord(c) < 32 for c in component if c != '\t'):
            return False
        
        # Check length (reasonable limit)
        if len(component) > 100:
            return False
        
        # Allow alphanumeric, dash, underscore, and dot
        import re
        if not re.match(r'^[a-zA-Z0-9._-]+$', component):
            return False
        
        return True

    def log_message(self, format, *args):
        """
        Silence HTTP server log messages
        """

        #super().log_message(format, *args)
        return
