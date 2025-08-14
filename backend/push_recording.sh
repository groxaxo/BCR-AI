#!/data/data/com.termux/files/usr/bin/bash

# A script to push call recordings from a specified directory on an Android device
# to a remote server using rsync. It's designed to be triggered automatically,
# for example, by Tasker, when a new recording is created.

# --- Configuration ---
# Source directory on the Android device where BCR saves the recordings.
# Update this path to match your BCR configuration.
SRC_DIR="/storage/emulated/0/CallRecordings/BCR/"

# Destination on the server.
# Replace 'op' with your username and '100.85.200.51' with your server's IP address.
# The destination directory should be the one watched by the process_calls.py script.
SERVER="op@100.85.200.51"
DEST_DIR="/path/to/server/incoming-calls/"

# --- rsync command ---
# -a: archive mode (preserves permissions, times, etc.)
# -v: verbose output
# -z: compress file data during the transfer
# --remove-source-files: delete files from the source directory after they are successfully transferred.
#                        Use with caution. Remove this option if you want to keep recordings on the phone.
rsync -avz --remove-source-files "$SRC_DIR" "$SERVER:$DEST_DIR"
