"""End-to-end sandbox check of gemini_client: book, place, cancel, a cross-account
fill (mm sells 1 YES, shop buys it), and positions.

Usage: python scripts/test_client.py
"""
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import gemini_client as gc  # noqa: E402


def pick_contract() -> tuple[str, float, float]:
    """An open contract expiring >30 min out whose spread has room for our price."""
    soon = datetime.now(timezone.utc) + timedelta(minutes=30)
    for ev in gc.get_events():
        for c in ev["contracts"]:
            exp = datetime.fromisoformat(c["expiryDate"].replace("Z", "+00:00"))
            if c.get("marketState") != "open" or exp < soon:
                continue
            book = gc.get_book(c["instrumentSymbol"])
            if book["bids"] and book["asks"] and book["asks"][0][0] - book["bids"][0][0] >= 0.03:
                return c["instrumentSymbol"], book["bids"][0][0], book["asks"][0][0]
    raise SystemExit("No suitable sandbox contract found")


symbol, bid, ask = pick_contract()
print(f"1. book   {symbol}: best bid {bid:.2f} / best ask {ask:.2f}")

# Place + cancel a resting order far from the market.
oid = gc.place_order("mm", symbol, "buy", "yes", 0.01, 1)
active = [str(o["orderId"]) for o in gc.get_active_orders("mm", symbol)]
print(f"2. place  mm buy 1 YES @0.01 -> order {oid}, in active orders: {oid in active}")
gc.cancel_order("mm", oid)
active = [str(o["orderId"]) for o in gc.get_active_orders("mm", symbol)]
print(f"3. cancel order {oid}, still active: {oid in active}")

# Cross-account fill: shop rests a YES bid inside the spread, then the mm takes it.
# Selling YES requires holding YES, so the mm sells YES by buying NO at 1 - px.
book = gc.get_book(symbol)
px = round(book["bids"][0][0] + 0.01, 2)
buy_id = gc.place_order("shop", symbol, "buy", "yes", px, 1)
sell_id = gc.place_order("mm", symbol, "buy", "no", round(1 - px, 2), 1)
print(f"4. trade  shop buy 1 YES @{px:.2f} ({buy_id}), mm buy 1 NO @{1 - px:.2f} ({sell_id})")
time.sleep(2)
for acct, oid in (("shop", buy_id), ("mm", sell_id)):
    still_open = oid in [str(o["orderId"]) for o in gc.get_active_orders(acct, symbol)]
    print(f"   {acct} order {oid} filled: {not still_open}")
    if still_open:
        gc.cancel_order(acct, oid)

for acct in ("mm", "shop"):
    pos = [p for p in gc.get_positions(acct) if p.get("symbol") == symbol]
    print(f"5. positions {acct}: " + (", ".join(
        f"{p['outcome']} qty={p['totalQuantity']} avg={p['avgPrice']}" for p in pos) or "none"))
