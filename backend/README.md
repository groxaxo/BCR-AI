# Automated Call Transcription and Processing Pipeline

This document describes a fully automated pipeline to take call recordings from an Android device, transcribe them, summarize them, and store the results in a structured format.

This pipeline is flexible, allowing you to use either self-hosted models for maximum privacy and control, or the official OpenAI APIs for ease of use and powerful models.

## Overview

The pipeline consists of two main parts: a client-side component on the Android phone and a server-side component for processing.

**Workflow:**
1.  **Record**: The [BCR app](https://github.com/chenxiaolong/BCR) records a phone call on a rooted Android device.
2.  **Transfer**: Tasker detects the new recording and triggers a Termux script (`push_recording.sh`) to transfer the audio file to a server via `rsync`.
3.  **Process**: A Python watcher script (`process_calls.py`) on the server detects the new file.
4.  **Preprocess**: The script converts the audio to `16kHz mono WAV` using `ffmpeg`.
5.  **Transcribe**: The script sends the audio to the selected transcription service (self-hosted Whisper or OpenAI API).
6.  **Summarize**: The resulting transcript is sent to the selected summarization service (self-hosted LLM or OpenAI API).
7.  **Store**: The transcript, summary, and metadata are saved as a structured `.json` file.

## Components

*   `install.sh`: An installer script to automate the server-side setup.
*   `requirements.txt`: A list of Python dependencies for the project.
*   `process_calls.py`: The main Python script for the server that watches for and processes new recordings.
*   `push_recording.sh`: A shell script for the Android phone to `rsync` recordings to the server.
*   `call_pipeline.service`: A `systemd` unit file to run the Python script as a persistent service on the server.

## Prerequisites

### Server-Side
*   A Linux server (e.g., Ubuntu 22.04).
*   `python3`, `pip`, and `python3-venv`.
*   `ffmpeg`: Can be installed with `sudo apt update && sudo apt install ffmpeg`.
*   (Optional) Docker and NVIDIA Container Toolkit for GPU-accelerated self-hosted models.

### Phone-Side
*   A rooted Android device.
*   [BCR (Basic Call Recorder)](https://github.com/chenxiaolong/BCR) installed and configured.
*   [Termux](https://f-droid.org/en/packages/com.termux/): A terminal emulator for Android.
*   [Tasker](https://play.google.com/store/apps/details?id=net.dinglisch.android.taskerm): An automation app for Android.
*   `rsync` and `openssh` installed in Termux: `pkg install rsync openssh`.

## Server Setup

### 1. Easy Install
For a fresh setup, you can use the provided installer script. It will guide you through the setup process, including dependency checks, virtual environment creation, and package installation.

```bash
# Navigate to the backend directory
cd backend

# Make the installer executable
chmod +x install.sh

# Run the installer
./install.sh
```
The script will finish by printing the manual steps required for configuration and service installation. **Follow those instructions carefully.**

### 2. Manual Installation
If you prefer to set up the environment manually:
```bash
# 1. Navigate to the backend directory
cd backend

# 2. Create and activate a Python virtual environment
python3 -m venv venv
source venv/bin/activate

# 3. Install required packages
pip install -r requirements.txt
```

### 3. Configuration
Open `backend/process_calls.py` in a text editor to configure the pipeline.

**a. Directory Paths (Required)**
You must update these paths to absolute paths on your server.
```python
WATCH_DIR = "/path/to/server/incoming-calls"
OUTPUT_DIR = "/path/to/server/processed"
ERROR_DIR = "/path/to/server/errors"
```

**b. Provider Selection**
Choose between `'self-hosted'` or `'openai'` for transcription and summarization.
```python
TRANSCRIPTION_PROVIDER = "self-hosted"
SUMMARIZATION_PROVIDER = "self-hosted"
```

**c. API Settings**
*   **If using 'openai'**:
    *   Set your `OPENAI_API_KEY`.
    *   You can change the `OPENAI_WHISPER_MODEL` and `OPENAI_LLM_MODEL` if desired.
*   **If using 'self-hosted'**:
    *   Ensure the `SELF_HOSTED_WHISPER_API_BASE` and `SELF_HOSTED_LLM_API_BASE` URLs are correct.
    *   To set up a self-hosted Whisper API with Docker, you can use this command:
        ```bash
        docker run --gpus all -d \
          -p 9000:9000 --name whisper-large-v3 \
          ghcr.io/schibsted/openai-compatible-whisper:main \
          --model large-v3 --device cuda
        ```
    *   For a self-hosted LLM, follow the documentation for your chosen platform (e.g., vLLM, Ollama) to set up an OpenAI-compatible API endpoint.

### 4. Install and Run the Service
The final step is to install and run the `systemd` service to make the pipeline run persistently. The `install.sh` script provides the exact commands for this, but they are also listed here for reference.

1.  **Edit the `.service` file**: Open `call_pipeline.service` and replace `/path/to/backend` with the absolute path to this directory. Also, ensure the `User` is correct.

2.  **Install and enable the service**:
    ```bash
    sudo cp call_pipeline.service /etc/systemd/system/call_pipeline.service
    sudo systemctl daemon-reload
    sudo systemctl enable call_pipeline.service
    sudo systemctl start call_pipeline.service
    ```

3.  **Check the service status**:
    ```bash
    sudo systemctl status call_pipeline.service
    # To view live logs
    sudo journalctl -u call_pipeline.service -f
    ```

## Phone Setup
The phone setup is a manual process.

### 1. SSH Key Authentication
For passwordless `rsync`, set up SSH key authentication from your phone to the server.
1.  **On your phone (in Termux)**: `ssh-keygen -t rsa -b 4096`
2.  **Copy the public key to the server**: `ssh-copy-id user@your_server_ip`

### 2. Configure the rsync Script
1.  Copy `push_recording.sh` to your phone (e.g., into Termux's home directory).
2.  Edit the script to set the correct `SERVER` and `DEST_DIR` variables. `DEST_DIR` must match `WATCH_DIR` on the server.
3.  Make the script executable: `chmod +x push_recording.sh`.

### 3. Automate with Tasker
Create a Tasker profile that triggers when a new file is created in your BCR recordings directory. The task should use the **Termux** plugin to run your `push_recording.sh` script.
*   **Profile**: Event -> File -> File Modified. Set the path to your BCR folder.
*   **Task**: Plugin -> Termux. Configure it to run the `push_recording.sh` executable.

## Usage
Once both the server and phone are set up, the entire process is hands-off. Recordings are automatically transferred, processed, and saved as detailed JSON files in your output directory.
