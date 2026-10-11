"""Offline checks for mock_book (no network except the optional events test).

Usage: python scripts/test_mock_book.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import mock_book as mb  # noqa: E402

S = "GEMI-WXHIGH-NYC-2610130359-LO61"

# MM quotes: bid YES @0.30 x10, ask YES @0.36 x10 (posted as buy NO @0.64).
bid = mb.place_order("mm", S, "buy", "yes", 0.30, 10)
ask = mb.place_order("mm", S, "buy", "no", 0.64, 10)
assert mb.get_book(S) == {"bids": [(0.30, 10)], "asks": [(0.36, 10)]}, mb.get_book(S)
print("1. mm quotes rest:", mb.get_book(S))

# Shop lifts 4 at 0.36 -> YES/NO match.
mb.place_order("shop", S, "buy", "yes", 0.40, 4)
assert mb.get_book(S)["asks"] == [(0.36, 6)]
assert mb.get_positions("shop") == [{"symbol": S, "outcome": "yes", "totalQuantity": "4", "avgPrice": "0.3600"}]
assert mb.get_positions("mm") == [{"symbol": S, "outcome": "no", "totalQuantity": "4", "avgPrice": "0.6400"}]
print("2. shop buys 4 YES @0.36; mm gets 4 NO @0.64; book:", mb.get_book(S))

# No naked shorts.
try:
    mb.place_order("shop", S, "sell", "yes", 0.50, 5)
    raise AssertionError("expected naked short to fail")
except mb.MockOrderError as e:
    print("3. naked short rejected:", e)

# Shop can sell what it holds: sell 2 YES @0.30 hits the mm bid.
mb.place_order("shop", S, "sell", "yes", 0.30, 2)
assert mb.get_book(S)["bids"] == [(0.30, 8)]
assert mb.get_positions("shop")[0]["totalQuantity"] == "2"
assert mb.get_positions("mm") == [{"symbol": S, "outcome": "no", "totalQuantity": "2", "avgPrice": "0.6400"}], mb.get_positions("mm")
print("4. shop sells 2 YES into mm bid; shop holds 2 YES; mm's 4 NO + 2 YES net to 2 NO")

# Cancel.
mb.cancel_order("mm", ask)
assert mb.get_book(S)["asks"] == []
print("5. cancel mm ask; active mm orders:", [o["orderId"] for o in mb.get_active_orders("mm")])

# Self-trade prevention: mm crossing its own bid cancels the resting bid.
mb.place_order("mm", S, "buy", "no", 0.75, 1)  # YES ask @0.25 crosses own bid @0.30
assert bid not in [o["orderId"] for o in mb.get_active_orders("mm")]
print("6. self-trade prevented; book:", mb.get_book(S))

# Netting: mm holds 2 NO; buying the shop's last 2 YES nets the mm to flat.
mb.place_order("shop", S, "sell", "yes", 0.40, 2)
mb.place_order("mm", S, "buy", "yes", 0.40, 2)
assert mb.get_positions("mm") == [] and mb.get_positions("shop") == []
print("6b. netting: mm 2 NO + 2 YES -> flat; shop flat")

print(f"7. trades: {len(mb.get_trades())}, cash mm={mb.get_cash('mm'):.2f} shop={mb.get_cash('shop'):.2f}")

ev = mb.get_events("Weather")
print(f"8. get_events('Weather') from production: {len(ev)} events, e.g. {ev[0]['title'] if ev else '-'}")
print("ALL MOCK BOOK CHECKS PASSED")
