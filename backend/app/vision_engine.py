import json
import signal
import time
from collections import deque
from datetime import datetime, timezone

import cv2
import numpy as np
from sqlalchemy import select

from app.db.session import SessionLocal
from app.core.config import settings
from app.models.camera import Camera
from app.models.safety import Zone, PPEType, ZonePPERule, SafetyDetectionEvent
from app.models.vision import CameraVisionSetting, VisionModelVersion
from app.models.ml import MLModelDeployment, MLShadowObservation
from app.services.camera_runtime import redis_client, frame_key, meta_key
from app.services.vision_runtime import (
    VISION_HEARTBEAT,
    IoUTracker,
    apply_nms,
    assign_zones,
    create_detector,
    harden_person_detections,
    publish_vision,
    render_overlay,
)
from app.services.ppe_runtime import create_ppe_detector, render_ppe_overlay
from app.services.compliance_runtime import TemporalComplianceEngine
from app.services.safety_events import close_event, get_open_event, open_or_get_event, persist_evaluation, update_event
from app.services.event_evidence import capture_event_evidence

stop = False


def halt(*_):
    global stop
    stop = True


def _tracker_signature(cfg):
    return (
        round(float(cfg.tracker_iou_threshold), 6),
        int(cfg.tracker_max_missed_frames),
        int(cfg.tracker_min_hits_to_confirm),
    )


def _hardening_kwargs(cfg):
    return {
        'min_box_area_ratio': float(cfg.min_box_area_ratio),
        'max_box_area_ratio': float(cfg.max_box_area_ratio),
        'min_height_ratio': float(cfg.min_height_ratio),
        'min_aspect_ratio': float(cfg.min_aspect_ratio),
        'max_aspect_ratio': float(cfg.max_aspect_ratio),
        'top_band_reject_y_ratio': float(cfg.top_band_reject_y_ratio),
        'top_band_reject_bottom_ratio': float(cfg.top_band_reject_bottom_ratio),
    }


def _compliance_policy(cfg):
    return {
        'window_seconds': float(cfg.compliance_window_seconds),
        'min_persistence_seconds': float(cfg.compliance_min_persistence_seconds),
        'min_consensus_ratio': float(cfg.compliance_min_consensus_ratio),
        'min_missing_observations': int(cfg.compliance_min_missing_observations),
        'cooldown_seconds': float(cfg.compliance_cooldown_seconds),
        'clear_grace_seconds': float(cfg.compliance_clear_grace_seconds),
        'track_absence_close_seconds': float(cfg.compliance_track_absence_close_seconds),
    }


def _compliance_signature(cfg):
    p = _compliance_policy(cfg)
    return tuple((k, round(v, 6) if isinstance(v, float) else v) for k, v in sorted(p.items()))


def _rule_payloads(db, zones):
    zone_map = {z.id: z for z in zones}
    if not zone_map:
        return []
    rows = db.execute(
        select(ZonePPERule, PPEType)
        .join(PPEType, PPEType.id == ZonePPERule.ppe_type_id)
        .where(ZonePPERule.zone_id.in_(list(zone_map)), ZonePPERule.active.is_(True), PPEType.active.is_(True))
    ).all()
    payloads = []
    for rule, ppe in rows:
        zone = zone_map.get(rule.zone_id)
        payloads.append({
            'id': str(rule.id), 'zone_id': str(rule.zone_id),
            'zone_code': zone.code if zone else None, 'zone_name': zone.name if zone else None,
            'ppe_type_id': str(ppe.id), 'ppe_code': ppe.code, 'ppe_name': ppe.name,
            'requirement': rule.requirement, 'severity': rule.severity,
            'min_confidence': float(rule.min_confidence) if rule.min_confidence is not None else float(ppe.min_confidence),
            'schedule_start': rule.schedule_start, 'schedule_end': rule.schedule_end,
            'task': rule.task, 'risk_level': rule.risk_level, 'operation_type': rule.operation_type, 'active': rule.active,
        })
    return payloads


