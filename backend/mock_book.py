"""In-memory order book with the same interface as gemini_client.py.

Mirrors the real sandbox rules we observed:
- The book is kept in YES space. "buy YES @p" is a bid at p; "buy NO @q" is an
  ask at 1-q. A YES buyer and a NO buyer match and together pay $1.
- You can only sell an outcome you hold (no naked shorts):
  "sell YES @p" is an ask at p; "sell NO @q" is a bid at 1-q.
- Price-time priority, fills at the resting order's price.
- Self-trade prevention: an incoming order cancels the same account's resting
  orders it would cross.
- YES and NO held in the same account net out (each pair redeems for $1).
Thread-safe, so the mm loop and the API can share it.
"""
import itertools
import threading
import time

from config import PROD_URL

_lock = threading.RLock()
_ids = itertools.count(1)
_orders: dict[str, dict] = {}      # order_id -> order (open orders only)
_positions: dict[tuple, dict] = {}  # (account, symbol, outcome) -> {"qty", "cost"}
_cash: dict[str, float] = {}        # account -> net cash flow (negative = spent)
_trades: list[dict] = []

_events_cache: dict = {"t": 0.0, "category": None, "data": []}
EVENTS_TTL = 300


class MockOrderError(Exception):
    pass


def get_events(category: str | None = None) -> list[dict]:
    """Real contract definitions from Gemini production (read-only, cached)."""
    import gemini_client
    c = _events_cache
    if c["category"] != category or time.time() - c["t"] > EVENTS_TTL:
        c.update(data=gemini_client.get_events(category, base=PROD_URL),
                 category=category, t=time.time())
    return c["data"]


def get_book(symbol: str) -> dict:
    with _lock:
        bids, asks = {}, {}
        for o in _orders.values():
            if o["symbol"] == symbol:
                side = bids if o["book_side"] == "bid" else asks
                side[o["yes_px"]] = side.get(o["yes_px"], 0) + o["remaining"]
        return {"bids": sorted(bids.items(), key=lambda l: -l[0]),
                "asks": sorted(asks.items(), key=lambda l: l[0])}


def place_order(account: str, symbol: str, side: str, outcome: str,
                price: float, qty: int) -> str:
    assert side in ("buy", "sell") and outcome in ("yes", "no")
    if not 0 < price < 1:
        raise ValueError(f"price must be in (0, 1), got {price}")
    price = round(price, 2)
    with _lock:
        if side == "sell":
            held = _positions.get((account, symbol, outcome), {}).get("qty", 0)
            committed = sum(o["remaining"] for o in _orders.values()
                            if (o["account"], o["symbol"], o["side"], o["outcome"])
                            == (account, symbol, "sell", outcome))
            if held - committed < qty:
                raise MockOrderError(
                    f"Cannot sell {outcome.upper()} contracts. No {outcome.upper()} position found.")
        # Translate into YES space: does this order sit on the bid or the ask?
        is_bid = (side, outcome) in (("buy", "yes"), ("sell", "no"))
        order = {
            "orderId": str(next(_ids)), "account": account, "symbol": symbol,
            "side": side, "outcome": outcome, "price": price, "quantity": qty,
            "remaining": qty, "book_side": "bid" if is_bid else "ask",
            "yes_px": price if outcome == "yes" else round(1 - price, 2),
            "createdAt": time.time(),
        }
        _match(order)
        if order["remaining"] > 0:
            _orders[order["orderId"]] = order
        return order["orderId"]


