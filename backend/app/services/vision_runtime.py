import json
import math
import time
from dataclasses import dataclass
from datetime import datetime, timezone

import cv2
import numpy as np

from app.core.config import settings
from app.services.camera_runtime import redis_client, frame_key

VISION_HEARTBEAT = 'hys:vision-engine:heartbeat'
VISION_RESULT = 'hys:vision:result:'
VISION_OVERLAY = 'hys:vision:overlay:'


def result_key(camera_id):
    return f'{VISION_RESULT}{camera_id}'


def overlay_key(camera_id):
    return f'{VISION_OVERLAY}{camera_id}'


def iou(a, b):
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    x1, y1 = max(ax, bx), max(ay, by)
    x2, y2 = min(ax + aw, bx + bw), min(ay + ah, by + bh)
    inter = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    union = max(0.0, aw * ah) + max(0.0, bw * bh) - inter
    return inter / union if union > 0 else 0.0


def point_in_polygon(x, y, points):
    inside = False
    j = len(points) - 1
    for i, p in enumerate(points):
        xi, yi = float(p['x']), float(p['y'])
        xj, yj = float(points[j]['x']), float(points[j]['y'])
        if ((yi > y) != (yj > y)) and x < (xj - xi) * (y - yi) / (yj - yi + 1e-12) + xi:
            inside = not inside
        j = i
    return inside


def clip_bbox(bbox, frame_width, frame_height):
    x, y, w, h = [float(v) for v in bbox]
    x1 = min(max(x, 0.0), float(frame_width))
    y1 = min(max(y, 0.0), float(frame_height))
    x2 = min(max(x + w, 0.0), float(frame_width))
    y2 = min(max(y + h, 0.0), float(frame_height))
    if x2 <= x1 or y2 <= y1:
        return None
    return [x1, y1, x2 - x1, y2 - y1]


class OpenCVHOGPersonDetector:
    """CPU baseline PERSON detector.

    It deliberately exposes raw proposals separately from hardening so that metrics
    distinguish detector output from accepted person candidates.
    """

    code = 'OPENCV_HOG_PERSON_BASELINE'

    def __init__(self):
        self.hog = cv2.HOGDescriptor()
        self.hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())

    def detect_raw(self, frame, min_confidence=0.62):
        h, w = frame.shape[:2]
        scale = min(1.0, 800.0 / max(w, 1))
        work = cv2.resize(frame, None, fx=scale, fy=scale) if scale < 1 else frame
        rects, weights = self.hog.detectMultiScale(
            work, winStride=(8, 8), padding=(8, 8), scale=1.05
        )
        proposals = []
        for (x, y, bw, bh), weight in zip(rects, weights):
            confidence = 1.0 / (1.0 + math.exp(-float(weight)))
            if confidence < float(min_confidence):
                continue
            proposals.append({
                'bbox': [x / scale, y / scale, bw / scale, bh / scale],
                'confidence': round(float(confidence), 4),
            })
        return proposals

    def detect(self, frame, min_confidence=0.62, nms_iou_threshold=0.35):
        """Compatibility method: raw proposals + NMS, without geometric hardening."""
        raw = self.detect_raw(frame, min_confidence)
        return apply_nms(raw, min_confidence, nms_iou_threshold)


def apply_nms(detections, score_threshold=0.05, nms_iou_threshold=0.35):
    if not detections:
        return []
    boxes = [[int(round(v)) for v in d['bbox']] for d in detections]
    scores = [float(d['confidence']) for d in detections]
    keep = cv2.dnn.NMSBoxes(
        boxes, scores, float(score_threshold), float(nms_iou_threshold)
    )
    indexes = [int(i) for i in np.array(keep).reshape(-1)] if len(keep) else []
    return [detections[i] for i in indexes]


