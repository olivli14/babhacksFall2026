"""Read-only view of both agents' real Gemini sandbox accounts (GET /sandbox/accounts).

Shows what the Gemini website would: USD balance, prediction-market positions,
open orders and recent orders with fills. Every signed call bumps the per-key
nonce by one, so results are cached and refreshed by at most one request at a
time; otherwise public polling could push nonces too far ahead of the clock and
break the live run's own orders.
"""
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

import gemini_client
from gemini_auth import private

ACCOUNTS = {"mm": "Market maker", "shop": "Shop"}
STARTING_USD = 100_000.0  # sandbox grant both accounts started with
TTL = 12.0                # positions / orders refresh
BALANCE_TTL = 30.0
MATCH_WINDOW = 20.0       # seconds between the two sides of one fill

_lock = threading.Lock()
_cache: dict = {"t": 0.0, "data": None}
_balances: dict = {"t": 0.0, "data": {}}


def _ts(iso: str | None) -> float | None:
    return datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp() if iso else None


def _f(x, default=0.0) -> float:
    try:
        return float(x)
    except (TypeError, ValueError):
        return default


def _contract(o: dict) -> dict:
    meta = o.get("contractMetadata") or {}
    return {"symbol": o.get("symbol"), "event": meta.get("eventName"), "contract": meta.get("contractName")}


def _order(o: dict) -> dict:
    filled = _f(o.get("filledQuantity"))
    return {
        "order_id": str(o.get("orderId")), **_contract(o),
        "side": o.get("side"), "outcome": o.get("outcome"),
        "price": _f(o.get("price")), "qty": _f(o.get("quantity")), "filled": filled,
        "avg_fill_price": _f(o.get("avgExecutionPrice"), None) if filled else None,
        "status": o.get("status"),
        "created": _ts(o.get("createdAt")), "updated": _ts(o.get("updatedAt")),
    }


def _yes_price(o: dict) -> float:
    """Fill price in YES terms, so the two sides of one trade compare directly."""
    px = o["avg_fill_price"] or o["price"]
    return px if o["outcome"] == "yes" else round(1 - px, 4)


def _usd(account: str) -> dict:
    for b in private(account, "/v1/balances"):
        if b.get("currency") == "USD":
            amount = _f(b.get("amount"))
            return {"amount": amount, "available": _f(b.get("available")),
                    "change": round(amount - STARTING_USD, 2)}
    return {}


def _account(account: str, with_balance: bool) -> dict:
    positions = [{
        **_contract(p), "outcome": p.get("outcome"), "qty": _f(p.get("totalQuantity")),
        "avg_price": _f(p.get("avgPrice")), "market_value": _f(p.get("marketValue"), None),
        "unrealized_pnl": _f(p.get("unrealizedPnl"), None),
    } for p in gemini_client.get_positions(account)]
    open_orders = [_order(o) for o in gemini_client.get_active_orders(account)]
    history = [_order(o) for o in gemini_client.get_order_history(account)]
    out = {"label": ACCOUNTS[account], "positions": positions, "open_orders": open_orders,
           "orders": history[:15], "_history": history,
           "stats": {"orders": len(history), "filled_orders": sum(o["filled"] > 0 for o in history),
                     "contracts_filled": sum(o["filled"] for o in history)}}
    if with_balance:
        out["usd"] = _usd(account)
    return out


def _fills(accounts: dict) -> list[dict]:
    """Every filled order, labelled with who was on the other side when we can tell.

    Gemini doesn't return the counterparty, so a shop fill and a market-maker fill
    on the same contract, at the same YES price, from opposite sides, within a few
    seconds, are treated as one trade between our two agents. A market-maker fill
    with no shop match was another sandbox trader; "unknown" = too old to check.
    """
    def filled(acct):
        rows = accounts[acct]["open_orders"] + accounts[acct]["_history"]
        return [o for o in rows if o["filled"] > 0]

    def long_yes(o):
        return (o["side"], o["outcome"]) in (("buy", "yes"), ("sell", "no"))

    mm_fills = filled("mm")
    # Gemini returns only the MM's last 50 orders (it requotes every 10 s), so
    # older shop fills can't be checked against it.
    mm_seen_since = min((o["created"] or 0 for o in accounts["mm"]["_history"]), default=0)
    used = set()
    out = []
    for s in filled("shop"):
        match = next((m for m in mm_fills
                      if m["order_id"] not in used and m["symbol"] == s["symbol"]
                      and long_yes(m) != long_yes(s)
                      and abs(_yes_price(m) - _yes_price(s)) < 0.005
                      and abs((m["updated"] or 0) - (s["updated"] or 0)) < MATCH_WINDOW), None)
        if match:
            used.add(match["order_id"])
        other = "other" if (s["updated"] or 0) >= mm_seen_since else "unknown"
        out.append({"time": s["updated"], "symbol": s["symbol"], "event": s["event"],
                    "contract": s["contract"], "qty": s["filled"], "yes_price": _yes_price(s),
                    "yes_buyer": "shop" if long_yes(s) else (match and "mm") or other,
                    "yes_seller": "shop" if not long_yes(s) else (match and "mm") or other,
                    "between_our_agents": bool(match),
                    "orders": {"shop": s["order_id"], "mm": match and match["order_id"]}})
    for m in mm_fills:
        if m["order_id"] in used:
            continue
        out.append({"time": m["updated"], "symbol": m["symbol"], "event": m["event"],
                    "contract": m["contract"], "qty": m["filled"], "yes_price": _yes_price(m),
                    "yes_buyer": "mm" if long_yes(m) else "other",
                    "yes_seller": "other" if long_yes(m) else "mm",
                    "between_our_agents": False, "orders": {"shop": None, "mm": m["order_id"]}})
    return sorted(out, key=lambda t: -(t["time"] or 0))[:20]


def _refresh() -> dict:
    with_balance = time.time() - _balances["t"] > BALANCE_TTL
    with ThreadPoolExecutor(2) as pool:  # different API keys, so no nonce clash
        futures = {a: pool.submit(_account, a, with_balance) for a in ACCOUNTS}
        accounts = {a: f.result() for a, f in futures.items()}
    if with_balance:
        _balances.update(t=time.time(), data={a: accounts[a].pop("usd", {}) for a in ACCOUNTS})
    for a in ACCOUNTS:
        accounts[a]["usd"] = _balances["data"].get(a, {})
    fills = _fills(accounts)
    for a in ACCOUNTS:
        accounts[a].pop("_history")
    return {"accounts": accounts, "fills": fills}


def snapshot() -> dict:
    """Cached snapshot; a failed refresh serves the last good one with an error."""
    with _lock:
        age = time.time() - _cache["t"]
        if _cache["data"] is None or age > TTL:
            try:
                _cache.update(data=_refresh(), t=time.time(), error=None)
            except Exception as e:  # keep serving the last good snapshot
                _cache["error"] = str(e)[:200]
                if _cache["data"] is None:
                    raise
        return {**_cache["data"], "fetched_at": _cache["t"], "error": _cache.get("error")}
