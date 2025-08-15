#!/bin/bash

# A script to automate the setup of the server-side components for the
# Automated Call Transcription and Processing Pipeline.

set -e # Exit immediately if a command exits with a non-zero status.

echo "--- Starting Backend Setup ---"

# --- 1. Check for Dependencies ---
echo "[1/5] Checking for required commands (python3, pip, venv)..."
for cmd in python3 pip; do
    if ! command -v $cmd &> /dev/null; then
        echo "Error: $cmd is not installed. Please install it and run this script again."
        exit 1
    fi
done
if ! python3 -m venv -h &> /dev/null; then
    echo "Error: python3-venv is not installed. Please install it (e.g., 'sudo apt install python3-venv') and run this script again."
    exit 1
fi
echo "Dependencies found."

# --- 2. Create Python Virtual Environment ---
echo "[2/5] Creating Python virtual environment in './venv'..."
python3 -m venv venv
echo "Virtual environment created."

# --- 3. Install Python Packages ---
echo "[3/5] Installing Python dependencies from requirements.txt..."
source venv/bin/activate
pip install -r requirements.txt
deactivate
echo "Dependencies installed."

# --- 4. Create Directories ---
echo "[4/5] Creating required directories..."
# Read the directory paths directly from the Python script to avoid duplication.
WATCH_DIR=$(grep -oP 'WATCH_DIR = "\K[^"]+' process_calls.py)
OUTPUT_DIR=$(grep -oP 'OUTPUT_DIR = "\K[^"]+' process_calls.py)
ERROR_DIR=$(grep -oP 'ERROR_DIR = "\K[^"]+' process_calls.py)

# Check if the user has updated the default paths
if [[ "$WATCH_DIR" == "/path/to/"* ]]; then
    echo "Warning: Default directory paths are still configured in process_calls.py."
    echo "Please edit process_calls.py to set your desired directory paths before running the service."
else
    for dir in "$WATCH_DIR" "$OUTPUT_DIR" "$ERROR_DIR"; do
        mkdir -p "$dir"
        echo "Created directory: $dir"
    done
    echo "Directories created successfully."
fi

# --- 5. Final Instructions ---
echo "[5/5] Setup is almost complete. Please follow these final manual steps:"
echo ""
echo "--------------------------------------------------------------------------"
echo "MANUAL STEPS REQUIRED:"
echo ""
echo "1. Configure the Pipeline:"
echo "   - Open 'backend/process_calls.py' in a text editor."
echo "   - **Crucially, update the directory paths** (WATCH_DIR, OUTPUT_DIR, ERROR_DIR) if you haven't already."
echo "   - Choose your providers ('self-hosted' or 'openai')."
echo "   - If using OpenAI, enter your API key for 'OPENAI_API_KEY'."
echo "   - If using self-hosted models, ensure the API base URLs are correct."
echo ""
echo "2. Configure and Install the Service:"
echo "   - Open 'backend/call_pipeline.service'."
echo "   - Replace '/path/to/backend' with the absolute path to this directory: $(pwd)"
echo "   - Set the 'User' to the user you want to run the service as (e.g., $(whoami))."
echo ""
echo "   - Then, run the following commands to install and start the service:"
echo "     sudo cp call_pipeline.service /etc/systemd/system/call_pipeline.service"
echo "     sudo systemctl daemon-reload"
echo "     sudo systemctl enable call_pipeline.service"
echo "     sudo systemctl start call_pipeline.service"
echo ""
echo "3. Check the service status with:"
echo "   sudo systemctl status call_pipeline.service"
echo "   sudo journalctl -u call_pipeline.service -f"
echo "--------------------------------------------------------------------------"
echo ""
echo "--- Backend Setup Finished ---"