def main():
    signal.signal(signal.SIGTERM, halt)
    signal.signal(signal.SIGINT, halt)
    redis = redis_client()
    detectors = {}
    ppe_detectors = {}
    shadow_detectors = {}
    shadow_last_sample = {}
    trackers = {}
    tracker_signatures = {}
    compliance_engines = {}
    compliance_signatures = {}
    evidence_buffers = {}
    last_seen = {}
    last_inference = {}

    while not stop:
        try:
            redis.set(
                VISION_HEARTBEAT,
                json.dumps({
                    'at': datetime.now(timezone.utc).isoformat(),
                    'backend': 'multi-provider',
                    'hardening': '0.4.1',
                }),
                ex=20,
            )
            with SessionLocal() as db:
                rows = db.execute(
                    select(Camera, CameraVisionSetting, VisionModelVersion)
                    .join(CameraVisionSetting, CameraVisionSetting.camera_id == Camera.id)
                    .join(VisionModelVersion, VisionModelVersion.id == CameraVisionSetting.model_version_id)
                    .where(Camera.active.is_(True), CameraVisionSetting.enabled.is_(True))
                ).all()

                for camera, cfg, model in rows:
                    try:
                        raw_meta = redis.get(meta_key(camera.id))
                        raw_frame = redis.get(frame_key(camera.id))
                        if not raw_meta or not raw_frame:
                            continue
                        meta = json.loads(raw_meta.decode())
                        captured_at = meta.get('captured_at')
                        if last_seen.get(camera.id) == captured_at:
                            continue
                        if time.monotonic() - last_inference.get(camera.id, 0.0) < 1 / max(float(cfg.inference_fps), 0.2):
                            continue
                        last_seen[camera.id] = captured_at
                        last_inference[camera.id] = time.monotonic()

                        frame = cv2.imdecode(np.frombuffer(raw_frame, np.uint8), cv2.IMREAD_COLOR)
                        if frame is None:
                            continue

                        detector = detectors.get(model.backend)
                        if detector is None:
                            detector = create_detector(model.backend)
                            detectors[model.backend] = detector

                        started = time.perf_counter()
                        raw_detections = detector.detect_raw(frame, float(cfg.min_confidence))
                        hardened, filter_stats = harden_person_detections(
                            raw_detections,
                            frame.shape,
                            **_hardening_kwargs(cfg),
                        )
                        filtered_detections = apply_nms(
                            hardened,
                            float(cfg.min_confidence),
                            float(cfg.nms_iou_threshold),
                        )
                        nms_rejections = max(0, len(hardened) - len(filtered_detections))

                        signature = _tracker_signature(cfg)
                        tracker = trackers.get(camera.id)
                        if tracker is None or tracker_signatures.get(camera.id) != signature:
                            tracker = IoUTracker(
                                float(cfg.tracker_iou_threshold),
                                int(cfg.tracker_max_missed_frames),
                                int(cfg.tracker_min_hits_to_confirm),
                            )
                            trackers[camera.id] = tracker
                            tracker_signatures[camera.id] = signature

                        all_tracks = tracker.update(filtered_detections)
                        confirmed_tracks = tracker.confirmed_tracks(visible_only=True)
                        candidate_tracks = tracker.candidate_tracks()
                        zones = list(db.scalars(
                            select(Zone).where(Zone.camera_id == camera.id, Zone.active.is_(True))
                        ))
                        ppe_model = db.get(VisionModelVersion, cfg.ppe_model_version_id) if cfg.ppe_model_version_id else None
                        ppe_detector = None
                        ppe_thresholds = {}
                        if cfg.ppe_enabled and ppe_model:
                            ppe_key = str(ppe_model.id)
                            ppe_detector = ppe_detectors.get(ppe_key)
                            if ppe_detector is None:
                                ppe_detector = create_ppe_detector(ppe_model.backend, ppe_model.model_metadata, ppe_model.artifact_uri)
                                ppe_detectors[ppe_key]=ppe_detector
                            supported = list(db.scalars(select(PPEType).where(PPEType.code.in_(['HELMET','VEST','SAFETY_SHOES']),PPEType.active.is_(True))))
                            ppe_thresholds = {item.code:float(item.min_confidence) for item in supported}

                        # Bloque 9: un candidato SHADOW nunca alimenta cumplimiento ni Safety Events.
                        shadow_dep = db.scalar(select(MLModelDeployment).where(
                            MLModelDeployment.organization_id == camera.organization_id,
                            MLModelDeployment.camera_id == camera.id,
                            MLModelDeployment.mode == 'SHADOW', MLModelDeployment.enabled.is_(True)
                        ).order_by(MLModelDeployment.started_at.desc()))
                        if shadow_dep is None:
                            shadow_dep = db.scalar(select(MLModelDeployment).where(
                                MLModelDeployment.organization_id == camera.organization_id,
                                MLModelDeployment.camera_id.is_(None),
                                MLModelDeployment.mode == 'SHADOW', MLModelDeployment.enabled.is_(True)
                            ).order_by(MLModelDeployment.started_at.desc()))
                        shadow_model = db.get(VisionModelVersion, shadow_dep.model_version_id) if shadow_dep else None
                        shadow_detector = None
                        shadow_error = None
                        if cfg.ppe_enabled and shadow_model:
                            try:
                                skey = str(shadow_model.id)
                                shadow_detector = shadow_detectors.get(skey)
                                if shadow_detector is None:
                                    shadow_detector = create_ppe_detector(shadow_model.backend, shadow_model.model_metadata, shadow_model.artifact_uri)
                                    shadow_detectors[skey] = shadow_detector
                            except Exception as exc:
                                shadow_error = str(exc)[:300]

                        frame_h, frame_w = frame.shape[:2]
                        # Ring buffer comprimido por cámara para evidencia previa al evento.
                        ok_evidence_jpg, evidence_jpg_arr = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
                        evidence_jpg = evidence_jpg_arr.tobytes() if ok_evidence_jpg else None
                        buf = evidence_buffers.setdefault(camera.id, deque(maxlen=8))
                        if evidence_jpg:
                            buf.append((captured_at, evidence_jpg))
                        items = []
                        shadow_dirty = False
                        shadow_frame = {'samples':0,'agreements':0}
                        now_mono = time.monotonic()
                        for track in confirmed_tracks:
                            ppe = ppe_detector.inspect_track(frame, track.bbox, thresholds=ppe_thresholds, visibility_ratio=float(cfg.ppe_min_visibility_ratio), uncertainty_margin=float(cfg.ppe_uncertainty_margin)) if ppe_detector else {}
                            track_id = f'TRACK-{track.id:04d}'
                            candidate_ppe = shadow_detector.inspect_track(frame, track.bbox, thresholds=ppe_thresholds, visibility_ratio=float(cfg.ppe_min_visibility_ratio), uncertainty_margin=float(cfg.ppe_uncertainty_margin)) if shadow_detector else {}
                            if shadow_dep and candidate_ppe:
                                for code in ('HELMET','VEST','SAFETY_SHOES'):
                                    base = ppe.get(code) or {'status':'NO_APLICA','confidence':None}
                                    cand = candidate_ppe.get(code) or {'status':'NO_APLICA','confidence':None}
                                    key=(str(shadow_dep.id),track_id,code)
                                    if now_mono-shadow_last_sample.get(key,0.0) >= float(settings.ml_shadow_sample_seconds):
                                        agree = str(base.get('status')) == str(cand.get('status'))
                                        db.add(MLShadowObservation(
                                            organization_id=camera.organization_id,camera_id=camera.id,deployment_id=shadow_dep.id,
                                            track_id=track_id,ppe_code=code,baseline_status=str(base.get('status')),
                                            candidate_status=str(cand.get('status')),baseline_confidence=base.get('confidence'),
                                            candidate_confidence=cand.get('confidence'),agreement=agree,observed_at=datetime.now(timezone.utc),
                                        ))
                                        shadow_last_sample[key]=now_mono; shadow_dirty=True
                                        shadow_frame['samples'] += 1; shadow_frame['agreements'] += int(agree)
                            items.append({
                                'track_id': track_id,'bbox': [round(v, 1) for v in track.bbox],
                                'confidence': round(track.confidence, 4),'age_frames': track.age,'hits': track.hits,'missed_frames': track.missed,'state': track.state,
                                'zones': assign_zones(track, zones, frame_w, frame_h),'ppe':ppe,'shadow_ppe':candidate_ppe,
                            })
                        if shadow_dirty:
                            db.commit()

                        display_items = [{**item, 'ppe': (item.get('shadow_ppe') or item.get('ppe') or {})} for item in items] if shadow_detector else items
                        overlay_evidence = render_ppe_overlay(frame, display_items, zones) if cfg.ppe_enabled and (ppe_detector or shadow_detector) else None
                        compliance_result = {'actions': [], 'samples': [], 'tracks': {}}
                        if cfg.compliance_enabled and cfg.ppe_enabled and ppe_detector:
                            policy = _compliance_policy(cfg)
                            signature = _compliance_signature(cfg)
                            compliance_engine = compliance_engines.get(camera.id)
                            if compliance_engine is None or compliance_signatures.get(camera.id) != signature:
                                compliance_engine = TemporalComplianceEngine(str(camera.id), policy, settings.app_timezone)
                                compliance_engines[camera.id] = compliance_engine
                                compliance_signatures[camera.id] = signature
                            rules_payload = _rule_payloads(db, zones)
                            now = datetime.now(timezone.utc)
                            # Recupera eventos OPEN tras reinicios para que puedan actualizarse o cerrarse,
                            # sin crear duplicados por pérdida del estado efímero del worker.
                            open_events = list(db.scalars(select(SafetyDetectionEvent).where(SafetyDetectionEvent.camera_id == camera.id, SafetyDetectionEvent.status == 'OPEN')))
                            for open_event in open_events:
                                compliance_engine.recover_event(open_event.dedupe_key, str(open_event.id), open_event.last_seen_at)
                                # Bloque 6: backfill de evidencia para eventos OPEN heredados de v0.6.x.
                                if (open_event.evidence_status or 'PENDING') == 'PENDING' and int(open_event.evidence_count or 0) == 0 and len(buf) >= 2:
                                    try:
                                        capture_event_evidence(db, open_event, evidence_jpg, overlay_evidence, list(buf), captured_at, float(cfg.inference_fps or 1.0))
                                    except Exception as evidence_exc:
                                        open_event.evidence_status='ERROR'; open_event.evidence_error=str(evidence_exc)[:500]
                            compliance_result = compliance_engine.evaluate(items, rules_payload, now)
                            model_snapshot = {
                                'person_model': model.code, 'person_model_version': model.version, 'person_backend': model.backend,
                                'ppe_model': ppe_model.code if ppe_model else None,
                                'ppe_model_version': ppe_model.version if ppe_model else None,
                                'ppe_backend': ppe_model.backend if ppe_model else None,
                            'compliance_enabled': bool(cfg.compliance_enabled),
                            'compliance_policy': _compliance_policy(cfg),
                                'engine_version': '0.7.0',
                            }
                            for action in compliance_result['actions']:
                                action['now'] = now
                                if action['type'] == 'OPEN':
                                    existed_before = get_open_event(db, action['key'])
                                    event, cooldown_until = open_or_get_event(db, camera, action, model_snapshot, policy['cooldown_seconds'], now)
                                    if event:
                                        compliance_engine.bind_event(action['key'], str(event.id))
                                        if existed_before is None:
                                            try:
                                                capture_event_evidence(db, event, evidence_jpg, overlay_evidence, list(buf), captured_at, float(cfg.inference_fps or 1.0))
                                            except Exception as evidence_exc:
                                                event.evidence_status='ERROR'; event.evidence_error=str(evidence_exc)[:500]
                                    else:
                                        compliance_engine.bind_event(action['key'], None, cooldown_until)
                                elif action['type'] == 'UPDATE':
                                    event = get_open_event(db, action['key'])
                                    if event:
                                        update_event(event, action, now)
                                        compliance_engine.bind_event(action['key'], str(event.id))
                                elif action['type'] == 'CLOSE':
                                    event = get_open_event(db, action['key'])
                                    if event:
                                        close_event(event, now, action.get('reason') or 'CONDITION_CLEARED')
                                    compliance_engine.mark_closed(action['key'], now)
                            # Historial compacto: transición de estado + máximo una muestra/segundo por clave.
                            for sample in compliance_result['samples']:
                                st = compliance_engine.states.get(sample['key'])
                                eid = st.event_id if st and st.event_id not in {None, 'PENDING', 'CLOSING'} else None
                                persist_evaluation(db, camera, sample, eid, now)
                            db.commit()
                            for item in items:
                                item['compliance'] = compliance_result['tracks'].get(item['track_id'], [])
                        else:
                            for item in items:
                                item['compliance'] = []

                        inference_ms = (time.perf_counter() - started) * 1000
                        false_rejections = (
                            int(filter_stats['rejected'])
                            + int(nms_rejections)
                            + int(tracker.last_candidate_rejections)
                        )
                        result = {
                            'camera_id': str(camera.id),
                            'captured_at': captured_at,
                            'inference_at': datetime.now(timezone.utc).isoformat(),
                            'model': model.code,
                            'model_version': model.version,
                            'backend': model.backend,
                            'hardening_version': '0.4.1',
                            'ppe_enabled': bool(cfg.ppe_enabled),
                            'ppe_model': ppe_model.code if ppe_model else None,
                            'ppe_model_version': ppe_model.version if ppe_model else None,
                            'ppe_backend': ppe_model.backend if ppe_model else None,
                            'shadow_model': shadow_model.code if shadow_model else None,
                            'shadow_model_version': shadow_model.version if shadow_model else None,
                            'shadow_error': shadow_error,
                            'overlay_source': 'SHADOW' if shadow_detector else 'BASELINE',
                            'shadow_samples_frame': shadow_frame.get('samples',0),
                            'shadow_agreement_frame': round(shadow_frame.get('agreements',0)/max(shadow_frame.get('samples',0),1),4) if shadow_frame.get('samples',0) else None,
                            'raw_detections': len(raw_detections),
                            'filtered_detections': len(filtered_detections),
                            'candidate_tracks': len(candidate_tracks),
                            'confirmed_persons': len(confirmed_tracks),
                            'persons': len(confirmed_tracks),
                            'active_tracks': len(confirmed_tracks),
                            'false_candidate_rejections': false_rejections,
                            'rejection_breakdown': {
                                **filter_stats['reasons'],
                                'nms': int(nms_rejections),
                                'expired_candidates': int(tracker.last_candidate_rejections),
                            },
                            'compliance_summary': {
                                'non_compliant': sum(1 for values in compliance_result.get('tracks', {}).values() for x in values if x.get('compliance_status') == 'NON_COMPLIANT'),
                                'unknown': sum(1 for values in compliance_result.get('tracks', {}).values() for x in values if x.get('compliance_status') == 'UNKNOWN'),
                                'compliant': sum(1 for values in compliance_result.get('tracks', {}).values() for x in values if x.get('compliance_status') == 'COMPLIANT'),
                                'no_aplica': sum(1 for values in compliance_result.get('tracks', {}).values() for x in values if x.get('compliance_status') == 'NO_APLICA'),
                                'actions': [a.get('type') for a in compliance_result.get('actions', [])],
                            },
                            'tracks': items,
                            'inference_ms': round(inference_ms, 2),
                            'inference_fps_target': cfg.inference_fps,
                            'frame_width': frame_w,
                            'frame_height': frame_h,
                            'status': 'RUNNING',
                        }
                        overlay = overlay_evidence if overlay_evidence is not None else render_overlay(frame, all_tracks, zones)
                        publish_vision(redis, camera.id, result, overlay)
                    except Exception as exc:
                        publish_vision(
                            redis,
                            camera.id,
                            {
                                'camera_id': str(camera.id),
                                'persons': 0,
                                'confirmed_persons': 0,
                                'active_tracks': 0,
                                'raw_detections': 0,
                                'filtered_detections': 0,
                                'candidate_tracks': 0,
                                'false_candidate_rejections': 0,
                                'tracks': [],
                                'status': 'ERROR',
                                'error': str(exc)[:300],
                                'inference_at': datetime.now(timezone.utc).isoformat(),
                            },
                            None,
                        )
        except Exception:
            # PostgreSQL/Redis transient failures must not kill the worker.
            time.sleep(1.0)
        time.sleep(0.05)


if __name__ == '__main__':
    main()
