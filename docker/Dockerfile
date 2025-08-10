# Use a base image with the desired operating system (Debian)
FROM debian:latest

# Update the package list and install the required packages, including Python 3
RUN apt-get update && apt-get install -y ca-certificates python3 python3-pip libatlas-base-dev libopenjp2-7-dev libtiff-dev python3-venv
RUN apt-get install -y unzip wget
# Copy the locally downloaded xrit-rx.zip file into the image
RUN mkdir -p /xrit-rx
RUN mkdir -p /tmp
RUN wget https://github.com/Zalgar/xrit-rx-docker/releases/latest/download/xrit-rx.zip -P /tmp/

# Create a virtual environment and activate it
RUN python3 -m venv /venv
ENV PATH="/venv/bin:$PATH"

# Extract xrit-rx.zip
RUN unzip /tmp/xrit-rx.zip -d /xrit-rx

# Install pip requirements inside the virtual environment
RUN pip install -r /xrit-rx/requirements.txt

# Set the working directory to the xrit-rx directory
WORKDIR /xrit-rx

# Download Decryption key for gk2a and run decryption tool
RUN wget https://nmsc.kma.go.kr/resources/enhome/resources/satellites/coms/COMS_Decryption_Sample_Cpp.zip -P /tmp/
RUN unzip /tmp/COMS_Decryption_Sample_Cpp.zip -d /tmp/COMS_Decryption_Sample_Cpp
RUN cp /tmp/COMS_Decryption_Sample_Cpp/EncryptionKeyMessage_001F2904C905.bin /xrit-rx/
RUN python3 tools/keymsg-decrypt.py EncryptionKeyMessage_001F2904C905.bin 001F2904C905

# Create an entry script to check for the required files and start the application
COPY entry.sh /xrit-rx/entry.sh

# Set the entry script as executable
RUN chmod +x /xrit-rx/entry.sh

#Cleanup
RUN rm /tmp/xrit-rx.zip
RUN rm -r /tmp/COMS_Decryption_Sample_Cpp
RUN rm /tmp/COMS_Decryption_Sample_Cpp.zip
RUN rm /xrit-rx/EncryptionKeyMessage_001F2904C905.bin

# Specify the command to run when the container starts
CMD ["/xrit-rx/entry.sh"]

