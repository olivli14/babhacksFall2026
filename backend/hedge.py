#!/usr/bin/env python3
# AI-generated with Claude (Anthropic). Review before relying on it.
"""Net a city's weather exposures and size the leftover hedge on Gemini.

Usage: python hedge.py [--city "Los Angeles"] [--date 2026-10-12] [--refresh]

Model: each business's daily profit is linear in the day's high temp T.
  heat_hurt: pnl = -dollars_per_degree * (T - baseline)
  cold_hurt: pnl = +dollars_per_degree * (T - baseline)
The pool's P&L is the sum. Opposite sides cancel; what's left is the pool's
net $/°F. We hedge the downside versus the expected P&L: on each Gemini
temperature bucket where the pool does worse than expected, buy enough YES
contracts ($1 payout each) to cover the shortfall.
"""
import warnings

warnings.filterwarnings("ignore", message="urllib3 v2 only supports OpenSSL")

import argparse
import json
import re
import statistics
import sys
import time
from datetime import date, datetime, timedelta, timezone

import requests

import db
import forecast
import onboard
from onboard import DATA_FILE, GEMINI_EVENTS_URL, OnboardError, cached, http_get_json, log

# ---------------------------------------------------------------------------
# Config: tweak these
# ---------------------------------------------------------------------------

COVERAGE = 1.0          # share of each bucket's loss to hedge (1.0 = full)
MIN_PROB = 0.01         # floor on model probabilities so no bucket is "free"
ENSEMBLE_MODEL = "gfs_seamless"
BACKTEST_DAYS = 365
HISTORY_YEARS = 5       # pulled and stored for the dashboard's year-over-year chart

ENSEMBLE_URL = "https://ensemble-api.open-meteo.com/v1/ensemble"
ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
PLANS_FILE = DATA_FILE.parent / "hedge_plans.json"
LIVE_EVENTS_KEY = "gemini:events:live"


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------

def live_gemini_events():
    """Gemini events with fresh prices; falls back to cache if offline."""
    params = {"status": "active", "category": "Weather", "limit": 200}
    try:
        r = requests.get(GEMINI_EVENTS_URL, params=params, timeout=15)
        r.raise_for_status()
        data = r.json()
    except requests.RequestException as e:
        log(f"warn: live Gemini fetch failed ({e}); using cached prices")
        return cached(LIVE_EVENTS_KEY, lambda: http_get_json(GEMINI_EVENTS_URL, params))
    # Overwrite the offline copy with these fresh prices.
    saved, onboard.REFRESH = onboard.REFRESH, True
    try:
        cached(LIVE_EVENTS_KEY, lambda: data)
    finally:
        onboard.REFRESH = saved
    return data


def parse_bucket(label):
    """'72°F to 73°F' -> (72, 73); '69°F or below' -> (None, 69); '78°F or above' -> (78, None)."""
    nums = [int(n) for n in re.findall(r"-?\d+", label)]
    if "below" in label:
        return None, nums[0]
    if "above" in label:
        return nums[0], None
    return nums[0], nums[1]


def market_for(city, day=None):
    """Return (date, [bucket dicts]) for the city's Gemini event on day (default: latest open)."""
    events = []
    for ev in live_gemini_events().get("data", []):
        m = re.search(r"Highest temperature in (.+?) on (.+?)\?", ev.get("title", ""))
        if not m or m.group(1) != city:
            continue
        ev_date = datetime.strptime(m.group(2), "%B %d, %Y").date()
        events.append((ev_date, ev))
    if not events:
        raise OnboardError(f"no active Gemini weather event for {city}")
    if day:
        events = [e for e in events if e[0] == day]
        if not events:
            raise OnboardError(f"no active Gemini event for {city} on {day}")
    ev_date, ev = max(events, key=lambda e: e[0])

    buckets = []
    for c in ev.get("contracts", []):
        lo, hi = parse_bucket(c.get("label", ""))
        ask = (c.get("prices") or {}).get("buy", {}).get("yes")
        buckets.append({
            "label": c["label"], "instrument": c.get("instrumentSymbol"),
            "lo": lo, "hi": hi, "ask": float(ask) if ask else None,
        })
    buckets.sort(key=lambda b: b["lo"] if b["lo"] is not None else -999)
    return ev_date, buckets


def ensemble_highs(lat, lon, day):
    """Ensemble member forecasts (°F) of the daily high on day."""
    data = http_get_json(ENSEMBLE_URL, {
        "latitude": lat, "longitude": lon, "daily": "temperature_2m_max",
        "temperature_unit": "fahrenheit", "models": ENSEMBLE_MODEL,
        "timezone": "auto", "forecast_days": 7, "asof": date.today().isoformat(),
    })
    daily = data.get("daily", {})
    if day.isoformat() not in daily.get("time", []):
        return []
    i = daily["time"].index(day.isoformat())
    return [daily[k][i] for k in daily if k != "time" and daily[k][i] is not None]


