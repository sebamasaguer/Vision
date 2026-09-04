"""QA deterministic for Hotfix v0.4.1.

Validates both negative and positive clips shipped with the project. It does not
use Redis, PostgreSQL, or camera configuration, so it can run during installation.
"""
import os
import sys
import cv2

from app.services.vision_runtime import (
    IoUTracker,
    OpenCVHOGPersonDetector,
    apply_nms,
    harden_person_detections,
)

DEFAULTS = dict(
    min_box_area_ratio=0.015,
    max_box_area_ratio=0.18,
    min_height_ratio=0.18,
    min_aspect_ratio=0.28,
    max_aspect_ratio=0.95,
    top_band_reject_y_ratio=0.15,
    top_band_reject_bottom_ratio=0.62,
)


def evaluate(path, expect_person, inference_fps=2.0):
    capture = cv2.VideoCapture(path)
    if not capture.isOpened():
        raise RuntimeError(f'No se pudo abrir {path}')
    source_fps = float(capture.get(cv2.CAP_PROP_FPS) or 15.0)
    sample_every = max(1, int(round(source_fps / inference_fps)))
    detector = OpenCVHOGPersonDetector()
    tracker = IoUTracker(.25, 4, 3)
    index = 0
    samples = 0
    raw_total = 0
    filtered_total = 0
    confirmed_samples = 0
    max_confirmed = 0
    rejected_total = 0

    while True:
        ok, frame = capture.read()
        if not ok:
            break
        if index % sample_every == 0:
            samples += 1
            raw = detector.detect_raw(frame, .62)
            hardened, stats = harden_person_detections(raw, frame.shape, **DEFAULTS)
            filtered = apply_nms(hardened, .62, .35)
            tracks = tracker.update(filtered, now=index / source_fps)
            confirmed = tracker.confirmed_tracks()
            raw_total += len(raw)
            filtered_total += len(filtered)
            rejected_total += stats['rejected'] + max(0, len(hardened)-len(filtered)) + tracker.last_candidate_rejections
            confirmed_samples += int(bool(confirmed))
            max_confirmed = max(max_confirmed, len(confirmed))
        index += 1
    capture.release()

    result = {
        'path': path,
        'samples': samples,
        'raw_total': raw_total,
        'filtered_total': filtered_total,
        'confirmed_samples': confirmed_samples,
        'max_confirmed': max_confirmed,
        'rejected_total': rejected_total,
    }
    if expect_person:
        if confirmed_samples < max(3, samples // 3) or max_confirmed < 1:
            raise AssertionError(f'QA positivo fallo: {result}')
    else:
        if filtered_total != 0 or confirmed_samples != 0 or max_confirmed != 0:
            raise AssertionError(f'QA negativo fallo: {result}')
    return result


def main():
    demo_root = os.getenv('HYS_DEMO_ROOT', '/demo')
    negative = os.path.join(demo_root, 'qa_hardening_negative.mp4')
    positive = os.path.join(demo_root, 'qa_hardening_person.mp4')
    neg = evaluate(negative, False)
    pos = evaluate(positive, True)
    print('[NEGATIVE] geometric_demo raw={raw_total} filtered={filtered_total} confirmed_samples={confirmed_samples} max_confirmed={max_confirmed} rejected={rejected_total}'.format(**neg))
    print('[PASS] Demo geometrico: 0 PERSON / 0 TRACKS confirmados.')
    print('[POSITIVE] person_demo raw={raw_total} filtered={filtered_total} confirmed_samples={confirmed_samples} max_confirmed={max_confirmed} rejected={rejected_total}'.format(**pos))
    print('[PASS] Video con persona: TRACK confirmado y estable.')


if __name__ == '__main__':
    main()