def harden_person_detections(
    detections,
    frame_shape,
    *,
    min_box_area_ratio=0.015,
    max_box_area_ratio=0.18,
    min_height_ratio=0.18,
    min_aspect_ratio=0.28,
    max_aspect_ratio=0.95,
    top_band_reject_y_ratio=0.15,
    top_band_reject_bottom_ratio=0.62,
):
    """Reject geometrically implausible HOG PERSON proposals.

    The upper-band rule specifically protects fixed camera scenes with headers,
    signage and rectangular structures while remaining configurable per camera.
    It is not a labor/safety rule; it is a detector quality heuristic.
    """
    frame_h, frame_w = frame_shape[:2]
    frame_area = max(float(frame_w * frame_h), 1.0)
    accepted = []
    reasons = {
        'invalid_box': 0,
        'area_too_small': 0,
        'area_too_large': 0,
        'height_too_small': 0,
        'aspect_ratio': 0,
        'upper_band': 0,
    }

    for item in detections:
        box = clip_bbox(item['bbox'], frame_w, frame_h)
        if not box:
            reasons['invalid_box'] += 1
            continue
        x, y, bw, bh = box
        area_ratio = (bw * bh) / frame_area
        height_ratio = bh / max(float(frame_h), 1.0)
        aspect_ratio = bw / max(bh, 1e-9)
        top_ratio = y / max(float(frame_h), 1.0)
        bottom_ratio = (y + bh) / max(float(frame_h), 1.0)

        if area_ratio < float(min_box_area_ratio):
            reasons['area_too_small'] += 1
            continue
        if area_ratio > float(max_box_area_ratio):
            reasons['area_too_large'] += 1
            continue
        if height_ratio < float(min_height_ratio):
            reasons['height_too_small'] += 1
            continue
        if not (float(min_aspect_ratio) <= aspect_ratio <= float(max_aspect_ratio)):
            reasons['aspect_ratio'] += 1
            continue
        if top_ratio <= float(top_band_reject_y_ratio) and bottom_ratio <= float(top_band_reject_bottom_ratio):
            reasons['upper_band'] += 1
            continue

        accepted.append({
            **item,
            'bbox': box,
            'geometry': {
                'area_ratio': round(area_ratio, 5),
                'height_ratio': round(height_ratio, 5),
                'aspect_ratio': round(aspect_ratio, 5),
            },
        })

    return accepted, {
        'rejected': sum(reasons.values()),
        'reasons': reasons,
    }


@dataclass
class Track:
    id: int
    bbox: list
    confidence: float
    age: int = 1
    missed: int = 0
    hits: int = 1
    state: str = 'candidate'
    first_seen: float = 0.0
    last_seen: float = 0.0

    @property
    def confirmed(self):
        return self.state == 'confirmed'


class IoUTracker:
    """Small deterministic tracker with candidate -> confirmed lifecycle.

    min_hits_to_confirm defaults to 1 for backwards compatibility with v0.4.0
    unit tests. The production v0.4.1 engine passes the per-camera value (default 3).
    """

    def __init__(self, iou_threshold=.25, max_missed=4, min_hits_to_confirm=1):
        self.iou_threshold = float(iou_threshold)
        self.max_missed = int(max_missed)
        self.min_hits_to_confirm = int(min_hits_to_confirm)
        self.next_id = 1
        self.tracks = {}
        self.last_candidate_rejections = 0

    def update(self, detections, now=None):
        now = now or time.time()
        unmatched = set(range(len(detections)))
        self.last_candidate_rejections = 0

        # Confirmed tracks are matched first, then candidates, to reduce ID stealing.
        ordered_ids = sorted(
            self.tracks,
            key=lambda tid: (not self.tracks[tid].confirmed, tid),
        )
        for tid in ordered_ids:
            tr = self.tracks.get(tid)
            if tr is None:
                continue
            best = None
            best_score = self.iou_threshold
            for index in list(unmatched):
                score = iou(tr.bbox, detections[index]['bbox'])
                if score >= best_score:
                    best = index
                    best_score = score
            tr.age += 1
            if best is None:
                tr.missed += 1
                if tr.missed > self.max_missed:
                    if not tr.confirmed:
                        self.last_candidate_rejections += 1
                    self.tracks.pop(tid, None)
                continue

            detection = detections[best]
            unmatched.remove(best)
            tr.bbox = detection['bbox']
            tr.confidence = float(detection['confidence'])
            tr.hits += 1
            tr.missed = 0
            tr.last_seen = now
            if not tr.confirmed and tr.hits >= self.min_hits_to_confirm:
                tr.state = 'confirmed'

        for index in unmatched:
            detection = detections[index]
            tid = self.next_id
            self.next_id += 1
            state = 'confirmed' if self.min_hits_to_confirm <= 1 else 'candidate'
            self.tracks[tid] = Track(
                tid,
                detection['bbox'],
                float(detection['confidence']),
                age=1,
                missed=0,
                hits=1,
                state=state,
                first_seen=now,
                last_seen=now,
            )

        return list(self.tracks.values())

    def confirmed_tracks(self, visible_only=True):
        return [
            track for track in self.tracks.values()
            if track.confirmed and (not visible_only or track.missed == 0)
        ]

    def candidate_tracks(self):
        return [track for track in self.tracks.values() if not track.confirmed]


