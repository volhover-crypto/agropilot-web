# backend/meteo/provider.py -- §34: Open-Meteo (без ключа/лимитов)
#
# Почасовой прогноз до 5 дней: температура, осадки, влажность, ветер.
# Агрегаты по горизонту от текущего часа (Europe/Moscow — рабочее время системы).

import json
import urllib.request
from datetime import datetime, timedelta, timezone

_API = "https://api.open-meteo.com/v1/forecast"
_MSK = timezone(timedelta(hours=3))


class ProviderError(Exception):
    pass


def fetch_hourly(lat: float, lon: float, forecast_days: int = 5) -> dict:
    """Сырой почасовой прогноз (timezone=Europe/Moscow)."""
    url = (f"{_API}?latitude={lat}&longitude={lon}"
           f"&hourly=temperature_2m,precipitation,relative_humidity_2m,wind_speed_10m"
           f"&timezone=Europe%2FMoscow&forecast_days={forecast_days}")
    try:
        with urllib.request.urlopen(url, timeout=30) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception as e:
        raise ProviderError(f"Open-Meteo недоступен: {e}") from e


def aggregate(raw: dict, horizon_h: int) -> dict:
    """Агрегаты по ближайшим horizon_h часам от текущего момента (МСК)."""
    hh = raw.get("hourly") or {}
    times = hh.get("time") or []
    temp = hh.get("temperature_2m") or []
    prec = hh.get("precipitation") or []
    hum = hh.get("relative_humidity_2m") or []
    wind = hh.get("wind_speed_10m") or []
    if not times:
        raise ProviderError("Open-Meteo вернул пустой прогноз")
    now_msk = datetime.now(_MSK).replace(minute=0, second=0, microsecond=0)
    i0 = 0
    for i, t in enumerate(times):
        if datetime.fromisoformat(t).replace(tzinfo=_MSK) >= now_msk:
            i0 = i
            break
    i1 = min(i0 + max(horizon_h, 1), len(times))

    def _vals(series):
        return [v for v in (series[i0:i1] if series else []) if v is not None]

    tv, pv, hv, wv = _vals(temp), _vals(prec), _vals(hum), _vals(wind)
    return {
        "temp_min": round(min(tv), 1) if tv else None,
        "temp_max": round(max(tv), 1) if tv else None,
        "precip_sum": round(sum(pv), 1) if pv else 0.0,
        "humidity_avg": round(sum(hv) / len(hv), 1) if hv else None,
        "wind_max": round(max(wv), 1) if wv else None,
        "hours_counted": i1 - i0,
        "since_msk": times[i0] if i0 < len(times) else None,
    }
