"""FastAPI layer the frontend calls. Run: uvicorn api:app --reload

The weather hedging story runs on `market` (MODE=mock: our order book, real
Gemini contract definitions). The /live endpoints run the agents on the real
Gemini sandbox and are started only with the DEMO_ADMIN_TOKEN header.
Every response carries `mode` so the UI can label panels.
"""
import hashlib
import json
import logging
import os
import random
import statistics
import threading
import time
from contextlib import asynccontextmanager
from typing import Literal

from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

import config
import contracts
import forecast
import market
import mm_agent
import mock_book
import shop_agent
from gemini_auth import private
from live import LiveRun, cancel_all_open

log = logging.getLogger("api")
MODE = config.MODE
MAX_PREMIUM_BUDGET = 1000.0
ADMIN_TOKEN = os.getenv("DEMO_ADMIN_TOKEN", "")
ORIGINS = ["http://localhost:3000", "http://localhost:5173"] + [
    o.strip() for o in os.getenv("FRONTEND_ORIGINS", "").split(",") if o.strip()]


class Profile(BaseModel):
    business_type: str = Field(min_length=1, max_length=80)
    location: str = Field(min_length=2, max_length=80)
    baseline_revenue: float = Field(gt=0, le=1_000_000)
    weather_variable: Literal["temperature_high"] = "temperature_high"
    bad_direction: Literal["below", "above"]
    threshold_f: float = Field(ge=-20, le=120)
    loss_per_degree: float = Field(ge=0, le=100_000)
    premium_budget: float = Field(gt=0, le=MAX_PREMIUM_BUDGET)


class ProfileBody(BaseModel):
    profile: Profile


class SimulateBody(BaseModel):
    profile_id: str
    days: int = Field(default=1000, ge=10, le=10_000)


class SettleBody(BaseModel):
    profile_id: str


class LiveStartBody(BaseModel):
    seconds: int = Field(default=300, ge=30, le=900)


# --- shared state ---
state = {"mm": None, "symbols": [], "event": None, "live": None}
profiles: dict[str, dict] = {}      # profile_id -> {"profile", "rec", "orders"}
_sandbox_ok = {"t": 0.0, "ok": None}
_lock = threading.Lock()


def profile_id(p: dict) -> str:
    return hashlib.sha1(json.dumps(p, sort_keys=True).encode()).hexdigest()[:12]


def start_market_maker() -> None:
    """Quote every bucket of the preset city's latest event."""
    event = contracts.find_event(shop_agent.ICE_CREAM_PRESET["location"])
    syms = contracts.event_symbols(event)
    mm = mm_agent.MarketMaker(syms)
    mm.step()  # quotes are up before the first request
    mm.start()
    state.update(mm=mm, symbols=syms, event=event)
    log.info("market maker quoting %d contracts on %s", len(syms), event["ticker"])


@asynccontextmanager
async def lifespan(app: FastAPI):
    logging.basicConfig(level=logging.INFO)
    try:
        if n := cancel_all_open():  # orders orphaned by a previous crash
            log.info("cancelled %d leftover sandbox orders", n)
    except Exception:
        log.exception("sandbox cleanup failed")
    try:
        start_market_maker()
    except Exception:
        log.exception("market maker failed to start")
    yield
    if state["mm"]:
        state["mm"].stop()
    if state["live"]:
        state["live"].stop()


app = FastAPI(title="Weather Hedging Agents", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=ORIGINS, allow_methods=["*"],
                   allow_headers=["*"])


def ensure_event_quoted(location: str) -> None:
    """If a profile is for a different city, have the market maker quote it too."""
    event = contracts.find_event(location)
    mm = state["mm"]
    new = [s for s in contracts.event_symbols(event) if s not in mm.symbols]
    if new:
        mm.symbols.extend(new)
        for s in new:
            mm.requote(s)


def check_sandbox() -> bool:
    """Both accounts reachable and terms accepted (cached for 60 s)."""
    if time.time() - _sandbox_ok["t"] > 60:
        try:
            _sandbox_ok["ok"] = all(
                private(a, "/v1/prediction-markets/terms/status", method="GET")
                .get("hasAcceptedLatest") for a in ("mm", "shop"))
        except Exception:
            _sandbox_ok["ok"] = False
        _sandbox_ok["t"] = time.time()
    return _sandbox_ok["ok"]


