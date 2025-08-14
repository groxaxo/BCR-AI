# Automated Call Transcription and Processing Pipeline

This document describes a fully automated pipeline to take call recordings from an Android device, transcribe them using Whisper, summarize them with an LLM, and store the results in a structured format.

## Overview

The pipeline consists of two main parts: a client-side component on the Android phone and a server-side component for processing.

**Workflow:**
1.  **Record**: The [BCR app](https://github.com/chenxiaolong/BCR) records a phone call on a rooted Android device.
2.  **Transfer**: Tasker detects the new recording and triggers a Termux script (`push_recording.sh`) to transfer the audio file to a server via `rsync`.
3.  **Process**: A Python watcher script (`process_calls.py`) on the server detects the new file.
4.  **Preprocess**: The script converts the audio to `16kHz mono WAV` using `ffmpeg`, the optimal format for Whisper.
5.  **Transcribe**: The script sends the audio to a self-hosted Whisper Large V3 API for transcription.
6.  **Summarize**: The resulting transcript is sent to a self-hosted vLLM API for summarization and analysis.
7.  **Store**: The transcript, summary, and metadata are saved as a structured `.json` file.

**Architecture Diagram:**
```
[Android Phone]                                  [Backend Server]
+------------------------------------+           +---------------------------------------------+
| [BCR App] ── new recording ──▶     |           |                                             |
|                                    |           |  /incoming-calls/                           |
| [Tasker] -- triggers --> [Termux]  | --rsync-->|     +--------------------------+            |
|     (runs push_recording.sh)       |           |     | process_calls.py         |            |
+------------------------------------+           |     | (watcher service)        |            |
                                                 |     +-------------+------------+            |
                                                 |                   |                         |
                                                 | (new file)        | 1. Preprocess (ffmpeg)  |
                                                 |                   | 2. Transcribe (Whisper) |
                                                 |                   | 3. Summarize (vLLM)     |
                                                 |                   | 4. Save JSON            |
                                                 |                   ▼                         |
                                                 |  /processed-calls/ (JSON outputs)           |
                                                 |  /errors/ (Failed files)                    |
                                                 +---------------------------------------------+
```

## Components

*   `push_recording.sh`: A shell script for the Android phone to `rsync` recordings to the server.
*   `process_calls.py`: The main Python script for the server that watches for and processes new recordings.
*   `call_pipeline.service`: A `systemd` unit file to run the Python script as a persistent service on the server.

## Prerequisites

### Server-Side
*   A Linux server (e.g., Ubuntu 22.04).
*   Python 3.8+ and `pip`.
*   `ffmpeg`: `sudo apt update && sudo apt install ffmpeg`
*   Docker and NVIDIA Container Toolkit (for GPU-accelerated Whisper).

### Phone-Side
*   A rooted Android device.
*   [BCR (Basic Call Recorder)](https://github.com/chenxiaolong/BCR) installed and configured.
*   [Termux](https://f-droid.org/en/packages/com.termux/): A terminal emulator for Android.
*   [Tasker](https://play.google.com/store/apps/details?id=net.dinglisch.android.taskerm): An automation app for Android.
*   `rsync` and `openssh` installed in Termux: `pkg install rsync openssh`

## Server Setup

### 1. Install Python Dependencies
It is recommended to use a Python virtual environment.
```bash
# Navigate to the backend directory
cd backend

# Create and activate a virtual environment
python3 -m venv venv
source venv/bin/activate

# Install required packages
pip install openai "watchdog[watchmedo]"
```

### 2. Set Up Whisper Large V3 API
You can run a Whisper API server using Docker. For GPU acceleration, ensure you have the NVIDIA drivers and NVIDIA Container Toolkit installed. The following command runs a community-built, OpenAI-compatible Whisper API server.

```bash
# Run this command on your server with a GPU
docker run --gpus all -d \
  -p 9000:9000 --name whisper-large-v3 \
  -e "WHISPER_MODEL=large-v3" \
  -e "WHISPER_THREADS=4" \
  -e "WHISPER_DEVICE=cuda" \
  ghcr.io/schibsted/openai-compatible-whisper:main
```
This will start a Whisper API server on port `9000`, which is what `process_calls.py` is configured to use by default.

### 3. Set Up vLLM API
Follow the official [vLLM documentation](https://vllm.ai/) to deploy your desired summarization model as an OpenAI-compatible API server. Update the `VLLM_API_BASE` and `VLLM_MODEL` variables in `process_calls.py` accordingly.

### 4. Configure the Processing Script
Open `process_calls.py` and modify the configuration variables at the top of the file:
*   `WATCH_DIR`: The absolute path to the directory where recordings will be received.
*   `OUTPUT_DIR`: The absolute path to the directory where processed `.json` files will be saved.
*   `ERROR_DIR`: The absolute path to the directory where failed files will be moved.
*   `VLLM_API_BASE`, `VLLM_API_KEY`, `VLLM_MODEL`: Your vLLM service details.

### 5. Set Up the systemd Service
To ensure the script runs continuously, set it up as a `systemd` service.

1.  **Edit the `.service` file**: Open `call_pipeline.service` and replace `/path/to/backend/` with the actual absolute path to this directory. Also, ensure the `User` is correct.

2.  **Install and enable the service**:
    ```bash
    # Copy the service file to the systemd directory
    sudo cp call_pipeline.service /etc/systemd/system/call_pipeline.service

    # Reload the systemd daemon to recognize the new service
    sudo systemctl daemon-reload

    # Enable the service to start on boot
    sudo systemctl enable call_pipeline.service

    # Start the service immediately
    sudo systemctl start call_pipeline.service
    ```

3.  **Check the service status**:
    ```bash
    sudo systemctl status call_pipeline.service

    # To view logs
    sudo journalctl -u call_pipeline.service -f
    ```

## Phone Setup

### 1. SSH Key Authentication
For passwordless `rsync`, set up SSH key authentication from your phone to the server.

1.  **On your phone (in Termux)**:
    ```bash
    # Install openssh if you haven't already
    pkg install openssh

    # Generate an SSH key pair
    ssh-keygen -t rsa -b 4096
    ```
    Press Enter to accept the default file location and leave the passphrase empty.

2.  **Copy the public key to the server**:
    ```bash
    # This command will copy your public key to the server's authorized_keys file
    ssh-copy-id user@your_server_ip
    ```
    Replace `user` and `your_server_ip` with your server's username and IP address. You will be prompted for your server password one last time.

### 2. Configure the rsync Script
1.  Copy the `push_recording.sh` script to your phone (e.g., to `/data/data/com.termux/files/home/`).
2.  Open the script and edit the `SERVER` and `DEST_DIR` variables to match your server's details. The `DEST_DIR` must match the `WATCH_DIR` on the server.
3.  Make the script executable in Termux: `chmod +x push_recording.sh`.

### 3. Automate with Tasker
Create a Tasker profile to run the `push_recording.sh` script whenever a new call recording is created by BCR.

1.  **Create a new Profile**:
    *   Go to Profiles tab and click `+`.
    *   Select **Event** -> **File** -> **File Modified**.
    *   In the **File** field, enter the path to your BCR recordings directory (e.g., `/sdcard/CallRecordings/BCR/`).
2.  **Create a new Task**:
    *   Tasker will prompt you to link a task. Create a new one.
    *   Click `+` to add an action.
    *   Select **Plugin** -> **Termux**.
    *   Tap the pencil icon to configure.
    *   **Executable**: `~/push_recording.sh` (or the path to your script).
    *   **Arguments**: (leave blank).
    *   Leave the other settings as default.

Now, whenever a file is added or modified in the BCR directory, Tasker will automatically execute the `rsync` script, sending the file to your server for processing.

## Usage
Once both the server and phone are set up, the entire process is hands-off.
1.  A call is made or received.
2.  BCR saves the recording.
3.  Tasker triggers the transfer to the server.
4.  The server-side script processes the file and saves a `.json` file to the `OUTPUT_DIR`.
5.  The original audio file on the server is deleted after successful processing. If an error occurs, it is moved to the `ERROR_DIR`. The original file on the phone is deleted by `rsync`.