def history_highs(lat, lon, years=HISTORY_YEARS):
    end = date.today() - timedelta(days=3)  # archive lags a couple of days
    start = date(end.year - years + 1, 1, 1)
    data = http_get_json(ARCHIVE_URL, {
        "latitude": lat, "longitude": lon, "daily": "temperature_2m_max",
        "temperature_unit": "fahrenheit", "timezone": "auto",
        "start_date": start.isoformat(), "end_date": end.isoformat(),
    })
    d = data.get("daily", {})
    return [(t, v) for t, v in zip(d.get("time", []), d.get("temperature_2m_max", [])) if v is not None]


# ---------------------------------------------------------------------------
# Math
# ---------------------------------------------------------------------------

def pnl(biz, temp):
    sign = -1 if biz["side"] == "heat_hurt" else 1
    return sign * biz["dollars_per_degree"] * (temp - biz["baseline_temp_f"])


def in_bucket(b, temp):
    t = round(temp)  # NWS reports whole degrees
    return (b["lo"] is None or t >= b["lo"]) and (b["hi"] is None or t <= b["hi"])


def bucket_temp(b, members):
    """Representative temp: mean of members in the bucket, else its midpoint/edge."""
    inside = [m for m in members if in_bucket(b, m)]
    if inside:
        return statistics.mean(inside)
    if b["lo"] is None:
        return b["hi"] - 1
    if b["hi"] is None:
        return b["lo"] + 1
    return (b["lo"] + b["hi"]) / 2


def shortfalls(pnls, probs):
    """Per-bucket shortfall versus the probability-weighted expected P&L."""
    expected = sum(p * q for p, q in zip(pnls, probs))
    return [max(0.0, expected - p) for p in pnls]


def hedge_cost(pnls, buckets):
    """Contracts and cost to cover each bucket's shortfall versus expected P&L."""
    gaps = shortfalls(pnls, [b["model_prob"] for b in buckets])
    contracts = [round(COVERAGE * g) for g in gaps]
    cost = sum(n * b["price"] for n, b in zip(contracts, buckets))
    return contracts, round(cost, 2)


def load_businesses(city):
    """Hedgeable businesses in a city, from Supabase; local JSON if Supabase is unreachable."""
    try:
        rows = db.select("businesses", gemini_city=city)
    except Exception as e:
        log(f"warn: Supabase read failed ({e}); using {DATA_FILE.name}")
        rows = [b for b in (json.loads(DATA_FILE.read_text()) if DATA_FILE.exists() else [])
                if b.get("gemini_city") == city]
    return [b for b in rows if b.get("side") in ("heat_hurt", "cold_hurt")
            and b.get("dollars_per_degree") and b.get("baseline_temp_f") is not None]


def store_weather(city, station, hist, ev_date, members):
    """Save history and the forecast to the weather_daily table."""
    base = {"city": city, "lat": station["lat"], "lon": station["lon"]}
    rows = [{**base, "date": t, "source": "archive", "high_f": v, "members": None} for t, v in hist]
    if members:
        rows.append({**base, "date": ev_date.isoformat(), "source": "forecast",
                     "high_f": round(statistics.mean(members), 2), "members": members})
    try:
        db.upsert("weather_daily", rows, on_conflict="city,date,source")
    except Exception as e:
        log(f"warn: Supabase write to weather_daily failed: {e}")


def bucket_prob(code, b, day):
    """P(lo <= reported high <= hi) from forecast.prob_above (same model as the market maker)."""
    p_lo = 1.0 if b["lo"] is None else forecast.prob_above(code, b["lo"], day)
    p_hi = 0.0 if b["hi"] is None else forecast.prob_above(code, b["hi"] + 1, day)
    return max(0.0, p_lo - p_hi)


