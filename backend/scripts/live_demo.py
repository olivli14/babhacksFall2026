"""Run the two agents LIVE on the Gemini sandbox for a few minutes.

The sandbox has no weather markets, so this uses a crypto contract:
- Market maker: the same mm_agent.MarketMaker. Fair value = mid of everyone
  else's quotes (our own orders are subtracted from the book), since the
  weather forecast doesn't apply to crypto.
- Shop: same sizing logic as shop_agent (loss to protect -> contracts, capped
  by a premium budget), buying YES from the market maker's ask.
All open orders are cancelled on exit.

Usage: python scripts/live_demo.py [seconds=300]
"""
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

os.environ["MODE"] = "sandbox"  # must be set before importing config/market
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import gemini_client as gc  # noqa: E402
import market  # noqa: E402
import mm_agent  # noqa: E402

DURATION = int(sys.argv[1]) if len(sys.argv) > 1 else 300
SHOP_PROFILE = {"business_type": "demo shop", "loss_to_protect": 10.0, "premium_budget": 6.0}
_last_fair: dict[str, float] = {}


def log(msg: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def external_book(symbol: str) -> dict:
    """The sandbox book minus the market maker's own resting orders."""
    book = gc.get_book(symbol)
    bids, asks = dict(book["bids"]), dict(book["asks"])
    for o in gc.get_active_orders("mm", symbol):
        rem = float(o["remainingQuantity"])
        px = float(o["price"])
        if (o["side"], o["outcome"]) in (("buy", "yes"), ("sell", "no")):
            yes_px = px if o["outcome"] == "yes" else round(1 - px, 2)
            bids[yes_px] = bids.get(yes_px, 0) - rem
        else:
            yes_px = px if o["outcome"] == "yes" else round(1 - px, 2)
            asks[yes_px] = asks.get(yes_px, 0) - rem
    return {"bids": sorted([(p, q) for p, q in bids.items() if q > 1e-9], key=lambda l: -l[0]),
            "asks": sorted([(p, q) for p, q in asks.items() if q > 1e-9], key=lambda l: l[0])}


def mid_fair_value(symbol: str) -> float:
    b = external_book(symbol)
    if b["bids"] and b["asks"]:
        _last_fair[symbol] = (b["bids"][0][0] + b["asks"][0][0]) / 2
    return _last_fair[symbol]


def pick_contract() -> tuple[str, str]:
    later = datetime.now(timezone.utc) + timedelta(seconds=DURATION + 15 * 60)
    best = None
    for ev in gc.get_events():
        for c in ev["contracts"]:
            exp = datetime.fromisoformat(c["expiryDate"].replace("Z", "+00:00"))
            if c.get("marketState") != "open" or exp < later:
                continue
            book = gc.get_book(c["instrumentSymbol"])
            if not (book["bids"] and book["asks"]):
                continue
            bid, ask = book["bids"][0][0], book["asks"][0][0]
            mid = (bid + ask) / 2
            # Want room inside the spread for our quotes and an uncertain outcome.
            if ask - bid >= 0.06 and 0.2 <= mid <= 0.8:
                score = abs(mid - 0.5)
                if best is None or score < best[0]:
                    best = (score, c["instrumentSymbol"], f"{ev['title']} / {c['label']}")
    if not best:
        raise SystemExit("No suitable sandbox contract right now")
    return best[1], best[2]


def shop_hedge(symbol: str, mm: mm_agent.MarketMaker) -> None:
    """Same logic as shop_agent: contracts = loss to protect, capped by budget."""
    ask = mm.state[symbol]["ask"]
    target = int(SHOP_PROFILE["loss_to_protect"])          # $1 payout per contract
    qty = min(target, int(SHOP_PROFILE["premium_budget"] // ask))
    log(f"SHOP  wants ${target:.0f} of protection; mm ask is {ask:.2f}; budget "
        f"${SHOP_PROFILE['premium_budget']:.0f} -> buying {qty} YES @ {ask:.2f} "
        f"(premium ${qty * ask:.2f}, covers {qty / target:.0%})")
    oid = market.place_order("shop", symbol, "buy", "yes", ask, qty)
    time.sleep(2)
    still_open = [o for o in gc.get_active_orders("shop", symbol) if str(o["orderId"]) == oid]
    if still_open:
        log(f"SHOP  order {oid} filled {still_open[0]['filledQuantity']}/{qty}; cancelling rest")
        market.cancel_order("shop", oid)
    else:
        log(f"SHOP  order {oid} FILLED {qty}/{qty}")


def positions(symbol: str) -> str:
    out = []
    for acct in ("mm", "shop"):
        ps = [f"{p['outcome'].upper()} {p['totalQuantity']}@{float(p['avgPrice']):.2f}"
              for p in gc.get_positions(acct) if p["symbol"] == symbol]
        out.append(f"{acct}: {', '.join(ps) or 'flat'}")
    return " | ".join(out)


def cleanup(symbol: str) -> None:
    for acct in ("mm", "shop"):
        for o in gc.get_active_orders(acct, symbol):
            try:
                gc.cancel_order(acct, str(o["orderId"]))
            except Exception:
                pass


if __name__ == "__main__":
    symbol, desc = pick_contract()
    log(f"LIVE SANDBOX demo for {DURATION}s on {symbol}  ({desc})")
    mm = mm_agent.MarketMaker(
        [symbol],
        mm_agent.MMConfig(half_spread=0.02, size=5, skew_per_contract=0.004,
                          max_skew=0.03, interval=10),
        fair_value_fn=mid_fair_value)
    end = time.time() + DURATION
    hedged = False
    try:
        while time.time() < end:
            mm.step()
            q = mm.state.get(symbol)
            if q:
                log(f"MM    fair {q['fair_value']:.3f}  bid {q['bid']:.2f}  ask {q['ask']:.2f}  "
                    f"size {q['size']}  inv YES {q['inventory_yes']:g} / NO {q['inventory_no']:g}")
            if not hedged and q and time.time() > end - DURATION + 30:
                shop_hedge(symbol, mm)
                hedged = True
                log(f"POS   {positions(symbol)}")
            time.sleep(mm.config.interval)
    except KeyboardInterrupt:
        log("interrupted")
    finally:
        mm._live.clear()
        cleanup(symbol)
        log(f"stopped; all open orders cancelled. Final: {positions(symbol)}")
