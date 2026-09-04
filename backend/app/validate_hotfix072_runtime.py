from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path

import cv2
import numpy as np

from app.services.event_evidence import browser_preview_bytes, encode_clip


def probe(data: bytes) -> dict:
    with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as fh:
        fh.write(data)
        path = Path(fh.name)
    try:
        proc = subprocess.run(
            ['ffprobe','-v','error','-select_streams','v:0','-show_entries','stream=codec_name,codec_tag_string,pix_fmt','-show_entries','format=duration','-of','json',str(path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=15,
            check=False,
        )
        if proc.returncode != 0:
            raise RuntimeError(proc.stderr.decode(errors='replace'))
        return json.loads(proc.stdout.decode())
    finally:
        path.unlink(missing_ok=True)


def jpeg_frames() -> list[tuple[str, bytes]]:
    out=[]
    for i in range(4):
        img=np.zeros((120,160,3),dtype=np.uint8)
        cv2.rectangle(img,(20+i*5,20),(80+i*5,100),(255,255,255),-1)
        ok,j=cv2.imencode('.jpg',img)
        if not ok: raise RuntimeError('JPEG QA fallo')
        out.append((str(i),j.tobytes()))
    return out


def make_legacy_mp4v(frames: list[tuple[str, bytes]]) -> bytes:
    with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as fh:
        path=Path(fh.name)
    try:
        writer=cv2.VideoWriter(str(path),cv2.VideoWriter_fourcc(*'mp4v'),1.0,(160,120))
        if not writer.isOpened(): raise RuntimeError('OpenCV mp4v QA no disponible')
        for _,raw in frames:
            img=cv2.imdecode(np.frombuffer(raw,np.uint8),cv2.IMREAD_COLOR)
            writer.write(img)
        writer.release()
        return path.read_bytes()
    finally:
        path.unlink(missing_ok=True)


def main():
    frames=jpeg_frames()
    clip=encode_clip(frames,1.0)
    if not clip: raise RuntimeError('encode_clip H.264 vacio')
    meta=probe(clip); stream=meta['streams'][0]
    if stream.get('codec_name')!='h264' or stream.get('codec_tag_string') not in {'avc1','avc3'}:
        raise RuntimeError(f'Codec nuevo no browser-compatible: {stream}')
    if stream.get('pix_fmt')!='yuv420p':
        raise RuntimeError(f'Pixel format nuevo inesperado: {stream.get("pix_fmt")}')
    if float(meta['format']['duration'])<=0.5:
        raise RuntimeError('Duracion H.264 invalida')
    legacy=make_legacy_mp4v(frames)
    preview,mime,transcoded=browser_preview_bytes(legacy,'video/mp4')
    pmeta=probe(preview); pstream=pmeta['streams'][0]
    if mime!='video/mp4' or not transcoded or pstream.get('codec_name')!='h264':
        raise RuntimeError(f'Preview legacy no convertido: {pstream}')
    print(f"HOTFIX072_VIDEO_OK new_codec={stream['codec_name']} tag={stream['codec_tag_string']} pix={stream['pix_fmt']} duration={meta['format']['duration']} legacy_preview={pstream['codec_name']}")


if __name__=='__main__':
    main()
