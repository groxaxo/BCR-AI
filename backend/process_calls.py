import time
import os
import subprocess
import json
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import openai
import logging

# --- Configuration ---
# Directory to watch for incoming call recordings.
# This should match the DEST_DIR in the push_recording.sh script.
WATCH_DIR = "/path/to/server/incoming-calls"

# Directory to store the processed JSON files.
OUTPUT_DIR = "/path/to/server/processed"

# Directory to log errors.
ERROR_DIR = "/path/to/server/errors"

# API endpoint for the self-hosted Whisper model.
# The default port is 9000 for the Docker container provided in the README.
WHISPER_API_BASE = "http://localhost:9000/v1"
WHISPER_API_KEY = "dummy"  # API key is not strictly required for local instances.
WHISPER_MODEL = "large-v3" # The model to use for transcription.

# API endpoint for the self-hosted vLLM.
# Replace with the actual URL of your vLLM service.
VLLM_API_BASE = "http://your_vllm_host:8000/v1"
VLLM_API_KEY = "dummy" # Use a real key if your service is protected.
VLLM_MODEL = "your-llm-model" # The model to use for summarization.

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S')

# --- Main Application ---
# Initialize API clients
try:
    openai_whisper = openai.OpenAI(base_url=WHISPER_API_BASE, api_key=WHISPER_API_KEY)
    openai_vllm = openai.OpenAI(base_url=VLLM_API_BASE, api_key=VLLM_API_KEY)
except Exception as e:
    logging.error(f"Failed to initialize OpenAI clients: {e}")
    # Exit if clients can't be initialized, as the script can't function.
    exit(1)


class CallHandler(FileSystemEventHandler):
    """
    Handles file system events for new call recordings.
    """
    def on_created(self, event):
        """
        Called when a file or directory is created.
        """
        if event.is_directory:
            return

        # Wait a moment to ensure the file is fully written
        time.sleep(2)

        filepath = event.src_path
        logging.info(f"New file detected: {filepath}")
        process_audio(filepath)


def preprocess_audio(input_path):
    """
    Converts the input audio file to a 16kHz mono WAV file using ffmpeg.
    Whisper performs best with WAV files in this format.
    """
    output_path = os.path.splitext(input_path)[0] + ".wav"
    try:
        cmd = ["ffmpeg", "-y", "-i", input_path,
               "-ar", "16000", "-ac", "1", output_path]
        subprocess.run(cmd, check=True, capture_output=True, text=True)
        logging.info(f"Successfully preprocessed {input_path} to {output_path}")
        return output_path
    except subprocess.CalledProcessError as e:
        logging.error(f"ffmpeg failed for {input_path}: {e.stderr}")
        return None


def process_audio(filepath):
    """
    The main processing pipeline for a single audio file.
    1. Preprocesses the audio file.
    2. Transcribes the audio using Whisper.
    3. Summarizes the transcript using a vLLM.
    4. Saves the results to a JSON file.
    5. Cleans up the original and temporary files.
    """
    wav_file = None
    try:
        # 1. Preprocess audio
        wav_file = preprocess_audio(filepath)
        if not wav_file:
            raise ValueError("Audio preprocessing failed.")

        # 2. Transcribe audio
        logging.info(f"Transcribing {wav_file} with Whisper ({WHISPER_MODEL})...")
        with open(wav_file, "rb") as f:
            transcription_text = openai_whisper.audio.transcriptions.create(
                model=WHISPER_MODEL,
                file=f,
                response_format="text"
            )
        logging.info("Transcription successful.")

        # 3. Summarize transcript
        logging.info(f"Summarizing transcript with vLLM ({VLLM_MODEL})...")
        chat_completion = openai_vllm.chat.completions.create(
            model=VLLM_MODEL,
            messages=[
                {"role": "system", "content": "Summarize the following call transcript and extract key points, action items, and entities discussed."},
                {"role": "user", "content": transcription_text}
            ]
        )
        summary = chat_completion.choices[0].message.content
        logging.info("Summarization successful.")

        # 4. Save results
        result = {
            "source_file": os.path.basename(filepath),
            "transcript": transcription_text,
            "summary": summary,
            "processed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        }

        os.makedirs(OUTPUT_DIR, exist_ok=True)
        json_filename = os.path.splitext(os.path.basename(filepath))[0] + ".json"
        json_path = os.path.join(OUTPUT_DIR, json_filename)

        with open(json_path, "w", encoding="utf-8") as jf:
            json.dump(result, jf, ensure_ascii=False, indent=2)

        logging.info(f"Successfully processed and saved to {json_path}")

    except Exception as e:
        logging.error(f"Error processing {filepath}: {e}")
        # Move the failed file to an error directory for manual inspection
        os.makedirs(ERROR_DIR, exist_ok=True)
        error_path = os.path.join(ERROR_DIR, os.path.basename(filepath))
        os.rename(filepath, error_path)
        logging.info(f"Moved failed file to {error_path}")

    finally:
        # 5. Clean up
        if os.path.exists(filepath):
            os.remove(filepath)
        if wav_file and os.path.exists(wav_file):
            os.remove(wav_file)
        logging.info(f"Cleaned up source files for {os.path.basename(filepath)}.")


def main():
    """
    Sets up the watchdog observer to monitor the directory for new files.
    """
    # Ensure directories exist
    os.makedirs(WATCH_DIR, exist_ok=True)
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(ERROR_DIR, exist_ok=True)

    event_handler = CallHandler()
    observer = Observer()
    observer.schedule(event_handler, WATCH_DIR, recursive=False)
    observer.start()

    logging.info(f"Monitoring directory for new calls: {WATCH_DIR}")

    try:
        while True:
            time.sleep(5)
    except KeyboardInterrupt:
        observer.stop()
        logging.info("Observer stopped.")
    observer.join()


if __name__ == "__main__":
    main()