def _match(taker: dict) -> None:
    opposite = "ask" if taker["book_side"] == "bid" else "bid"
    crosses = (lambda m: m["yes_px"] <= taker["yes_px"]) if opposite == "ask" \
        else (lambda m: m["yes_px"] >= taker["yes_px"])
    best_first = (lambda m: (m["yes_px"], m["createdAt"])) if opposite == "ask" \
        else (lambda m: (-m["yes_px"], m["createdAt"]))
    makers = sorted((o for o in _orders.values() if o["symbol"] == taker["symbol"]
                     and o["book_side"] == opposite and crosses(o)), key=best_first)
    for maker in makers:
        if taker["remaining"] <= 0:
            break
        if maker["account"] == taker["account"]:  # self-trade prevention
            del _orders[maker["orderId"]]
            continue
        qty = min(taker["remaining"], maker["remaining"])
        yes_px = maker["yes_px"]
        for o in (taker, maker):
            o["remaining"] -= qty
            _fill(o, qty, yes_px)
        if maker["remaining"] <= 0:
            del _orders[maker["orderId"]]
        buyer, seller = (taker, maker) if taker["book_side"] == "bid" else (maker, taker)
        _trades.append({"symbol": taker["symbol"], "yes_price": yes_px, "qty": qty,
                        "taker": taker["account"], "maker": maker["account"],
                        # Who ended up long vs short YES, and how each side placed it.
                        "yes_buyer": buyer["account"], "yes_seller": seller["account"],
                        "buyer_order": f'{buyer["side"]} {buyer["outcome"]}',
                        "seller_order": f'{seller["side"]} {seller["outcome"]}',
                        "taker_order": taker["orderId"], "maker_order": maker["orderId"],
                        "time": time.time()})


def _fill(order: dict, qty: float, yes_px: float) -> None:
    px = yes_px if order["outcome"] == "yes" else round(1 - yes_px, 2)
    key = (order["account"], order["symbol"], order["outcome"])
    pos = _positions.setdefault(key, {"qty": 0.0, "cost": 0.0})
    if order["side"] == "buy":
        pos["qty"] += qty
        pos["cost"] += px * qty
        _cash[order["account"]] = _cash.get(order["account"], 0.0) - px * qty
    else:
        avg = pos["cost"] / pos["qty"] if pos["qty"] else 0.0
        pos["qty"] -= qty
        pos["cost"] -= avg * qty
        _cash[order["account"]] = _cash.get(order["account"], 0.0) + px * qty
    if pos["qty"] <= 1e-9:
        del _positions[key]
    _net(order["account"], order["symbol"])


def _net(account: str, symbol: str) -> None:
    """Like Gemini: holding YES and NO together redeems pairs for $1 each."""
    yes = _positions.get((account, symbol, "yes"))
    no = _positions.get((account, symbol, "no"))
    if not (yes and no):
        return
    pairs = min(yes["qty"], no["qty"])
    for key, pos in (((account, symbol, "yes"), yes), ((account, symbol, "no"), no)):
        pos["cost"] -= pos["cost"] / pos["qty"] * pairs
        pos["qty"] -= pairs
        if pos["qty"] <= 1e-9:
            del _positions[key]
    _cash[account] = _cash.get(account, 0.0) + pairs


def cancel_order(account: str, order_id: str) -> None:
    with _lock:
        o = _orders.get(str(order_id))
        if not o or o["account"] != account:
            raise MockOrderError(f"Order {order_id} not found")
        del _orders[str(order_id)]


def get_positions(account: str) -> list[dict]:
    """Same keys as Gemini's positions response (values as strings)."""
    with _lock:
        return [{"symbol": s, "outcome": out, "totalQuantity": f"{p['qty']:g}",
                 "avgPrice": f"{p['cost'] / p['qty']:.4f}"}
                for (a, s, out), p in _positions.items() if a == account]


def get_active_orders(account: str, symbol: str | None = None) -> list[dict]:
    with _lock:
        return [{"orderId": o["orderId"], "symbol": o["symbol"], "side": o["side"],
                 "outcome": o["outcome"], "price": f"{o['price']:.2f}",
                 "quantity": f"{o['quantity']:g}", "remainingQuantity": f"{o['remaining']:g}",
                 "filledQuantity": f"{o['quantity'] - o['remaining']:g}", "status": "open"}
                for o in _orders.values()
                if o["account"] == account and symbol in (None, o["symbol"])]


# --- mock-only helpers (not part of the shared interface) ---

def get_trades(symbol: str | None = None) -> list[dict]:
    with _lock:
        return [t for t in _trades if symbol in (None, t["symbol"])]


def get_cash(account: str) -> float:
    return _cash.get(account, 0.0)


def reset() -> None:
    with _lock:
        _orders.clear(); _positions.clear(); _cash.clear(); _trades.clear()
