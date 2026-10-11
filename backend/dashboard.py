# AI-generated with Claude (Anthropic). Review before relying on it.
"""Routes for the onboarding + dashboard frontend. Mounted in api.py.

POST /api/onboard      {url, city?, annual_revenue?} -> {domain, profile}
GET  /api/businesses                                  -> [profile, ...]
GET  /api/dashboard    ?domain=&days=                 -> everything the dashboard shows

Per-business hedge math: each business is covered for days that come in below
its own average weather P&L. Its fee is its share of the pooled premium,
split in proportion to what it would pay hedging alone.
"""
import json
import statistics
from datetime import date, timedelta

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

import db
import hedge
import onboard

router = APIRouter(prefix="/api")


class OnboardBody(BaseModel):
    url: str = Field(min_length=3, max_length=300)
    city: str | None = Field(default=None, max_length=80)
    annual_revenue: float | None = Field(default=None, gt=0, le=1_000_000_000)


def _shift_year(d: date, years: int) -> date:
    """Same calendar day `years` later (Feb 29 -> Feb 28)."""
    try:
        return d.replace(year=d.year + years)
    except ValueError:
        return d.replace(year=d.year + years, day=28)


def _all_businesses() -> list[dict]:
    try:
        return db.select("businesses")
    except Exception:
        return json.loads(onboard.DATA_FILE.read_text()) if onboard.DATA_FILE.exists() else []


def _business(domain: str) -> dict:
    rows = [b for b in _all_businesses() if b.get("domain") == domain]
    if not rows:
        raise HTTPException(404, f"{domain} hasn't been onboarded")
    return max(rows, key=lambda b: b.get("onboarded_at") or "")


@router.post("/onboard")
def api_onboard(body: OnboardBody):
    try:
        profile = onboard.run(body.url.strip(), (body.city or "").strip() or None, body.annual_revenue)
    except onboard.OnboardError as e:
        raise HTTPException(400, str(e))
    return {"domain": profile["domain"], "profile": profile}


@router.get("/businesses")
def api_businesses():
    return sorted(_all_businesses(), key=lambda b: b.get("name") or b["domain"])


