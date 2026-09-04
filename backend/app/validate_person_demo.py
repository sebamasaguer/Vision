"""Compatibility wrapper: positive PERSON QA using v0.4.1 hardening + tracking."""
from app.validate_person_hardening import evaluate


def main() -> int:
    try:
        result = evaluate('/demo/qa_hardening_person.mp4', True)
    except Exception as exc:
        print(f'[FAIL] {exc}')
        return 1
    print('[PERSON-DEMO] samples={samples} raw={raw_total} filtered={filtered_total} confirmed_samples={confirmed_samples} max_confirmed={max_confirmed}'.format(**result))
    print('[PASS] Detector PERSON positivo + tracking confirmado con clip QA incluido.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
