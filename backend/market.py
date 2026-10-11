"""The trading interface agents import. Picks the backend from MODE in config.

    import market
    market.place_order("shop", symbol, "buy", "yes", 0.30, 10)
"""
from config import MODE

if MODE == "sandbox":
    from gemini_client import (cancel_order, get_active_orders, get_book,  # noqa: F401
                               get_events, get_positions, place_order)
else:
    from mock_book import (cancel_order, get_active_orders, get_book,  # noqa: F401
                           get_events, get_positions, place_order)
