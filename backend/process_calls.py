import time
import os
import subprocess
import json
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import openai
import logging

# --- Configuration ---
# General settings
WATCH_DIR = "/path/to/server/incoming-calls"
OUTPUT_DIR = "/path/to/server/processed"
ERROR_DIR = "/path/to/server/errors"

# --- Provider Selection ---
# Choose 'self-hosted' or 'openai' for transcription and summarization.
TRANSCRIPTION_PROVIDER = "self-hosted"  # 'self-hosted' or 'openai'
SUMMARIZATION_PROVIDER = "self-hosted"  # 'self-hosted' or 'openai'

# --- API Credentials and Models ---
# OpenAI API Settings (used if 'openai' is selected as a provider)
OPENAI_API_KEY = "sk-your-openai-api-key"
OPENAI_WHISPER_MODEL = "whisper-1"         # e.g., 'whisper-1'
OPENAI_LLM_MODEL = "gpt-4-turbo-preview"  # e.g., 'gpt-4-turbo-preview'

# Self-Hosted API Settings (used if 'self-hosted' is selected)
# URL for the self-hosted Whisper-compatible API server
SELF_HOSTED_WHISPER_API_BASE = "http://localhost:9000/v1"
SELF_HOSTED_WHISPER_MODEL = "large-v3"

# URL for the self-hosted vLLM or other OpenAI-compatible API server
SELF_HOSTED_LLM_API_BASE = "http://localhost:8000/v1"
SELF_HOSTED_LLM_MODEL = "your-local-llm-model"

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S')

# --- Main Application ---
def initialize_clients():
    """Initializes the API clients based on the selected providers."""
    global openai_whisper, whisper_model, openai_llm, llm_model

    # --- Transcription Client ---
    if TRANSCRIPTION_PROVIDER == 'openai':
        logging.info("Using OpenAI API for transcription.")
        openai_whisper = openai.OpenAI(api_key=OPENAI_API_KEY)
        whisper_model = OPENAI_WHISPER_MODEL
    elif TRANSCRIPTION_PROVIDER == 'self-hosted':
        logging.info("Using self-hosted API for transcription.")
        openai_whisper = openai.OpenAI(base_url=SELF_HOSTED_WHISPER_API_BASE, api_key="dummy")
        whisper_model = SELF_HOSTED_WHISPER_MODEL
    else:
        logging.error(f"Invalid TRANSCRIPTION_PROVIDER: {TRANSCRIPTION_PROVIDER}")
        exit(1)

    # --- Summarization Client ---
    if SUMMARIZATION_PROVIDER == 'openai':
        logging.info("Using OpenAI API for summarization.")
        openai_llm = openai.OpenAI(api_key=OPENAI_API_KEY)
        llm_model = OPENAI_LLM_MODEL
    elif SUMMARIZATION_PROVIDER == 'self-hosted':
        logging.info("Using self-hosted API for summarization.")
        openai_llm = openai.OpenAI(base_url=SELF_HOSTED_LLM_API_BASE, api_key="dummy")
        llm_model = SELF_HOSTED_LLM_MODEL
    else:
        logging.error(f"Invalid SUMMARIZATION_PROVIDER: {SUMMARIZATION_PROVIDER}")
        exit(1)

class CallHandler(FileSystemEventHandler):
    """Handles file system events for new call recordings."""
    def on_created(self, event):
        if event.is_directory:
            return
        time.sleep(2)  # Wait for the file to be fully written
        filepath = event.src_path
        logging.info(f"New file detected: {filepath}")
        process_audio(filepath)

def preprocess_audio(input_path):
    """Converts the input audio file to a 16kHz mono WAV file using ffmpeg."""
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
    """The main processing pipeline for a single audio file."""
    wav_file = None
    try:
        # 1. Preprocess audio
        wav_file = preprocess_audio(filepath)
        if not wav_file:
            raise ValueError("Audio preprocessing failed.")

        # 2. Transcribe audio
        logging.info(f"Transcribing {wav_file} with {TRANSCRIPTION_PROVIDER} ({whisper_model})...")
        with open(wav_file, "rb") as f:
            transcription_text = openai_whisper.audio.transcriptions.create(
                model=whisper_model,
                file=f,
                response_format="text"
            )
        logging.info("Transcription successful.")

        # 3. Summarize transcript
        logging.info(f"Summarizing transcript with {SUMMARIZATION_PROVIDER} ({llm_model})...")
        chat_completion = openai_llm.chat.completions.create(
            model=llm_model,
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
            "transcription_provider": TRANSCRIPTION_PROVIDER,
            "transcription_model": whisper_model,
            "summarization_provider": SUMMARIZATION_PROVIDER,
            "summarization_model": llm_model,
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
        os.makedirs(ERROR_DIR, exist_ok=True)
        error_path = os.path.join(ERROR_DIR, os.path.basename(filepath))
        try:
            os.rename(filepath, error_path)
            logging.info(f"Moved failed file to {error_path}")
        except OSError as rename_error:
            logging.error(f"Could not move failed file to error directory: {rename_error}")

    finally:
        # 5. Clean up
        if os.path.exists(filepath):
            os.remove(filepath)
        if wav_file and os.path.exists(wav_file):
            os.remove(wav_file)
        logging.info(f"Cleaned up source files for {os.path.basename(filepath)}.")

def main():
    """Sets up the watchdog observer to monitor the directory for new files."""
    # Ensure essential directories exist
    for dir_path in [WATCH_DIR, OUTPUT_DIR, ERROR_DIR]:
        if "/path/to/" in dir_path:
            logging.error(f"Configuration error: Please update the directory path '{dir_path}' in the script.")
            exit(1)
        os.makedirs(dir_path, exist_ok=True)

    initialize_clients()

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
