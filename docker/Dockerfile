# Multi-stage build for smaller final image
FROM node:22-slim AS builder

# Install only what we need for building
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    unzip \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Sass
RUN npm install -g sass

# Copy source files instead of downloading release
COPY src /build
COPY requirements.txt /build/requirements.txt

# Ensure CSS is compiled
WORKDIR /build
RUN if [ -f html/css/dash.scss ]; then sass --no-source-map html/css/dash.scss html/css/dash.css; fi

# Download and process decryption keys
RUN mkdir -p /tmp && \
    wget --no-check-certificate https://nmsc.kma.go.kr/resources/enhome/resources/satellites/coms/COMS_Decryption_Sample_Cpp.zip -P /tmp/ && \
    unzip /tmp/COMS_Decryption_Sample_Cpp.zip -d /tmp/COMS_Decryption_Sample_Cpp && \
    cp /tmp/COMS_Decryption_Sample_Cpp/EncryptionKeyMessage_001F2904C905.bin /build/ && \
    rm -rf /tmp/COMS_Decryption_Sample_Cpp*

# Final runtime image
FROM python:3.12-alpine

# Install only runtime dependencies (Alpine packages)
RUN apk add --no-cache \
    lapack-dev \
    openjpeg-dev \
    tiff-dev \
    gcc \
    musl-dev \
    g++ \
    && apk del gcc musl-dev g++

# Copy built application from builder stage
COPY --from=builder /build /xrit-rx

# Set working directory
WORKDIR /xrit-rx

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Process decryption key
RUN python3 tools/keymsg-decrypt.py EncryptionKeyMessage_001F2904C905.bin 001F2904C905 && \
    rm EncryptionKeyMessage_001F2904C905.bin

# Copy entry script
COPY docker/entry.sh /xrit-rx/entry.sh
RUN apk add --no-cache dos2unix \
    && dos2unix /xrit-rx/entry.sh \
    && chmod +x /xrit-rx/entry.sh

# Create non-root user for security
RUN adduser -D -u 1000 xrituser && \
    chown -R xrituser:xrituser /xrit-rx
USER xrituser

# Expose port
EXPOSE 1692

# Start application
CMD ["/xrit-rx/entry.sh"]