def plan(city, day=None, store=True):
    businesses = load_businesses(city)
    if not businesses:
        raise OnboardError(f"no classified businesses mapped to {city}")

    station = next(s for s in onboard.gemini_stations() if s["city"] == city)
    ev_date, buckets = market_for(city, day)
    members = forecast._ensemble(station).get(ev_date.isoformat(), [])
    hist = history_highs(station["lat"], station["lon"])
    if store:
        store_weather(city, station, hist, ev_date, members)

    # Probability per bucket from the shared forecast model, floored, renormalized.
    raw = [max(MIN_PROB, bucket_prob(station["code"], b, ev_date.isoformat())) for b in buckets]
    total = sum(raw)
    for b, p in zip(buckets, raw):
        b["model_prob"] = round(p / total, 3)
        b["price"] = b["ask"] if b["ask"] is not None else b["model_prob"]
        b["price_source"] = "market" if b["ask"] is not None else "model (no quote)"
        b["temp_f"] = round(bucket_temp(b, members), 1)

    # Per-business and pooled P&L per bucket.
    per_biz = {biz["domain"]: [pnl(biz, b["temp_f"]) for b in buckets] for biz in businesses}
    pooled = [sum(col) for col in zip(*per_biz.values())]

    pooled_contracts, pooled_cost = hedge_cost(pooled, buckets)
    standalone = {d: hedge_cost(losses, buckets)[1] for d, losses in per_biz.items()}
    standalone_cost = sum(standalone.values())

    probs = [b["model_prob"] for b in buckets]
    expected_pnl = sum(p * q for p, q in zip(pooled, probs))
    exp_shortfall = sum(q * g for q, g in zip(probs, shortfalls(pooled, probs)))
    rows = []
    for b, p, n in zip(buckets, pooled, pooled_contracts):
        rows.append({
            "bucket": b["label"], "instrument": b["instrument"], "temp_f": b["temp_f"],
            "model_prob": b["model_prob"], "ask": b["ask"], "price": b["price"],
            "price_source": b["price_source"],
            "edge": round(b["model_prob"] - b["price"], 3),  # >0: market cheaper than our forecast
            "pool_pnl": round(p, 2),
            "contracts": n, "cost": round(n * b["price"], 2),
        })

    net_slope = sum((-1 if x["side"] == "heat_hurt" else 1) * x["dollars_per_degree"] for x in businesses)
    return {
        "city": city,
        "date": ev_date.isoformat(),
        "station": {"lat": station["lat"], "lon": station["lon"]},
        "businesses": [{"domain": x["domain"], "side": x["side"], "baseline_temp_f": x["baseline_temp_f"],
                        "dollars_per_degree": x["dollars_per_degree"]} for x in businesses],
        "net_dollars_per_degree": round(net_slope, 2),
        "forecast": {**{k: (round(v, 2) if isinstance(v, float) else v)
                        for k, v in forecast.distribution(station["code"], ev_date.isoformat()).items()},
                     "mean_high_f": round(forecast.distribution(station["code"], ev_date.isoformat())["mean_f"], 1)},
        "hedge_cost_by_business": standalone,
        "buckets": rows,
        "expected_pool_pnl": round(expected_pnl, 2),
        "expected_shortfall": round(exp_shortfall, 2),
        "hedge_cost_pooled": pooled_cost,
        "hedge_cost_standalone": round(standalone_cost, 2),
        "netting_savings": round(standalone_cost - pooled_cost, 2),
        "backtest": backtest(businesses, hist[-BACKTEST_DAYS:]),
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def backtest(businesses, hist):
    """Replay the last year: unhedged vs hedged daily pool P&L.

    The hedge pays each day's shortfall versus the year's average P&L and is
    bought at fair price (its average payout). Real hedges add bucket rounding
    and spreads.
    """
    if not hist:
        return None
    temps = [t for _, t in hist]

    def premium_and_payouts(pnls):
        mean = statistics.mean(pnls)
        payouts = [max(0.0, mean - p) for p in pnls]
        return statistics.mean(payouts), payouts

    pool = [sum(pnl(b, t) for b in businesses) for t in temps]
    premium, payouts = premium_and_payouts(pool)
    hedged = [p + pay - premium for p, pay in zip(pool, payouts)]
    standalone_premium = sum(premium_and_payouts([pnl(b, t) for t in temps])[0] for b in businesses)
    worst = min(range(len(pool)), key=pool.__getitem__)
    mean_pool = statistics.mean(pool)
    return {
        "days": len(hist), "from": hist[0][0], "to": hist[-1][0],
        "avg_high_f": round(statistics.mean(t for _, t in hist), 1),
        "below_average_days": sum(p < mean_pool for p in pool),
        "worst_day": {"date": hist[worst][0], "high_f": hist[worst][1],
                      "pnl_unhedged": round(pool[worst], 2), "pnl_hedged": round(hedged[worst], 2)},
        "daily_stdev_unhedged": round(statistics.pstdev(pool), 2),
        "daily_stdev_hedged": round(statistics.pstdev(hedged), 2),
        "avg_daily_premium_pooled": round(premium, 2),
        "avg_daily_premium_standalone": round(standalone_premium, 2),
    }


def save(result):
    try:
        db.upsert("hedge_plans", [{"city": result["city"], "date": result["date"], "plan": result}],
                  on_conflict="city,date")
    except Exception as e:
        log(f"warn: Supabase write to hedge_plans failed: {e}")
    rows = json.loads(PLANS_FILE.read_text()) if PLANS_FILE.exists() else []
    rows = [r for r in rows if (r["city"], r["date"]) != (result["city"], result["date"])] + [result]
    rows.sort(key=lambda r: (r["city"], r["date"]))
    PLANS_FILE.write_text(json.dumps(rows, indent=2) + "\n")


def main():
    ap = argparse.ArgumentParser(description="Net a city's exposures and size the Gemini hedge")
    ap.add_argument("--city", default="Los Angeles", help="Gemini city name, as in the market title")
    ap.add_argument("--date", type=date.fromisoformat, help="event date YYYY-MM-DD (default: latest open)")
    ap.add_argument("--refresh", action="store_true", help="bypass cache/ for forecasts and history")
    args = ap.parse_args()
    onboard.REFRESH = args.refresh

    start = time.time()
    try:
        result = plan(args.city, args.date)
        save(result)
    except OnboardError as e:
        log(f"error: {e}")
        return 2
    except Exception as e:
        log(f"error: {type(e).__name__}: {e}")
        return 1
    print(json.dumps(result, indent=2))
    log(f"done in {time.time() - start:.2f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