# --- endpoints ---
@app.get("/health")
def health():
    mm = state["mm"]
    live = state["live"]
    return {"mode": MODE, "mm_running": bool(mm and mm.running),
            "mm_event": state["event"]["ticker"] if state["event"] else None,
            "sandbox_ok": check_sandbox(), "live_running": bool(live and live.running)}


@app.get("/market")
def get_market(symbol: str | None = Query(None)):
    """One contract, or every contract the market maker quotes."""
    mm = state["mm"]
    if not mm:
        raise HTTPException(503, "market maker not running")
    syms = [symbol] if symbol else mm.symbols
    out = []
    for s in syms:
        c = contracts.parse(s)
        q = mm.state.get(s)  # use the mm's own fair value so the panel is consistent
        fv = q["fair_value"] if q else round(contracts.fair_value(s), 4)
        out.append({"symbol": s, "bucket": c["strike"], "lo": c["lo"], "hi": c["hi"],
                    "fair_value": fv, "book": market.get_book(s), "mm_quotes": q})
    event = state["event"]
    body = {"mode": MODE, "event": event["ticker"], "event_title": event.get("title"),
            "contracts": out}
    if symbol:
        body.update(out[0])
    return body


@app.get("/positions")
def get_positions(account: Literal["mm", "shop"]):
    return {"mode": MODE, "account": account, "positions": market.get_positions(account)}


@app.post("/hedge")
def hedge(body: ProfileBody):
    p = body.profile.model_dump()
    ensure_event_quoted(p["location"])
    rec = shop_agent.recommend(p)
    pid = profile_id(p)
    with _lock:
        profiles[pid] = {"profile": p, "rec": rec, "orders": None}
    return {"mode": MODE, "profile_id": pid, "recommendation": rec,
            "explanation": rec["explanation"]}


@app.post("/hedge/execute")
def hedge_execute(body: ProfileBody):
    p = body.profile.model_dump()
    ensure_event_quoted(p["location"])
    rec = shop_agent.recommend(p)  # re-price against the current book
    orders = shop_agent.execute(rec)
    pid = profile_id(p)
    with _lock:
        profiles[pid] = {"profile": p, "rec": rec, "orders": orders}
    statuses = {o["status"] for o in orders}
    status = "filled" if statuses == {"filled"} else ("none" if not orders else "partial")
    return {"mode": MODE, "profile_id": pid, "order_ids": [o["order_id"] for o in orders],
            "orders": orders, "status": status, "recommendation": rec,
            "explanation": rec["explanation"]}


@app.get("/scenarios")
def scenarios(profile_id: str):
    entry = profiles.get(profile_id)
    if not entry:
        raise HTTPException(404, "unknown profile_id; call /hedge first")
    p, rec = entry["profile"], entry["rec"]
    t = p["threshold_f"]
    hot, cold = (t + 6, t - 8) if p["bad_direction"] == "below" else (t + 8, t - 6)
    return {"mode": MODE, "executed": entry["orders"] is not None,
            "hot": shop_agent.scenario(p, rec, hot),
            "cold": shop_agent.scenario(p, rec, cold)}


@app.get("/trades")
def trades(limit: int = Query(50, ge=1, le=500)):
    """Recent fills on the simulated book, newest first, in plain words."""
    out = []
    for t in reversed(mock_book.get_trades()[-limit:]):
        c = contracts.parse(t["symbol"])
        out.append({**t, "bucket": c["strike"],
                    "no_price": round(1 - t["yes_price"], 2),
                    "notional": round(t["yes_price"] * t["qty"], 2)})
    return {"mode": MODE, "trades": out}


def _forecast_for(entry: dict) -> dict:
    rec = entry["rec"]
    return forecast.distribution(rec["location"], rec["date"])


def _entry(profile_id: str) -> dict:
    entry = profiles.get(profile_id)
    if not entry:
        raise HTTPException(404, "unknown profile_id; call /hedge first")
    return entry


