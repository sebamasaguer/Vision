import json
import subprocess
import tempfile
from pathlib import Path

import cv2
import numpy as np

from app.services.event_evidence import browser_preview_bytes, encode_clip


def _probe(data: bytes) -> dict:
    with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as fh:
        fh.write(data)
        path = Path(fh.name)
    try:
        proc = subprocess.run(
            ['ffprobe','-v','error','-select_streams','v:0','-show_entries','stream=codec_name,codec_tag_string,pix_fmt,width,height,duration','-show_entries','format=duration','-of','json',str(path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=15,
        )
        assert proc.returncode == 0, proc.stderr.decode(errors='replace')
        return json.loads(proc.stdout.decode())
    finally:
        path.unlink(missing_ok=True)


def _jpeg_frames(count=4):
    frames=[]
    for i in range(count):
        img=np.zeros((120,160,3),dtype=np.uint8)
        cv2.rectangle(img,(20+i*5,20),(80+i*5,100),(255,255,255),-1)
        ok,j=cv2.imencode('.jpg',img); assert ok
        frames.append((str(i),j.tobytes()))
    return frames


def test_encode_clip_generates_browser_compatible_h264_video_bytes():
    clip=encode_clip(_jpeg_frames(),1.0)
    assert clip is not None and len(clip)>500
    meta=_probe(clip)
    stream=meta['streams'][0]
    assert stream['codec_name']=='h264'
    assert stream['codec_tag_string'] in {'avc1','avc3'}
    assert stream['pix_fmt']=='yuv420p'
    assert float(meta['format']['duration'])>0.5


def test_browser_preview_transcodes_legacy_mp4v_without_mutating_source():
    frames=[]
    for _,raw in _jpeg_frames():
        frames.append(cv2.imdecode(np.frombuffer(raw,np.uint8),cv2.IMREAD_COLOR))
    with tempfile.NamedTemporaryFile(suffix='.mp4',delete=False) as fh:
        legacy_path=Path(fh.name)
    try:
        writer=cv2.VideoWriter(str(legacy_path),cv2.VideoWriter_fourcc(*'mp4v'),1.0,(160,120))
        assert writer.isOpened()
        for img in frames: writer.write(img)
        writer.release()
        legacy=legacy_path.read_bytes()
    finally:
        legacy_path.unlink(missing_ok=True)
    original=bytes(legacy)
    preview,mime,transcoded=browser_preview_bytes(legacy,'video/mp4')
    assert legacy==original
    assert mime=='video/mp4' and transcoded is True and preview!=legacy
    stream=_probe(preview)['streams'][0]
    assert stream['codec_name']=='h264' and stream['pix_fmt']=='yuv420p'
