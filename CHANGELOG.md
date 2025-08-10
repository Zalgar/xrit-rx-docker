# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.0.0] - 2025-08-10

### Added
- **Real-time Download Progress Tracking**: Monitor multi-segment image downloads with live progress indicators showing received vs. expected segments
- **Partial Image Previews**: View images as they download with real-time updates, displaying received segments with black areas for missing data  
- **Enhanced API Endpoints**: New endpoints for progress tracking (`/api/current/progress`), partial images (`/api/current/partial`), and live previews (`/api/latest/{type}/partial`)
- **Timeout Handling**: Automatic completion logic for stalled downloads, ensuring reliable operation even with missed segments
- **Enhanced Dashboard UI**: Improved web interface with progress bars, real-time updates, and better error handling
- **Comprehensive API Documentation**: Detailed documentation page with examples and integration guidance (`/api/docs`)
- **Direct Image Serving**: API endpoints now serve raw binary data directly with proper MIME type headers
- **Enhanced Metadata**: Comprehensive information including file hashes for integrity verification, timestamps, and image properties
- **CORS Support**: Cross-origin resource sharing for external application integration

### Enhanced
- **API Response Format**: Enhanced `/api/latest/{type}` endpoints with comprehensive metadata including hashes and timestamps
- **Error Handling**: Robust connection handling with graceful degradation for network issues (BrokenPipeError, timeouts)
- **Performance Optimizations**: Asynchronous font loading, optimized partial image generation, efficient memory management
- **Documentation**: Significantly expanded README.md with detailed API documentation, usage examples, and technical implementation details

### Technical Improvements
- **Memory Management**: Optimized partial image generation and automatic cleanup to prevent memory leaks
- **Progress Tracking System**: Real-time segment counting with configurable timeout handling (default 300 seconds)
- **Automatic Completion**: Downloads auto-complete when 70% of segments received and timeout occurs
- **Per-channel Tracking**: Support for simultaneous multi-product download monitoring
- **File Serving**: Content-Type header detection and efficient serving for image endpoints

### Breaking Changes
- **Version Number**: Updated from 1.3.1 to 2.0.0 to reflect significant feature additions
- **API Version**: Updated API version response from 1.1 to 2.0

---

## [1.3.1] - Previous Release
- Original xrit-rx functionality by [sam210723](https://github.com/sam210723)
- Basic LRIT/HRIT downlink processing
- Web dashboard for monitoring
- Basic API endpoints for image access
- Virtual channel demultiplexing
- Image decryption and processing
