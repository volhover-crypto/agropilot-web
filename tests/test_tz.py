# tests/test_tz.py -- О4: дисциплина таймзон (DEFAULT_TZ, не зона хоста)

from datetime import datetime, timezone

from backend.common.tz import DEFAULT_TZ, api_dt, now_local, now_utc, parse_dt


def test_parse_naive_iso_gets_default_tz():
    dt = parse_dt("2026-09-27T09:00:00")
    assert dt.tzinfo is not None
    assert dt.utcoffset() == DEFAULT_TZ.utcoffset(dt)


def test_parse_with_offset_kept():
    dt = parse_dt("2026-09-27T09:00:00+05:00")
    assert dt.utcoffset().total_seconds() == 5 * 3600


def test_parse_datetime_naive_attached():
    dt = parse_dt(datetime(2026, 9, 27, 9, 0, 0))
    assert dt.tzinfo is DEFAULT_TZ


def test_api_dt_always_has_offset():
    s = api_dt("2026-09-27T09:00:00")
    assert "+00:00" in s
    # 09:00 МСК == 06:00 UTC
    assert s.startswith("2026-09-27T06:00:00")


def test_now_local_is_msk_and_utc_aware():
    loc, utc = now_local(), now_utc()
    assert loc.tzinfo is not None and utc.tzinfo is not None
    # МСК = UTC+3 круглый год (без DST)
    assert loc.utcoffset().total_seconds() == 3 * 3600
    assert abs((loc.astimezone(timezone.utc) - utc).total_seconds()) < 2


def test_bad_string_raises():
    try:
        parse_dt("не-дата")
        raised = False
    except ValueError:
        raised = True
    assert raised