def assign_zones(track, zones, width, height):
    x, y, w, h = track.bbox
    px = (x + w / 2) / max(width, 1)
    py = (y + h) / max(height, 1)
    return [
        {'id': str(z.id), 'code': z.code, 'name': z.name}
        for z in zones
        if point_in_polygon(px, py, z.polygon_points)
    ]


def _label_origin(x, y, label_width, frame_width, frame_height):
    x = max(2, min(int(x), max(2, frame_width - label_width - 4)))
    y = int(y)
    if y < 24:
        y = min(frame_height - 4, y + 24)
    else:
        y = y - 6
    return x, max(18, min(y, frame_height - 4))


def render_overlay(frame, tracks, zones):
    img = frame.copy()
    frame_h, frame_w = img.shape[:2]

    for zone in zones:
        points = np.array(
            [[int(p['x'] * frame_w), int(p['y'] * frame_h)] for p in zone.polygon_points],
            np.int32,
        )
        if len(points) >= 3:
            cv2.polylines(img, [points], True, (79, 226, 182), 2, cv2.LINE_AA)
            zx, zy = _label_origin(points[0][0], points[0][1], 110, frame_w, frame_h)
            cv2.putText(img, zone.code, (zx, zy), cv2.FONT_HERSHEY_SIMPLEX, .5, (79, 226, 182), 1, cv2.LINE_AA)

    visible = [track for track in tracks if track.confirmed and track.missed == 0]
    for track in visible:
        x, y, bw, bh = [int(round(v)) for v in track.bbox]
        x = max(0, min(x, frame_w - 1))
        y = max(0, min(y, frame_h - 1))
        x2 = max(x + 1, min(x + bw, frame_w - 1))
        y2 = max(y + 1, min(y + bh, frame_h - 1))
        cv2.rectangle(img, (x, y), (x2, y2), (79, 226, 182), 2)
        label = f'TRACK-{track.id:04d}  PERSON {track.confidence:.2f}'
        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, .48, 1)
        lx, ly = _label_origin(x, y, tw, frame_w, frame_h)
        cv2.rectangle(img, (lx - 2, ly - th - 5), (lx + tw + 3, ly + 3), (8, 26, 30), -1)
        cv2.putText(img, label, (lx, ly), cv2.FONT_HERSHEY_SIMPLEX, .48, (79, 226, 182), 1, cv2.LINE_AA)

    ok, encoded = cv2.imencode('.jpg', img, [int(cv2.IMWRITE_JPEG_QUALITY), 84])
    return encoded.tobytes() if ok else None


def publish_vision(redis, camera_id, result, overlay):
    ttl = max(3, settings.vision_result_ttl_seconds)
    pipeline = redis.pipeline()
    pipeline.set(result_key(camera_id), json.dumps(result, separators=(',', ':')).encode(), ex=ttl)
    if overlay:
        pipeline.set(overlay_key(camera_id), overlay, ex=ttl)
    pipeline.execute()


def create_detector(backend: str):
    if backend == 'opencv_hog':
        return OpenCVHOGPersonDetector()
    raise RuntimeError(f'Backend de detector no soportado: {backend}')
