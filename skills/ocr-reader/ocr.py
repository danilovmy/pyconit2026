from doctr.models import ocr_predictor
from doctr.io import DocumentFile
from pathlib import Path
import json

import sys
import subprocess
from PIL import Image
from docuwarp.unwarp import Unwarp
import shutil
# Load model
from argparse import ArgumentParser
import bbox_align

import logging

logger = logging.getLogger(__file__)
handler = logging.FileHandler( Path(__file__).parent / "logger.log")
handler.setFormatter(logging.Formatter('%(asctime)s: %(message)s'))
logger.addHandler(handler)

MODEL_SIZE = "medium"
model = {MODEL_SIZE: None}

def align(extract_info):
    vertices = []
    words = []
    # minx, maxx, miny, maxy = 0, 0 , 0, 0

    for idx, obj in enumerate(extract_info['words']):
        obj["geometry"] = sorted(obj["geometry"], key=lambda x: x[0])
        tl, bl, tr, br = [*sorted(obj["geometry"][:2], key=lambda x: x[1]), *sorted(obj["geometry"][2:], key=lambda x: x[1])]
        obj["geometry"] = [tl, tr, br, bl]
        if (tl == tr) or (br == bl) or (tl == bl) or (tr == br):
            logger.error(f'Geometry error {obj["geometry"]}')
            continue
        if obj["crop_orientation"]["value"] == 180:
            obj["value"] = obj["value"][::-1]

        vertices += [obj["geometry"]]
            # x1,y1,x2,y2 = int(float(x1)*100), int(float(y1)*100), int(float(x2)*100), int(float(y2)*100) #float(x1),float(y1,float(x2,float(y2)
        words += [obj["value"]]


    boundaries = [[0,0],[1,0],[1,1],[0,1]]
    
    logger.info(f'align worlds')
    lines = bbox_align.process(vertices, boundaries)
    logger.info(f'worlds aligned')

    sentence_list = []
    for line in lines:
        sentence_list += ' '.join(words[idx] for idx in line),
    return sentence_list

def parse_args(argv=None):
    parser = ArgumentParser( description="Move an inbound image file to media/archive/bills, Run OCR on an image or PDF file with doctr model, and save the transcript next to the archived file." )
    parser.add_argument("input", nargs='+', help="Path to input media file (typically in media/inbound)")
    parser.add_argument('-v', '--verbose', action='store_true', help="log more info", default=False)
    parser.add_argument('-k', '--keep-on-place', action='store_true', help="Don't move the file, don't clean up", default=False)
    parser.add_argument('-s', '--silent', action='store_true', help="Don't send any callback", default=False)
    parser.add_argument('-sid', '--session-id', help="session id", default=None)
    parser.add_argument('-a', '--agent', help="Agent to notify", default="main")
    parser.add_argument('-w', '--wrapped', action='store_true', help="OCR wrapped image", default=False)
    # doctr not allow to set language
    # parser.add_argument('-lang', '--language', help="Strict define language", default='')
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

def prepare_filename(filename, keep_on_place=False, **kwargs):
    if keep_on_place:
        return filename

    # Derive archive directory: .../media/inbound/... -> .../media/archive/...
    # Assume structure C:/.../media/inbound/<file>
    archive_dir = Path(__file__).parent.parent.parent / 'media' / "archive" / "bills"
    archive_dir.mkdir(parents=True, exist_ok=True)
    
    processed_filename = archive_dir / filename.name

    # 1) Move file first
    shutil.move(str(filename), processed_filename)

    return processed_filename

def unwarp_image(filename):
    logger.info(f'before unwarp {filename}')
    _image = Image.open(filename)
    image = Unwarp().inference(_image)
    _image.close()
    image.save(filename.parent / f'{filename.stem}_unwarped{filename.suffix}')
    image.close()
    logger.info(f'unwarped {filename} save')
    return filename.parent / f'{filename.stem}_unwarped{filename.suffix}'


def process_file(filename, wrap=False, keep_on_place=False, **kwargs):
    logger.info(f'process_file {filename}')
    if filename.suffix.lower() == ".pdf":
        doc = DocumentFile.from_pdf(filename)
    else:
        if wrap:
            doc = DocumentFile.from_images(filename)
        else:
            unwarped_image = unwarp_image(filename)
            doc = DocumentFile.from_images(unwarped_image)
            if not keep_on_place:
                Path(unwarped_image).unlink(missing_ok=True)

    logger.info(f'Doctr doc created')
    # Run OCR
    model = get_model()
    result = model(doc)
    extract_info = result.export()

    logger.info(f'Doctr doc predicted')
    
    as_json={'words': []}

    as_json['dimensions'] = extract_info['pages'][0]['dimensions']
    for obj1 in extract_info['pages'][0]["blocks"]:
        as_json['geometry'] = [[float(x),float(y)] for x,y in obj1['geometry']]
        for obj2 in obj1["lines"]:
            as_json['words'] += obj2["words"]

    logger.info(f'predictions ready to align')

    (filename.parent / f'{filename.stem}.txt').write_text('\n'.join(align(as_json)))

def get_model(size=MODEL_SIZE):
    if not model.get(size):
        model[size] = ocr_predictor(pretrained=True, assume_straight_pages=False)
        logger.info(f'OCR model loaded')
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
    send_callback(f"[ocr-start] file: {in_path.name}", **kwargs)

    # 3) archivate file
    processed_filename = prepare_filename(in_path, **kwargs)

    # 4) transcribe    
    process_file(processed_filename, **kwargs)

    # 5) Notify agent via CLI so it can process the transcript
    send_callback(f"[ocr-done] file: {processed_filename.name}", **kwargs)


if __name__ == "__main__":
    try:
        main(sys.argv[1:])
    except Exception as e:
        logger.error(f'{e}')