from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

SEVERITY_RANK = {"INFO": 0, "ADVERTENCIA": 1, "ALTA": 2, "CRITICA": 3}
EVALUABLE = {"OK", "NO_DETECTADO"}
UNKNOWN = {"INCIERTO", "NO_VISIBLE"}


def schedule_applies(rule: dict, now: datetime, timezone_name: str = "America/Argentina/Salta") -> bool:
    start = rule.get("schedule_start")
    end = rule.get("schedule_end")
    if not start and not end:
        return True
    local = now.astimezone(ZoneInfo(timezone_name))
    current = local.strftime("%H:%M")
    if start and end:
        if start <= end:
            return start <= current <= end
        return current >= start or current <= end  # rango nocturno
    if start:
        return current >= start
    return current <= end


def compliance_status(observed_status: str, requirement: str = "REQUIRED") -> str:
    if requirement != "REQUIRED" or observed_status == "NO_APLICA":
        return "NO_APLICA"
    if observed_status == "OK":
        return "COMPLIANT"
    if observed_status == "NO_DETECTADO":
        return "NON_COMPLIANT"
    if observed_status in UNKNOWN:
        return "UNKNOWN"
    return "NO_APLICA"


def effective_rules_for_track(track: dict, rules: list[dict], now: datetime, timezone_name: str) -> list[dict]:
    zone_ids = {str(z.get("id")) for z in (track.get("zones") or []) if z.get("id")}
    grouped: dict[str, dict] = {}
    for rule in rules:
        if str(rule.get("zone_id")) not in zone_ids:
            continue
        if not rule.get("active", True) or not schedule_applies(rule, now, timezone_name):
            continue
        code = str(rule.get("ppe_code"))
        previous = grouped.get(code)
        if previous is None:
            grouped[code] = rule
            continue
        # REQUIRED siempre gana a OPTIONAL/NOT_APPLICABLE; luego mayor severidad.
        old_req = previous.get("requirement") == "REQUIRED"
        new_req = rule.get("requirement") == "REQUIRED"
        if new_req and not old_req:
            grouped[code] = rule
        elif new_req == old_req and SEVERITY_RANK.get(rule.get("severity", "INFO"), 0) > SEVERITY_RANK.get(previous.get("severity", "INFO"), 0):
            grouped[code] = rule
    return list(grouped.values())


@dataclass
class TemporalState:
    history: deque = field(default_factory=deque)
    event_id: str | None = None
    cooldown_until: datetime | None = None
    clear_since: datetime | None = None
    last_seen: datetime | None = None
    last_sample_at: datetime | None = None
    last_sample_status: str | None = None
    last_rule: dict | None = None


