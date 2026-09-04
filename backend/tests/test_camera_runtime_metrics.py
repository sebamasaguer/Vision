from collections import deque

from app.services.camera_runtime import demo_pacing_delay, measured_rate_hz, valid_source_fps


def test_measured_rate_uses_publication_timestamps_not_decode_throughput():
    timestamps = deque([10.0, 10.2, 10.4, 10.6, 10.8])
    assert round(measured_rate_hz(timestamps), 3) == 5.0


def test_measured_rate_requires_two_samples():
    assert measured_rate_hz([]) == 0.0
    assert measured_rate_hz([10.0]) == 0.0


def test_demo_pacing_respects_source_timeline():
    # Third frame of a 15 FPS source belongs at t=100.2.
    delay = demo_pacing_delay(frame_index=3, source_fps=15.0, playback_started=100.0, now=100.15)
    assert round(delay, 3) == 0.05


def test_demo_pacing_never_returns_negative_sleep():
    assert demo_pacing_delay(frame_index=3, source_fps=15.0, playback_started=100.0, now=101.0) == 0.0


def test_invalid_source_fps_is_sanitized():
    assert valid_source_fps(15.0) == 15.0
    assert valid_source_fps(0.0, fallback=12.0) == 12.0
    assert valid_source_fps(999.0, fallback=12.0) == 12.0
