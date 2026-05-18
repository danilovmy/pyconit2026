# -*- coding: utf-8 -*-
from faster_whisper import WhisperModel

from argparse import ArgumentParser
import shutil
import sys, os
import subprocess
from pathlib import Path
import logging

logger = logging.getLogger(__file__)
handler = logging.FileHandler( Path(__file__).parent / "logger.log")
handler.setFormatter(logging.Formatter('%(asctime)s: %(message)s'))
logger.addHandler(handler)
GATEWAY_URL = "http://127.0.0.1:18789"  # openclaw case
TOKEN = "token_to_connect_through_http" # openclaw case
import requests


# Match model/config with wisper.py
MODEL_SIZE = "medium"
model = {MODEL_SIZE: None}
# model = WhisperModel('medium', device="cpu", compute_type="int8")


def parse_args(argv=None):
    parser = ArgumentParser( description="Move an inbound media file to archive, transcribe it with fast-whisper, " "and save the transcript next to the archived file." )
    parser.add_argument("input", nargs='+', help="Path to input media file (typically in media/inbound)")
    parser.add_argument('-s', '--silent', action='store_true', help="Don't send any callback", default=False)
    parser.add_argument('-v', '--verbose', action='store_true', help="Log more info", default=False)
    parser.add_argument('-a', '--agent', help="Agent to notify", default="main")
    parser.add_argument('-sid', '--session-id', help="session id", default=None)
    parser.add_argument('-k', '--keep-on-place', action='store_true', help="Don't move the file", default=False)
    parser.add_argument('-lang', '--language', help="Strict define language", default='')
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    if args.verbose:
        logger.setLevel(logging.INFO)
    logger.info(f'start main {vars(args)}')

    for filename in args.input:
        logger.info(f'start parse {filename}')
        processing(filename, **vars(args))

    logger.info('stop')

def send_callback(message, silent=False, agent="main", session_id=None, **kwargs):
    # Notify main agent about processing
    if not silent:
        try:
            logger.info(f'before callback send')
            # send_http_callback(message)
            # We send a small callback message; the agent will anderstand it itself.
            session_info = ["--session-id", session_id] if session_id else []
            subprocess.run(["openclaw.cmd", "agent", "--agent", agent, "--verbose", "off", "-m", message] + session_info, shell=False)
            logger.info(f'callback sended {message}')
        except Exception as e:
            # Failure to send start notification should not break transcription
            logger.error(f'{e}')


def send_http_callback(message):
    headers = {
        "Authorization": f"Bearer {TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "agent:main:main",
        "messages": [
            {"role": "user", "content": message}
        ],
    }
    response = requests.post(f"{GATEWAY_URL}/v1/chat/completions", json=payload, headers=headers, timeout=30)
    response.raise_for_status()
    logger.info(f'callback answer: {response.json()}') 


def prepare_filename(filename, keep_on_place=False, **kwargs):
    if keep_on_place:
        return filename

    # Derive archive directory: .../media/inbound/... -> .../media/archive/...
    # Assume structure C:/.../media/inbound/<file>
    archive_dir = Path(__file__).parent.parent.parent / 'media' / "archive"
    archive_dir.mkdir(parents=True, exist_ok=True)
    
    processed_filename = archive_dir / filename.name

    # 1) Move file first
    shutil.move(str(filename), processed_filename)

    return processed_filename

def process_file(filename, language='', **kwargs):
    # 1) Transcribe from file
    try:
        logger.info(f'model start transcribe audio')
        with filename.open('rb') as source:
            kw = {}
            if language and language in ['de', 'en', 'ru']:
                kw['language'] = language
                logger.info(f'strict defined language {language}')
            segments, info = get_model().transcribe(source, beam_size=5, **kw)
        logger.info(f'model transcribed audio')
    except Exception as e:
        logger.error(f'model transcribing error {e}')

    # 2) Notify about Detected language
    lines = [f"Detected language '{info.language}' with probability {info.language_probability}"]

    # 3) Concatenate all segment texts into a single string
    for segment in segments:
        lines.append(f"[{segment.start} -> {segment.end}] {segment.text}")
    logger.info(f'transcription ready to save')
    # 4) Save transcript next to audio file
    filename.with_suffix(".txt").write_text("\n".join(lines), encoding="utf-8")
    
def get_model(size=MODEL_SIZE):
    if not model.get(size):
        model[size] = WhisperModel(size, device="cpu", compute_type="int8")
        logger.info(f'whisper model loaded')
    return model[size]

def processing(filename, **kwargs):

    # 1) prepare and check file
    logger.info(f'processing {filename}')
    in_path = Path(filename).expanduser().resolve()
    logger.info(f'processing full filename {in_path}')
    if not in_path.exists() or not in_path.is_file():
        logger.info(f'file not found {in_path}')
        return


    # 2) Notify caller about start of processing
    send_callback(f"[transcribe-start] file: {in_path.name}", **kwargs)

    # 3) archivate file
    processed_filename = prepare_filename(in_path, **kwargs)

    # 4) transcribe    
    process_file(processed_filename, **kwargs)

    # 5) Notify agent via CLI so it can process the transcript
    send_callback(f"[transcribe-done] file: {processed_filename.name}", **kwargs)


if __name__ == "__main__":
    try:
        main(sys.argv[1:])
    except Exception as e:
        logger.error(f'{e}')