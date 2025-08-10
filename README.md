# :satellite: xrit-rx - LRIT/HRIT Downlink Processor

[![GitHub release](https://img.shields.io/github/release/Zalgar/xrit-rx-docker.svg)](https://github.com/Zalgar/xrit-rx-docker/releases/latest)
[![Python versions](https://img.shields.io/badge/python-3.8%20%7C%203.9%20%7C%203.10%20%7C%203.11-blue)](https://www.python.org/)
[![Github all releases](https://img.shields.io/github/downloads/Zalgar/xrit-rx-docker/total.svg)](https://github.com/Zalgar/xrit-rx-docker/releases/latest)
[![GitHub license](https://img.shields.io/github/license/Zalgar/xrit-rx-docker.svg)](https://github.com/Zalgar/xrit-rx-docker/blob/master/LICENSE)

***
**⚠️ This software is now outdated. Receiving imagery from GK-2A via LRIT and HRIT is now possible with [SatDump](https://www.satdump.org/).**
***

***
**⚠️ This software is now outdated. Receiving imagery from GK-2A via LRIT and HRIT is now possible with [SatDump](https://www.satdump.org/).**
***

**xrit-rx** is a packet demultiplexer and file processor for receiving images from geostationary weather satellite [GEO-KOMPSAT-2A (GK-2A)](https://nmsc.kma.go.kr/enhome/html/base/cmm/selectPage.do?page=satellite.gk2a.intro). It is designed for use with [**goesrecv**](https://github.com/sam210723/goestools) (originally by [Pieter Noordhuis](https://twitter.com/pnoordhuis)), or [**xritdecoder**](https://github.com/opensatelliteproject/xritdemod/releases/tag/1.0.3) by [Lucas Teske](https://twitter.com/lucasteske).

**xrit-rx** receives [Virtual Channel Data Units (VCDUs)](https://nmsc.kma.go.kr/resources/homepage/pdf/GK2A_LRIT_Mission_Specification_Document_v1.0.pdf#page=27) over the network from either **goesrecv** or **xritdecoder** and demultiplexes them into separate virtual channels, each containing a different type of image data.
The demultiplexed packets are assembled into complete files which are output as images such as the ones below.

![GK-2A Wavelengths](https://vksdr.com/bl-content/uploads/pages/5fdcbf35a5231fc135c274ac17ca50c8/wavelengths.png)

## Getting Started
A guide for setting up the hardware and software components of a GK-2A LRIT receiver is [available on my site](https://vksdr.com/xrit-rx). It also covers the types of images that can be received, image post-processing techniques and data decryption.

<a href="https://vksdr.com/xrit-rx" target="_blank"><p align="center"><img src="https://vksdr.com/bl-content/uploads/pages/5fdcbf35a5231fc135c274ac17ca50c8/guide-thumb-light.png" title="Receiving Images from Geostationary Weather Satellite GEO-KOMPSAT-2A"></p></a>

The [RTL-SDR Blog](https://www.rtl-sdr.com) has also [written a guide](https://www.rtl-sdr.com/rtl-sdr-com-goes-16-17-and-gk-2a-weather-satellite-reception-comprehensive-tutorial/) for setting up the hardware and software required to receive imagery from GOES-16/17 and GK-2A. Once you are able to receive the GK-2A LRIT downlink with **goesrecv**, you can begin installing and configuring **xrit-rx**.

<<<<<<< HEAD
### Installing xrit-rx
Download the [latest version of **xrit-rx**](https://github.com/Zalgar/xrit-rx-docker/releases/latest) (``xrit-rx.zip``) from the Releases page, then unzip the contents to a new folder.

[`numpy`](https://pypi.org/project/numpy), [`pillow`](https://pypi.org/project/Pillow/), [`colorama`](https://pypi.org/project/colorama/) and [`pycryptodome`](https://pypi.org/project/pycryptodome/) are required to run **xrit-rx**. Use the following command to download and install these packages:
```
pip3 install -r requirements.txt
```

Images downlinked from GK-2A are encrypted by the [Korean Meteorological Administration](https://nmsc.kma.go.kr/enhome/html/main/main.do) (KMA). Decryption keys can be downloaded from KMA's website and used with **xrit-rx**.
More information is [available in the setup guide](https://vksdr.com/xrit-rx#keys).

=======
>>>>>>> 67c098783b37be94107cb4598c921c6a2415c1d4
### Configuring xrit-rx
All user-configurable options are found in the [`xrit-rx.ini`](src/xrit-rx.ini) file. The default configuration will work for most situations.

If **xrit-rx** is not running on the same device as **goesrecv** / **xritdecoder**, the `ip` option will need to be updated with the IP address of the device running **goesrecv** / **xritdecoder**.

## List of options

#### `rx` section
| Setting | Description | Options | Default |
| ------- | ----------- | ------- | ------- |
| `spacecraft` | Name of spacecraft being received | `GK-2A` | `GK-2A` |
| `mode` | Type of downlink being received | `lrit` or `hrit` | `lrit` |
| `input` | Input source | `goesrecv` or `osp` | `goesrecv` |
| `keys` | Path to decryption key file | *Absolute or relative file path* | `EncryptionKeyMessage.bin` |

#### `output` section

| Setting | Description | Options | Default |
| ------- | ----------- | ------- | ------- |
| `path` | Root output path for received files | *Absolute or relative file path* | `"received"` |
| `images` | Enable/Disable saving Image files to disk | `true` or `false` | `true` |
| `xrit` | Enable/Disable saving xRIT files to disk | `true` or `false` | `false` |
| `channel_blacklist` | List of virtual channels to ignore<br>Can be multiple channels (e.g. `4,5`) | `0: Full Disk`<br>`4: Alpha-numeric Text`<br>`5: Additional Data`<br> | *none* |

#### `goesrecv` section

| Setting | Description | Options | Default |
| ------- | ----------- | ------- | ------- |
| `ip` | IP Address of a device running **goesrecv** | *Any IPv4 address* | `127.0.0.1` |
| `vchan` | Output port of **goesrecv** | *Any TCP port number* | `5004` |

#### `osp` section

| Setting | Description | Options | Default |
| ------- | ----------- | ------- | ------- |
| `ip` | IP Address of a device running Open Satellite Project **xritdecoder** | *Any IPv4 address* | `127.0.0.1` |
| `vchan` | Output port of Open Satellite Project **xritdecoder** | *Any TCP port number* | `5001` |

#### `udp` section

| Setting | Description | Options | Default |
| ------- | ----------- | ------- | ------- |
| `ip` | IP Address to bind UDP socket to | *Any IPv4 address* | `127.0.0.1` |
| `vchan` | Port number to bind UDP socket to | *Any UDP port number* | `5002` |

#### `dashboard` section

| Setting | Description | Options | Default |
| ------- | ----------- | ------- | ------- |
| `enabled` | Enable/Disable dashboard server | `true` or `false` | `true` |
| `port` | Port number for server to listen on | *Any TCP port number* | `1692` |
| `interval` | Update interval in seconds | `integer` | `1` |


## Dashboard
**xrit-rx** includes a web-based dashboard for easy monitoring and viewing of received data.
The current GK-2A LRIT schedule is also displayed on the dashboard (retrieved from [KMA NMSC](https://nmsc.kma.go.kr/enhome/html/main/main.do)).

![Dashboard](https://vksdr.com/bl-content/uploads/pages/5fdcbf35a5231fc135c274ac17ca50c8/dashboard.png)

By default the dashboard is enabled and accessible on port <abbr title="Comes from the COMS-1/GK-2A LRIT frequency: 1692.14 MHz">1692</abbr> via HTTP (no HTTPS). These settings can be changed in the ``[dashboard]`` section of ``xrit-rx.ini``.

### Enhanced Dashboard Features
This version includes several enhancements to improve the real-time monitoring experience:

- **Real-time Download Progress**: Monitor the progress of multi-segment image downloads with live percentage updates and segment tracking
- **Partial Image Previews**: View images as they are being downloaded, with received segments displayed and missing segments shown as black areas
- **Timeout Handling**: Automatic completion of downloads that stall or miss segments, ensuring reliable operation
- **Improved API Documentation**: Comprehensive API documentation page with optimized loading performance
- **Enhanced Error Handling**: Robust connection error handling to prevent dashboard crashes during network issues

The dashboard automatically polls for progress updates and refreshes partial images in real-time, providing immediate feedback on satellite data reception status.


## HTTP API
**xrit-rx** has a comprehensive API accessible via HTTP primarily to support its web-based monitoring dashboard.
This may be useful for integrating **xrit-rx** with other applications.

The API only supports `GET` requests and will return either a `200 OK` or `404 Not Found` status.
The root endpoint is located at `/api` which returns information about the current xrit-rx configuration (example below).
```json
{
  "version": 2.0,
  "spacecraft": "GK-2A",
  "downlink": "LRIT",
  "vcid_blacklist": [
    4,
    5
  ],
  "output_path": "received/LRIT/",
  "images": true,
  "xrit": false,
  "interval": 1
}
```

The API also supports a special dynamic endpoint for retrieving image files over a network. This endpoint uses the start of the relative decoder output path found in the configuration object at the API root endpoint (``/api``).

For example, if ``output_path`` is ``"received/LRIT"`` the endpoint will be ``/api/received/LRIT``. From there the URL follows the folder structure created by xrit-rx for saving received images (e.g. ``/api/received/LRIT/20190722/FD/IMG_FD_047_IR105_20190722_075006.jpg``). The API does not currently support directory listing.

### Enhanced API Features
This version includes additional API endpoints for real-time monitoring:

- **Progress Tracking**: `/api/current/progress` provides real-time download progress for all active multi-segment products
- **Partial Images**: `/api/current/partial` lists available partial/preview images for active downloads
- **Live Image Previews**: `/api/latest/{type}/partial` serves partial images updated in real-time as segments arrive
- **Enhanced Latest Image Endpoints**: Expanded `/api/latest/{type}` endpoints with metadata, hash verification, and file serving capabilities
- **Improved Documentation**: `/api/docs` endpoint and dedicated API documentation page with comprehensive examples
- **Enhanced Error Handling**: Robust connection handling and graceful degradation for network issues

#### Latest Image API Enhancements
The latest image endpoints have been significantly enhanced beyond the original basic functionality:

**Original Functionality:**
- `/api/latest/image` - Returns path to most recent image of any type
- `/api/latest/xrit` - Returns path to most recent xRIT file

**New Enhanced Endpoints:**
- `/api/latest/{type}` - Returns comprehensive metadata for the most recent image of a specific type, including file path, hash, timestamp, and image properties
- `/api/latest/{type}/image` - Directly serves the actual completed image file with proper MIME type headers (image/jpeg, image/png, etc.)
- `/api/latest/{type}/partial` - **NEW**: Serves real-time partial/preview images for actively downloading products, showing received segments with black areas for missing data

**Key Improvements:**
- **Direct File Serving**: Image endpoints now serve raw binary data directly instead of just file paths, enabling immediate display in web applications
- **Real-time Partial Images**: Revolutionary new capability to view images as they download, updated automatically as new segments arrive
- **Enhanced Metadata**: Comprehensive information including file hashes for integrity verification, timestamps, and image properties
- **Type-specific Access**: Granular access to specific image types (FD, SICEF24, SSTF24, etc.) with case-insensitive matching
- **Proper MIME Types**: Correct Content-Type headers for seamless integration with web browsers and applications
- **Error Handling**: Graceful 404 responses when images are not available, with meaningful error messages

**Use Cases:**
- **Web Dashboards**: Direct image embedding without additional file serving infrastructure
- **Monitoring Applications**: Real-time progress visualization with partial image previews
- **Automated Systems**: Hash-based integrity checking and automated image processing
- **Mobile Applications**: Bandwidth-efficient partial image loading for slow connections

### List of Endpoints
| URL | Description | Example | MIME |
| --- | ----------- | ------- | ---- |
| `/api` | General configuration information | *see above* | `application/json` |
| `/api/docs` | Comprehensive API documentation | *JSON format documentation* | `application/json` |
| `/api/current/vcid` | Currently active virtual channel number | `{ "vcid": 63 }` | `application/json` |
| `/api/current/progress` | Real-time download progress for active products | `{ "FD": { "segments": 10, "total": 40, "progress": 25.0, "channel": 0 } }` | `application/json` |
| `/api/current/partial` | Available partial/preview images for active downloads | `{ "available": ["FD", "SICEF24"], "count": 2 }` | `application/json` |
| `/api/latest/image` | Path to most recently received product (any type) | `{ "image": "received/LRIT/[...].jpg", "type": "FD" }` | `application/json` |
| `/api/latest/{type}` | **Enhanced**: Comprehensive metadata for most recent image of specific type | `{ "image": "received/LRIT/[...].jpg", "hash": "abc123...", "timestamp": "2025-08-10T12:00:00Z", "size": 1024000, "channel": 0 }` | `application/json` |
| `/api/latest/{type}/image` | **Enhanced**: Direct serving of completed image file with proper headers | *Raw JPEG/PNG binary data* | `image/jpeg`, `image/png` |
| `/api/latest/{type}/partial` | **NEW**: Real-time partial/preview image for actively downloading products | *Raw image data with black areas for missing segments, updates as segments arrive* | `image/jpeg`, `image/png` |
| `/api/latest/xrit` | Path to most recently received xRIT file | `{ "xrit": "received/LRIT/[...].lrit", "timestamp": "2025-08-10T12:00:00Z" }` | `application/json` |

#### API Usage Examples

**Basic Image Retrieval:**
```bash
# Get metadata for latest Full Disk image
curl http://localhost:1692/api/latest/fd

# Download the latest Full Disk image directly
curl http://localhost:1692/api/latest/fd/image -o latest_fd.jpg

# Get partial/preview image of currently downloading Full Disk
curl http://localhost:1692/api/latest/fd/partial -o partial_fd.jpg
```

**Progress Monitoring:**
```bash
# Monitor download progress
curl http://localhost:1692/api/current/progress

# Check which products have partial images available
curl http://localhost:1692/api/current/partial
```

**Integration Examples:**
```html
<!-- Direct image embedding in web applications -->
<img src="http://localhost:1692/api/latest/fd/image" alt="Latest Full Disk Image">

<!-- Real-time partial image preview -->
<img src="http://localhost:1692/api/latest/fd/partial" alt="Downloading..." id="partial-preview">
<script>
    // Refresh partial image every 5 seconds
    setInterval(() => {
        document.getElementById('partial-preview').src = 
            'http://localhost:1692/api/latest/fd/partial?' + Date.now();
    }, 5000);
</script>
```

#### Technical Implementation Details

**Partial Image Generation:**
- Partial images are generated using PIL/Pillow with black backgrounds for missing segments
- Images are only regenerated when new segments arrive, optimizing performance
- Automatic cleanup prevents memory leaks during long download sessions
- Progressive JPEG encoding for faster partial image loading

**Progress Tracking System:**
- Real-time segment counting with configurable timeout handling (default 300 seconds)
- Automatic completion when 70% of segments received and timeout occurs
- Per-channel progress tracking for simultaneous multi-product downloads
- Timestamp tracking for last received segment to detect stalled downloads

**Performance Optimizations:**
- Asynchronous file serving to prevent blocking on large image requests
- Content-Type header detection based on file extensions
- Efficient memory management for simultaneous partial image generation
- Cached metadata to reduce disk I/O for frequently requested endpoints

**Error Handling:**
- Graceful degradation when images are not available (404 responses)
- Connection timeout handling for network issues
- BrokenPipeError handling for client disconnections
- Comprehensive logging for debugging and monitoring

**CORS and Security:**
- Cross-Origin Resource Sharing (CORS) headers for web application integration
- No authentication required for monitoring/read-only endpoints
- Rate limiting not implemented (designed for local/trusted network use)
- File path validation to prevent directory traversal attacks

**Supported Image Types**: FD, SICEF24, SICEF48, SSTF24, SSTF48, SSTF72, FOGVIS, COMSFOG, FCT, GWW3F, RWW3A, SUFA03, ANT, ADD (case-insensitive)


## Enhanced Features
This version (2.0.0) builds upon the excellent foundation created by [sam210723](https://github.com/sam210723) with the following improvements:

### Real-time Monitoring Enhancements
- **Download Progress Tracking**: Monitor multi-segment image downloads with real-time progress indicators showing received vs. expected segments
- **Partial Image Previews**: View images as they download with live updates, displaying received segments and black areas for missing data
- **Automatic Timeout Handling**: Robust completion logic for stalled downloads, ensuring reliable operation even with missed segments
- **Enhanced Dashboard UI**: Improved web interface with progress bars, real-time updates, and better error handling

### API and Documentation Improvements  
- **Expanded API Endpoints**: New endpoints for progress tracking, partial images, and enhanced metadata
- **Comprehensive Documentation**: Detailed API documentation with examples and integration guidance
- **Performance Optimizations**: Faster-loading documentation page with asynchronous font loading and reduced content size
- **CORS Support**: Cross-origin resource sharing for external application integration

### Technical Enhancements
- **Robust Error Handling**: Improved connection handling with graceful degradation for network issues
- **Memory Management**: Optimized partial image generation and cleanup
- **Real-time Updates**: Efficient polling mechanisms for dashboard and API consumers

All enhancements maintain compatibility with the original **xrit-rx** configuration and workflow while adding powerful new monitoring capabilities for satellite data reception.


## Acknowledgments
  - [Lucas Teske](https://twitter.com/lucasteske) - Developer of [**Open Satellite Project**](https://github.com/opensatelliteproject) and writer of ["GOES Satellite Hunt"](https://www.teske.net.br/lucas/2016/10/goes-satellite-hunt-part-1-antenna-system/)
  - [Pieter Noordhuis](https://twitter.com/pnoordhuis) - Developer of [**goestools**](https://github.com/pietern/goestools)
  - [John Bell](https://twitter.com/eswnl) - Software testing and IQ recordings
  - ["kisaa"](https://github.com/kisaa) - GK-2A HRIT debugging and packet recordings
  - [@Rasiel_J](https://twitter.com/Rasiel_J) - IQ recordings


## libjpeg
**xrit-rx** uses [**libjpeg**](https://github.com/thorfdbg/libjpeg) for converting JPEG2000 (J2K/JP2) images to Portable Pixmap Format (PPM) images.
A compiled 32-bit binary for Windows is included in **xrit-rx** releases along with the **libjpeg** [LICENSE](https://github.com/Zalgar/xrit-rx-docker/blob/master/src/tools/libjpeg/LICENSE) (GPLv3) and [README](https://github.com/Zalgar/xrit-rx-docker/blob/master/src/tools/libjpeg/README).

The source code for **libjpeg** can be found at https://github.com/thorfdbg/libjpeg.