@app.post("/simulate")
def simulate(body: SimulateBody):
    """Draw `days` possible daily highs from the forecast and settle the hedge each time."""
    entry = _entry(body.profile_id)
    p, rec = entry["profile"], entry["rec"]
    dist = _forecast_for(entry)
    rng = random.Random(42)  # same picture every click, so the demo is stable
    temps = [round(rng.gauss(dist["mean_f"], dist["sd_f"])) for _ in range(body.days)]
    runs = [shop_agent.scenario(p, rec, t) for t in temps]
    hedged = [r["net"] for r in runs]
    unhedged = [r["net_unhedged"] for r in runs]

    lo, hi = min(hedged + unhedged), max(hedged + unhedged)
    n_bins = 20
    width = max((hi - lo) / n_bins, 1.0)
    bins = [{"from": round(lo + i * width, 2), "to": round(lo + (i + 1) * width, 2),
             "hedged": 0, "unhedged": 0} for i in range(n_bins)]
    for h, u in zip(hedged, unhedged):
        bins[min(int((h - lo) / width), n_bins - 1)]["hedged"] += 1
        bins[min(int((u - lo) / width), n_bins - 1)]["unhedged"] += 1

    def stats(xs):
        return {"mean": round(statistics.mean(xs), 2), "worst": round(min(xs), 2),
                "best": round(max(xs), 2), "stdev": round(statistics.pstdev(xs), 2),
                "p5": round(sorted(xs)[len(xs) // 20], 2)}

    temp_counts: dict[int, int] = {}
    for t in temps:
        temp_counts[t] = temp_counts.get(t, 0) + 1
    return {"mode": MODE, "days": body.days,
            "forecast": {k: dist[k] for k in ("mean_f", "sd_f", "source")},
            "hedged": stats(hedged), "unhedged": stats(unhedged),
            "days_hedge_paid": sum(r["hedge_payout"] > 0 for r in runs),
            "premium": rec["premium"],
            "histogram": bins,
            "temperatures": [{"temp_f": t, "days": n} for t, n in sorted(temp_counts.items())],
            "sample": runs[:30]}


@app.post("/settle")
def settle(body: SettleBody):
    """Pick one high from the forecast and settle the hedge: one simulated 'tomorrow'."""
    entry = _entry(body.profile_id)
    dist = _forecast_for(entry)
    temp = round(random.gauss(dist["mean_f"], dist["sd_f"]))
    result = shop_agent.scenario(entry["profile"], entry["rec"], temp)
    winners = [l["bucket"] for l in entry["rec"]["legs"]
               if contracts.pays_out(contracts.parse(l["symbol"]), temp)]
    return {"mode": MODE, "temp_f": temp, "forecast": {k: dist[k] for k in ("mean_f", "sd_f", "source")},
            "paying_buckets": winners, "result": result}


@app.get("/presets")
def presets():
    return {"mode": MODE, "ice_cream": shop_agent.ICE_CREAM_PRESET}


@app.post("/intake")
def intake():
    # Step 11: Claude-backed chat. Until then the UI uses the preset.
    return {"mode": MODE, "reply": "Intake chat isn't wired up yet. Use the Ice cream shop preset.",
            "profile": None}


# --- live sandbox panel ---
@app.get("/live")
def live_status():
    live = state["live"]
    return {"mode": "sandbox", **(live.status() if live else {"running": False, "log": []})}


@app.post("/live/start")
def live_start(body: LiveStartBody, x_demo_admin_token: str = Header(default="")):
    if not ADMIN_TOKEN or x_demo_admin_token != ADMIN_TOKEN:
        raise HTTPException(403, "live sandbox trading requires the admin token")
    if state["live"] and state["live"].running:
        raise HTTPException(409, "a live run is already in progress")
    state["live"] = LiveRun(body.seconds)
    state["live"].start()
    return {"mode": "sandbox", "started": True, "seconds": body.seconds}


@app.post("/live/stop")
def live_stop(x_demo_admin_token: str = Header(default="")):
    if not ADMIN_TOKEN or x_demo_admin_token != ADMIN_TOKEN:
        raise HTTPException(403, "requires the admin token")
    if state["live"]:
        state["live"].stop()
    return {"mode": "sandbox", "stopping": True}