@router.get("/dashboard")
def api_dashboard(domain: str, days: int = Query(365, ge=7, le=730)):
    biz = _business(domain)
    out = {"business": biz, "hub": None, "forecast": None, "recommendation": None,
           "temperature_history": [], "pnl_series": [], "summary": None, "pool": []}
    city = biz.get("gemini_city")
    if not city:
        return out
    station = next((s for s in onboard.gemini_stations() if s["city"] == city), None)
    out["hub"] = {"gemini_city": city, "code": station and station.get("code"),
                  "station": "LAX" if city == "Los Angeles" else city,
                  "distance_miles": biz.get("distance_miles")}
    hedgeable = biz.get("side") in ("heat_hurt", "cold_hurt")
    if not hedgeable:
        return out

    plan = hedge.plan(city, store=False)
    pool = plan["businesses"]
    alone = plan["hedge_cost_by_business"]
    share = alone.get(domain, 0) / sum(alone.values()) if sum(alone.values()) else 0
    names = {x["domain"]: x.get("name") for x in _all_businesses()}
    out["pool"] = [{"domain": b["domain"], "side": b["side"], "name": names.get(b["domain"]) or b["domain"],
                    "dollars_per_degree": b["dollars_per_degree"]} for b in pool]
    out["forecast"] = {
        "date": plan["date"], "mean_high_f": plan["forecast"]["mean_high_f"],
        "sd_f": plan["forecast"].get("sd_f"), "source": plan["forecast"].get("source"),
        "members": plan["forecast"].get("members"),
        "buckets": [{"label": b["bucket"], "model_prob": b["model_prob"], "market_price": b["ask"],
                     "temp_f": b["temp_f"]} for b in plan["buckets"]],
    }
    your_cost = round(plan["hedge_cost_pooled"] * share, 2)
    out["recommendation"] = {
        "date": plan["date"], "your_daily_cost": your_cost,
        "standalone_daily_cost": alone.get(domain, 0),
        "pool_daily_cost": plan["hedge_cost_pooled"],
        "pool_standalone_cost": plan["hedge_cost_standalone"],
        "pool_savings_pct": round(100 * (1 - plan["hedge_cost_pooled"] / plan["hedge_cost_standalone"]))
        if plan["hedge_cost_standalone"] else 0,
        "pool_size": len(pool), "net_dollars_per_degree": plan["net_dollars_per_degree"],
        "contracts": [{"bucket": b["bucket"], "contracts": b["contracts"], "price": b["price"],
                       "price_source": b["price_source"], "cost": b["cost"]}
                      for b in plan["buckets"] if b["contracts"]],
    }

    # History: the selected window this year plus the same calendar window in prior years.
    hist = hedge.history_highs(station["lat"], station["lon"])
    by_date = {date.fromisoformat(t): v for t, v in hist}
    end = max(by_date)
    start = end - timedelta(days=days - 1)
    for years_back in range(0, 5):
        lo, hi = _shift_year(start, -years_back), _shift_year(end, -years_back)
        for d, v in by_date.items():
            if lo <= d <= hi:
                out["temperature_history"].append({
                    "date": _shift_year(d, years_back).isoformat(),
                    "year": d.year if years_back == 0 else end.year - years_back,
                    "years_back": years_back, "high_f": round(v, 1)})

    # Daily weather P&L vs. a normal day for that date (same calendar week in prior years).
    # Daily contracts insure surprises, not seasons, so "normal" is the baseline.
    def normal_high(d: date) -> float | None:
        vals = [by_date[x] for k in range(1, 5) for off in range(-7, 8)
                if (x := _shift_year(d, -k) + timedelta(days=off)) in by_date]
        return statistics.mean(vals) if len(vals) >= 10 else None

    window = [(d, by_date[d], n) for d in sorted(by_date) if start <= d <= end
              if (n := normal_high(d)) is not None]
    if not window:
        return out

    def surprises(b):
        return [hedge.pnl(b, v) - hedge.pnl(b, n) for _, v, n in window]

    mine = surprises(biz)
    fee_alone = statistics.mean(max(0.0, -x) for x in mine)
    alone_fees = {b["domain"]: statistics.mean(max(0.0, -x) for x in surprises(b)) for b in pool}
    pool_surprise = [sum(col) for col in zip(*(surprises(b) for b in pool))]
    pool_premium = statistics.mean(max(0.0, -x) for x in pool_surprise)
    total_alone = sum(alone_fees.values())
    fee = pool_premium * (alone_fees.get(domain, fee_alone) / total_alone) if total_alone else 0.0
    hedged = [x + max(0.0, -x) - fee for x in mine]

    out["pnl_series"] = [{"date": d.isoformat(), "high_f": round(v, 1), "normal_high_f": round(n, 1),
                          "unhedged": round(u, 2), "hedged": round(h, 2)}
                         for (d, v, n), u, h in zip(window, mine, hedged)]
    worst = min(range(len(mine)), key=mine.__getitem__)
    out["summary"] = {
        "days": len(window), "from": window[0][0].isoformat(), "to": window[-1][0].isoformat(),
        "worst_day": {"date": window[worst][0].isoformat(), "high_f": round(window[worst][1], 1),
                      "normal_high_f": round(window[worst][2], 1),
                      "unhedged": round(mine[worst], 2), "hedged": round(hedged[worst], 2)},
        "bad_days": sum(x < 0 for x in mine),
        "stdev_unhedged": round(statistics.pstdev(mine), 2),
        "stdev_hedged": round(statistics.pstdev(hedged), 2),
        "daily_fee_pooled": round(fee, 2), "daily_fee_alone": round(fee_alone, 2),
        "total_fee_pooled": round(fee * len(window), 2),
        "total_fee_alone": round(fee_alone * len(window), 2),
        "total_losses_unhedged": round(sum(min(0.0, x) for x in mine), 2),
    }
    return out
