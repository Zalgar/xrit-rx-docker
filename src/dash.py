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
                    'get_current_vcid': '/api/current/vcid'
                }
            }
        
        elif path[0] == "timelapse":                           # Timelapse creation endpoints
            if len(path) == 2 and path[1] == "create":
                # /api/timelapse/create?hours=24&type=FD&format=mp4
                query_params = self.parse_query_params()
                
                hours = int(query_params.get('hours', ['24'])[0])
                image_type = query_params.get('type', ['FD'])[0].upper()
                format_type = query_params.get('format', ['mp4'])[0].lower()
                
                if format_type not in ['mp4', 'gif']:
                    status = 400
                    content = {'error': 'Format must be mp4 or gif'}
                elif hours not in [3, 24]:
                    status = 400
                    content = {'error': 'Hours must be 3 or 24'}
                else:
                    # Create timelapse asynchronously
                    success = self.create_timelapse_async(hours, image_type, format_type)
                    if success:
                        content = {
                            'status': 'started',
                            'message': f'Timelapse creation started for {hours}h of {image_type} images in {format_type} format',
                            'estimated_time': '30-60 seconds'
                        }
                    else:
                        status = 500
                        content = {'error': 'Failed to start timelapse creation'}
            
            elif len(path) == 2 and path[1] == "list":
                # /api/timelapse/list - list available timelapses
                content = self.list_timelapses()
            
            elif len(path) >= 2 and path[1] == "download":
                # /api/timelapse/download/{filename} - download timelapse file
                if len(path) >= 3:
                    filename = "/".join(path[2:])
                    timelapse_path = os.path.join(dash_config.output, "timelapses", filename)
                    
                    if os.path.isfile(timelapse_path) and self.is_safe_path(timelapse_path):
                        mime = mimetypes.guess_type(timelapse_path)[0] or 'application/octet-stream'
                        content = open(timelapse_path, 'rb').read()
                    else:
                        status = 404
                        content = {'error': 'Timelapse file not found'}
                else:
                    status = 400
                    content = {'error': 'Filename required'}
        
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


    def log_message(self, format, *args):
        """
        Silence HTTP server log messages
        """

        #super().log_message(format, *args)
        return
