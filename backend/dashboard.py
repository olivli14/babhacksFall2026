# AI-generated with Claude (Anthropic). Review before relying on it.
"""Routes for the onboarding + dashboard frontend. Mounted in api.py.

POST /api/onboard      {url, city?, annual_revenue?} -> {domain, profile}
GET  /api/businesses                                  -> [profile, ...]
GET  /api/dashboard    ?domain=&days=                 -> everything the dashboard shows
POST /api/pool/execute {domain}                       -> the pool buys its contracts from the market maker
GET  /api/pool/market  ?domain=                       -> market maker quotes + fills for the pool's event

Per-business hedge math: each business is covered for days that come in below
its own average weather P&L. Its fee is its share of the pooled premium,
split in proportion to what it would pay hedging alone.
"""
import json
import random
import statistics
import time
from datetime import date, timedelta

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

import contracts
import db
import forecast
import hedge
import market
import mock_book
import onboard

router = APIRouter(prefix="/api")


class PoolBody(BaseModel):
    domain: str


SIM_DAYS = 1000


def _simulate(biz: dict, plan: dict, share: float) -> dict:
    """1,000 possible tomorrows drawn from the forecast.

    Unhedged: this business's weather P&L vs. a day at the forecast mean.
    Hedged (swap): members hand their weather swings to the pool, so opposite
    businesses fund each other. The pool buys Gemini contracts on its net
    leftover. Each member gets `share` of the pool's result: the pooled swing
    plus contract payouts minus the premium. No free lunch: the average hedged
    day is negative by the expected cost of the hedge.
    """
    fc = plan["forecast"]
    mean, sd = fc["mean_f"], fc["sd_f"]
    pool = plan["businesses"]
    expected = {b["domain"]: hedge.pnl(b, mean) for b in pool}
    premium = plan["hedge_cost_pooled"]
    rng = random.Random(42)  # same picture on every load
    temps = [round(rng.gauss(mean, sd)) for _ in range(SIM_DAYS)]

    unhedged, hedged, payouts = [], [], []
    for t in temps:
        pool_swing = sum(hedge.pnl(b, t) - expected[b["domain"]] for b in pool)
        payout = sum(b["contracts"] for b in plan["buckets"] if hedge.in_bucket(_bounds(b), t))
        payouts.append(payout)
        unhedged.append(hedge.pnl(biz, t) - expected[biz["domain"]])
        hedged.append(share * (pool_swing + payout - premium))

    lo, hi = min(unhedged + hedged), max(unhedged + hedged)
    n_bins = 24
    width = max((hi - lo) / n_bins, 1.0)
    bins = [{"from": round(lo + i * width, 2), "to": round(lo + (i + 1) * width, 2), "hedged": 0, "unhedged": 0}
            for i in range(n_bins)]
    for h, u in zip(hedged, unhedged):
        bins[min(int((h - lo) / width), n_bins - 1)]["hedged"] += 1
        bins[min(int((u - lo) / width), n_bins - 1)]["unhedged"] += 1

    def stats(xs):
        xs_sorted = sorted(xs)
        return {"mean": round(statistics.mean(xs), 2), "worst": round(xs_sorted[0], 2),
                "best": round(xs_sorted[-1], 2), "stdev": round(statistics.pstdev(xs), 2),
                "p5": round(xs_sorted[len(xs) // 20], 2), "p95": round(xs_sorted[-(len(xs) // 20) - 1], 2)}

    return {"days": SIM_DAYS, "forecast_mean_f": round(mean, 1), "forecast_sd_f": round(sd, 2),
            "share": round(share, 3), "premium": round(share * premium, 2),
            "days_hedge_paid": sum(p > 0 for p in payouts),
            # Expected cost: your share of the premium minus your share of the average payout.
            # Computed from the payouts directly; the swing terms average out and only add noise.
            "avg_cost": round(share * (premium - statistics.mean(payouts)), 2),
            "unhedged": stats(unhedged), "hedged": stats(hedged), "histogram": bins}


def _bounds(row: dict) -> dict:
    """Parse a plan bucket label ('70°F to 71°F') into lo/hi."""
    lo, hi = hedge.parse_bucket(row["bucket"])
    return {"lo": lo, "hi": hi}


class OnboardBody(BaseModel):
    url: str = Field(min_length=3, max_length=300)
    name: str | None = Field(default=None, max_length=120)
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
        profile = onboard.run(body.url.strip(), (body.city or "").strip() or None, body.annual_revenue,
                              (body.name or "").strip() or None)
    except onboard.OnboardError as e:
        raise HTTPException(400, str(e))
    return {"domain": profile["domain"], "profile": profile}


@router.get("/businesses")
def api_businesses():
    return sorted(_all_businesses(), key=lambda b: b.get("name") or b["domain"])


@router.get("/dashboard")
def api_dashboard(domain: str, days: int = Query(365, ge=7, le=730)):
    biz = _business(domain)
    out = {"business": biz, "hub": None, "forecast": None, "recommendation": None, "simulation": None,
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

    plan = hedge.plan(city, store=False, price_fn=_mm_ask_fn(city))
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
        "pool_daily_cost": plan["hedge_cost_pooled"], "priced_by": "market maker" if any(b["price_source"] == "market maker" for b in plan["buckets"]) else "forecast",
        "pool_standalone_cost": plan["hedge_cost_standalone"],
        "pool_savings_pct": round(100 * (1 - plan["hedge_cost_pooled"] / plan["hedge_cost_standalone"]))
        if plan["hedge_cost_standalone"] else 0,
        "pool_size": len(pool), "net_dollars_per_degree": plan["net_dollars_per_degree"],
        "contracts": [{"bucket": b["bucket"], "contracts": b["contracts"], "price": b["price"],
                       "price_source": b["price_source"], "cost": b["cost"]}
                      for b in plan["buckets"] if b["contracts"]],
    }

    out["simulation"] = _simulate(biz, plan, share)

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


def _mm_ask_fn(city: str):
    """Price lookup at the market maker's current ask, or None if it isn't running."""
    import api

    if not api.state.get("mm"):
        return None
    try:
        api.ensure_event_quoted(city)
    except Exception:
        return None

    def ask(symbol):
        asks = market.get_book(symbol)["asks"] if symbol else []
        return asks[0][0] if asks else None
    return ask


# --- Agents in action: the pool trades with the market maker on the simulated book ---

def _pool_event(domain: str) -> tuple[dict, list[str]]:
    import api  # api imports this module; by request time it's fully loaded

    city = _business(domain).get("gemini_city")
    if not city:
        raise HTTPException(400, "this business has no weather market")
    if not api.state["mm"]:
        raise HTTPException(503, "market maker not running")
    api.ensure_event_quoted(city)
    event = contracts.find_event(city)
    return event, contracts.event_symbols(event)


@router.post("/pool/execute")
def pool_execute(body: PoolBody):
    """The pool's agent buys tomorrow's contracts at the market maker's ask."""
    biz = _business(body.domain)
    event, symbols = _pool_event(body.domain)
    plan = hedge.plan(biz["gemini_city"], store=False, price_fn=_mm_ask_fn(biz["gemini_city"]))
    by_bucket = {contracts.parse(s)["strike"]: s for s in symbols}
    orders = []
    for b in plan["buckets"]:
        if not b["contracts"]:
            continue
        sym = b["instrument"] if b["instrument"] in symbols else None
        if not sym:
            lo, hi = hedge.parse_bucket(b["bucket"])
            key = f"LO{hi}" if lo is None else f"HI{lo}" if hi is None else f"{lo}TO{hi}"
            sym = by_bucket.get(key)
        asks = market.get_book(sym)["asks"] if sym else []
        if not asks:
            orders.append({"bucket": b["bucket"], "qty": b["contracts"], "status": "no ask"})
            continue
        price = asks[0][0]
        qty = min(b["contracts"], 2000)
        oid = market.place_order("shop", sym, "buy", "yes", price, qty)
        still_open = {str(o["orderId"]): o for o in market.get_active_orders("shop", sym)}.get(oid)
        filled = qty - float(still_open["remainingQuantity"]) if still_open else qty
        if still_open:
            market.cancel_order("shop", oid)
        orders.append({"bucket": b["bucket"], "symbol": sym, "qty": qty, "price": price,
                       "filled": filled, "cost": round(filled * price, 2),
                       "status": "filled" if filled == qty else "partial" if filled else "unfilled"})
    return {"mode": market.MODE, "event": event.get("title"),
            "orders": orders, "total_cost": round(sum(o.get("cost", 0) for o in orders), 2)}


@router.get("/pool/market")
def pool_market(domain: str):
    """Market maker quotes and recent fills for this business's weather event."""
    import api

    event, symbols = _pool_event(domain)
    mm = api.state["mm"]
    quotes = []
    for s in symbols:
        c = contracts.parse(s)
        q = mm.state.get(s) or {}
        quotes.append({"symbol": s, "bucket": c["strike"], "lo": c["lo"], "hi": c["hi"],
                       "fair_value": q.get("fair_value"), "bid": q.get("bid"), "ask": q.get("ask"),
                       "inventory": (q.get("inventory_yes", 0) or 0) - (q.get("inventory_no", 0) or 0)})
    fills = []
    for t in reversed(mock_book.get_trades()[-200:]):
        if t["symbol"] in symbols:
            fills.append({**t, "bucket": contracts.parse(t["symbol"])["strike"]})
    return {"mode": api.MODE, "event": event.get("title"), "quotes": quotes, "fills": fills[:30],
            "as_of": time.time()}
