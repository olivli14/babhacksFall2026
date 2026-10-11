# AI-generated with Claude (Anthropic). Review before relying on it.
"""Daily-high forecast probabilities for Gemini weather stations.

prob_above(location, threshold_f, date) -> P(reported daily high >= threshold_f), 0 to 1.

Model:
  1. Forecast: Open-Meteo ensembles at the station (GFS 31 members + ECMWF 51
     members). The day's high ~ Normal(ensemble mean, sd), where
     sd = sqrt(ensemble spread^2 + MODEL_ERROR_SD_F^2). The extra term covers
     gridded-model vs. station error; raw ensembles are overconfident.
  2. Fallback when the date is outside the forecast window or the API is down:
     climatology, i.e. the same calendar window (+/- 7 days) over the last
     CLIMO_YEARS years at the station.
NWS reports whole degrees, so "high >= 70" means the true high >= 69.5.

location: Gemini code ("LA", "NYC") or city name ("Los Angeles").
date: "YYYY-MM-DD", the station's local date.
"""
import math
import statistics
import threading
import time
from datetime import date as Date, timedelta

import requests

import onboard

ENSEMBLE_URL = "https://ensemble-api.open-meteo.com/v1/ensemble"
ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
MODELS = "gfs_seamless,ecmwf_ifs025"
MODEL_ERROR_SD_F = 2.0   # added in quadrature to the ensemble spread
MIN_SD_F = 1.0
CACHE_TTL_S = 30 * 60    # forecasts update a few times a day
CLIMO_YEARS = 5
CLIMO_WINDOW_DAYS = 7

_cache: dict = {}        # station code -> (fetched_at, {date: [members]})
_lock = threading.Lock()
_stations: dict | None = None
CITY_ALIASES = {"new york": "NYC", "new york city": "NYC", "washington": "DCA", "dc": "DCA"}


def station(location: str) -> dict:
    """Resolve a Gemini code or city name to {city, code, lat, lon}."""
    global _stations
    if _stations is None:
        _stations = {s["code"]: s for s in onboard.gemini_stations() if s.get("code")}
    key = location.strip()
    if key.upper() in _stations:
        return _stations[key.upper()]
    code = CITY_ALIASES.get(key.lower())
    if code in _stations:
        return _stations[code]
    for s in _stations.values():
        if s["city"].lower() == key.lower():
            return s
    raise LookupError(f"unknown Gemini weather location: {location}")


def _ensemble(st: dict) -> dict:
    """{date: [member highs °F]} for the next ~7 days, cached in memory for CACHE_TTL_S."""
    with _lock:
        hit = _cache.get(st["code"])
        if hit and time.time() - hit[0] < CACHE_TTL_S:
            return hit[1]
    try:
        r = requests.get(ENSEMBLE_URL, timeout=20, params={
            "latitude": st["lat"], "longitude": st["lon"], "daily": "temperature_2m_max",
            "temperature_unit": "fahrenheit", "models": MODELS, "timezone": "auto",
            "forecast_days": 7,
        })
        r.raise_for_status()
        daily = r.json().get("daily", {})
    except requests.RequestException as e:
        onboard.log(f"warn: ensemble fetch failed for {st['code']}: {e}")
        return hit[1] if hit else {}  # stale beats nothing
    keys = [k for k in daily if k.startswith("temperature_2m_max")]
    by_date = {d: [daily[k][i] for k in keys if daily[k][i] is not None]
               for i, d in enumerate(daily.get("time", []))}
    by_date = {d: m for d, m in by_date.items() if m}
    with _lock:
        _cache[st["code"]] = (time.time(), by_date)
    return by_date


def _climatology(st: dict, day: Date) -> tuple[float, float]:
    """Mean and sd of the daily high in a +/- window around day's calendar date."""
    end = Date.today() - timedelta(days=3)
    data = onboard.http_get_json(ARCHIVE_URL, {
        "latitude": st["lat"], "longitude": st["lon"], "daily": "temperature_2m_max",
        "temperature_unit": "fahrenheit", "timezone": "auto",
        "start_date": Date(end.year - CLIMO_YEARS, 1, 1).isoformat(), "end_date": end.isoformat(),
    })
    d = data.get("daily", {})
    vals = []
    for t, v in zip(d.get("time", []), d.get("temperature_2m_max", [])):
        if v is None:
            continue
        past = Date.fromisoformat(t)
        try:
            anchor = day.replace(year=past.year)
        except ValueError:  # Feb 29
            anchor = day.replace(year=past.year, day=28)
        if abs((past - anchor).days) <= CLIMO_WINDOW_DAYS:
            vals.append(v)
    if len(vals) < 10:
        raise LookupError(f"not enough history for {st['code']} around {day}")
    return statistics.mean(vals), statistics.pstdev(vals)


def distribution(location: str, date: str) -> dict:
    """Normal approximation of the day's high: {mean_f, sd_f, source, members}."""
    st = station(location)
    members = _ensemble(st).get(date)
    if members and len(members) >= 5:
        spread = statistics.pstdev(members)
        sd = max(MIN_SD_F, math.sqrt(spread ** 2 + MODEL_ERROR_SD_F ** 2))
        return {"code": st["code"], "mean_f": statistics.mean(members), "sd_f": sd,
                "source": "ensemble", "members": len(members)}
    mean, sd = _climatology(st, Date.fromisoformat(date))
    return {"code": st["code"], "mean_f": mean, "sd_f": max(MIN_SD_F, sd),
            "source": "climatology", "members": 0}


def prob_above(location: str, threshold_f: float, date: str) -> float:
    """P(NWS-reported daily high >= threshold_f) at the location's station on date."""
    d = distribution(location, date)
    cutoff = math.ceil(threshold_f) - 0.5  # whole-degree reporting
    z = (cutoff - d["mean_f"]) / d["sd_f"]
    return 0.5 * math.erfc(z / math.sqrt(2))  # 1 - normal CDF
