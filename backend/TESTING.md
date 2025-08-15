# Manual Testing Guide

This document provides steps to manually test the proposal and approval workflow of the `process_calls.py` script.

This test does **not** require valid audio files or running Whisper/vLLM services. It verifies that the core logic of file monitoring, proposing, approving, and error handling is working correctly.

## 1. Configure the Script

1.  Open `backend/process_calls.py`.
2.  **Crucially**, update the directory path variables in the "Configuration" section. The script will create these directories if they don't exist, so you can point them to a temporary location for testing. For example:
    ```python
    INCOMING_DIR = "/tmp/bcr-pipeline/incoming"
    PROPOSED_DIR = "/tmp/bcr-pipeline/proposed"
    APPROVED_DIR = "/tmp/bcr-pipeline/approved"
    OUTPUT_DIR   = "/tmp/bcr-pipeline/processed"
    ERROR_DIR    = "/tmp/bcr-pipeline/errors"
    ```
3.  You do not need to change the API endpoint configurations for this test.

## 2. Run the Script

1.  Open a terminal and navigate to the `backend` directory.
2.  If you use a virtual environment, activate it (`source venv/bin/activate`).
3.  Run the script:
    ```bash
    python process_calls.py
    ```
4.  You should see log messages indicating that the script is watching the `incoming` and `approved` directories. Keep this terminal open and visible.

## 3. Test the Workflow

You will need a second terminal to create and move files.

1.  **Propose a new file:**
    *   In your second terminal, create a dummy file in the `INCOMING_DIR`:
        ```bash
        touch /tmp/bcr-pipeline/incoming/test_call_01.oga
        ```
    *   **Observe the script's terminal.** Within a few seconds, you should see logs like:
        ```
        PROPOSAL: New file 'test_call_01.oga' moved to '/tmp/bcr-pipeline/proposed' for approval.
        To approve, move it to: '/tmp/bcr-pipeline/approved'
        ```
    *   **Verify:** Check that `test_call_01.oga` is now in the `/tmp/bcr-pipeline/proposed` directory and no longer in `incoming`.

2.  **Approve the file:**
    *   In your second terminal, move the file from the `proposed` directory to the `approved` directory:
        ```bash
        mv /tmp/bcr-pipeline/proposed/test_call_01.oga /tmp/bcr-pipeline/approved/
        ```
    *   **Observe the script's terminal.** You should see a series of logs indicating the approval was received and processing has started:
        ```
        APPROVAL RECEIVED: New file 'test_call_01.oga' detected in '/tmp/bcr-pipeline/approved'.
        ffmpeg failed for /tmp/bcr-pipeline/approved/test_call_01.oga: ...
        Error processing /tmp/bcr-pipeline/approved/test_call_01.oga: Audio preprocessing failed.
        Moved failed file to /tmp/bcr-pipeline/errors/test_call_01.oga
        Cleaned up source files for test_call_01.oga.
        ```
    *   **This is the expected outcome.** The script tries to process the file, `ffmpeg` fails on the empty dummy file, the script catches the error, and moves the file to the error directory.

3.  **Verify the final state:**
    *   Check that the `approved` directory is now empty.
    *   Check that `test_call_01.oga` now exists in the `/tmp/bcr-pipeline/errors` directory.

If you see all of the above behavior, the core logic is working correctly.