class TemporalComplianceEngine:
    """Motor temporal puro. No conoce SQLAlchemy ni Redis.

    Dedupe: camera + track + PPE. Si un track cae en zonas superpuestas, la regla
    REQUIRED de mayor severidad es la que representa la condición.
    """

    def __init__(self, camera_id: str, policy: dict, timezone_name: str = "America/Argentina/Salta"):
        self.camera_id = str(camera_id)
        self.policy = dict(policy)
        self.timezone_name = timezone_name
        self.states: dict[str, TemporalState] = {}

    def _key(self, track_id: str, ppe_code: str) -> str:
        return f"{self.camera_id}:{track_id}:{ppe_code}"

    def _stats(self, state: TemporalState, now: datetime):
        window = float(self.policy.get("window_seconds", 4.0))
        cutoff = now - timedelta(seconds=window)
        while state.history and state.history[0][0] < cutoff:
            state.history.popleft()
        evals = [(ts, st) for ts, st in state.history if st in EVALUABLE]
        missing_window = [(ts, st) for ts, st in evals if st == "NO_DETECTADO"]
        consensus = len(missing_window) / len(evals) if evals else 0.0
        # Persistencia estricta: OK/INCIERTO/NO_VISIBLE interrumpen la secuencia.
        # Así una oclusión breve no "suma segundos" a una falta de EPP.
        trailing_missing = []
        for ts, st in reversed(state.history):
            if st != "NO_DETECTADO":
                break
            trailing_missing.append((ts, st))
        trailing_missing.reverse()
        span = (trailing_missing[-1][0] - trailing_missing[0][0]).total_seconds() if len(trailing_missing) >= 2 else 0.0
        return {
            "missing_observations": len(trailing_missing),
            "evaluable_observations": len(evals),
            "consensus_ratio": round(consensus, 4),
            "missing_span_seconds": round(span, 4),
        }

    def bind_event(self, key: str, event_id: str | None, cooldown_until: datetime | None = None):
        state = self.states.get(key)
        if not state:
            return
        state.event_id = event_id
        if cooldown_until:
            state.cooldown_until = cooldown_until

    def recover_event(self, key: str, event_id: str, last_seen: datetime | None = None):
        state = self.states.setdefault(key, TemporalState())
        if not state.event_id or state.event_id in {"PENDING", "CLOSING"}:
            state.event_id = str(event_id)
        if last_seen and (state.last_seen is None or last_seen > state.last_seen):
            state.last_seen = last_seen

    def mark_closed(self, key: str, now: datetime):
        state = self.states.get(key)
        if not state:
            return
        state.event_id = None
        state.clear_since = None
        state.history.clear()
        state.cooldown_until = now + timedelta(seconds=float(self.policy.get("cooldown_seconds", 15.0)))

    def _sample_due(self, state: TemporalState, now: datetime, status: str) -> bool:
        if state.last_sample_status != status:
            state.last_sample_status = status
            state.last_sample_at = now
            return True
        if state.last_sample_at is None or (now - state.last_sample_at).total_seconds() >= 1.0:
            state.last_sample_at = now
            return True
        return False

    def evaluate(self, tracks: list[dict], rules: list[dict], now: datetime | None = None):
        now = now or datetime.now(timezone.utc)
        visible_track_ids = {str(t.get("track_id")) for t in tracks}
        current_keys: set[str] = set()
        actions: list[dict] = []
        samples: list[dict] = []
        track_compliance: dict[str, list[dict]] = {}

        for track in tracks:
            track_id = str(track.get("track_id"))
            track_compliance[track_id] = []
            effective = effective_rules_for_track(track, rules, now, self.timezone_name)
            ppe = track.get("ppe") or {}
            for rule in effective:
                code = str(rule.get("ppe_code"))
                requirement = str(rule.get("requirement") or "REQUIRED")
                ppe_item = (ppe.get(code) or {}) if code in ppe else {}
                confidence = ppe_item.get("confidence") if ppe_item else None
                base_observed = ppe_item.get("status") if ppe_item else "NO_APLICA"
                base_observed = base_observed or "NO_APLICA"
                # La regla puede exigir un confidence mayor que el catálogo. Una presencia
                # por debajo de ese umbral es INCIERTA, nunca un incumplimiento automático.
                threshold = rule.get("min_confidence")
                if base_observed in {"NO_VISIBLE", "INCIERTO", "NO_APLICA"}:
                    observed = base_observed
                elif ppe_item.get("detected") is True and threshold is not None and confidence is not None and float(confidence) < float(threshold):
                    observed = "INCIERTO"
                elif ppe_item.get("detected") is True:
                    observed = "OK"
                elif ppe_item:
                    observed = "NO_DETECTADO"
                else:
                    observed = "NO_APLICA"
                status = compliance_status(observed, requirement)
                key = self._key(track_id, code)
                current_keys.add(key)
                state = self.states.setdefault(key, TemporalState())
                state.last_seen = now
                state.last_rule = rule
                state.history.append((now, observed))
                stats = self._stats(state, now)

                item = {
                    "key": key,
                    "ppe_code": code,
                    "ppe_name": rule.get("ppe_name") or code,
                    "zone_id": str(rule.get("zone_id")) if rule.get("zone_id") else None,
                    "zone_code": rule.get("zone_code"),
                    "requirement": requirement,
                    "severity": rule.get("severity") or "ADVERTENCIA",
                    "observed_status": observed,
                    "compliance_status": status,
                    "confidence": confidence,
                    **stats,
                    "event_active": bool(state.event_id and state.event_id not in {"PENDING", "CLOSING"}),
                }
                track_compliance[track_id].append(item)

                if self._sample_due(state, now, status):
                    samples.append({**item, "track_id": track_id, "rule": rule})

                if requirement != "REQUIRED" or status in {"NO_APLICA", "UNKNOWN"}:
                    # UNKNOWN pausa; no genera ni cierra un evento por sí solo.
                    continue

                if observed == "NO_DETECTADO":
                    state.clear_since = None
                    ready = (
                        stats["missing_observations"] >= int(self.policy.get("min_missing_observations", 3))
                        and stats["missing_span_seconds"] >= float(self.policy.get("min_persistence_seconds", 2.0))
                        and stats["consensus_ratio"] >= float(self.policy.get("min_consensus_ratio", 0.70))
                    )
                    if ready:
                        if not state.event_id and (not state.cooldown_until or now >= state.cooldown_until):
                            state.event_id = "PENDING"
                            actions.append({"type": "OPEN", "key": key, "track_id": track_id, "rule": rule, "observed_status": observed, "confidence": confidence, **stats})
                        elif state.event_id and state.event_id not in {"PENDING", "CLOSING"}:
                            actions.append({"type": "UPDATE", "key": key, "event_id": state.event_id, "track_id": track_id, "rule": rule, "observed_status": observed, "confidence": confidence, **stats})
                elif observed == "OK" and state.event_id and state.event_id not in {"PENDING", "CLOSING"}:
                    if state.clear_since is None:
                        state.clear_since = now
                    elif (now - state.clear_since).total_seconds() >= float(self.policy.get("clear_grace_seconds", 1.0)):
                        event_id = state.event_id
                        state.event_id = "CLOSING"
                        actions.append({"type": "CLOSE", "key": key, "event_id": event_id, "track_id": track_id, "rule": rule, "reason": "CONDITION_CLEARED", "observed_status": observed, "confidence": confidence, **stats})

        # Estados con evento activo que ya no tienen regla aplicable o track visible.
        absence_limit = float(self.policy.get("track_absence_close_seconds", 3.0))
        clear_grace = float(self.policy.get("clear_grace_seconds", 1.0))
        for key, state in list(self.states.items()):
            if key in current_keys or not state.event_id or state.event_id in {"PENDING", "CLOSING"}:
                continue
            parts = key.split(":")
            track_id = parts[-2] if len(parts) >= 3 else ""
            delay = clear_grace if track_id in visible_track_ids else absence_limit
            if state.last_seen and (now - state.last_seen).total_seconds() >= delay:
                reason = "RULE_NO_LONGER_APPLIES" if track_id in visible_track_ids else "TRACK_ABSENT"
                event_id = state.event_id
                state.event_id = "CLOSING"
                actions.append({"type": "CLOSE", "key": key, "event_id": event_id, "track_id": track_id, "rule": state.last_rule or {}, "reason": reason, **self._stats(state, now)})

        return {"actions": actions, "samples": samples, "tracks": track_compliance}
