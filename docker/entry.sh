#!/bin/sh

# Check for the presence of required files
cd /xrit-rx
if [ -f /xrit-rx/xrit-rx.ini ] && [ -f /xrit-rx/EncryptionKeyMessage.bin ]; then
    echo "Required files found. Starting the application..."
    
    # Start xrit-rx (which will also start the timelapse service)
    python3 xrit-rx.py
else
    echo "Required files not found. Please ensure xrit-rx.ini and EncryptionKeyMessage.bin are present."
fi

