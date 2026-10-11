"""Gemini Prediction Markets client (sandbox). mock_book.py implements the same interface.

Accounts are "mm" (market maker) and "shop"; credentials come from config.py.
Prices are in [0, 1] (dollars per $1 contract). Books are in YES space.
"""
import requests

from config import PROD_URL, SANDBOX_URL
from gemini_auth import private

PRICE_DECIMALS = 2  # priceIncrement is 0.01 on every contract seen so far


def get_events(category: str | None = None, base: str = SANDBOX_URL) -> list[dict]:
    """Active events (each with a `contracts` list). Pass base=PROD_URL for production."""
    events, offset = [], 0
    while True:
        params = {"status": "active", "limit": 500, "offset": offset}
        if category:
            params["category"] = category
        r = requests.get(f"{base}/v1/prediction-markets/events", params=params, timeout=30)
        r.raise_for_status()
        body = r.json()
        batch = body.get("data", [])
        events.extend(batch)
        offset += len(batch)
        if not batch or offset >= body.get("pagination", {}).get("total", 0):
            return events


def get_book(symbol: str, base: str = SANDBOX_URL) -> dict:
    """{"bids": [(price, qty), ...] best first, "asks": [...] best first}, YES space."""
    r = requests.get(f"{base}/v1/book/{symbol}", timeout=15)
    r.raise_for_status()
    raw = r.json()
    levels = lambda side: [(float(l["price"]), float(l["amount"])) for l in raw.get(side, [])]
    return {
        "bids": sorted(levels("bids"), key=lambda l: -l[0]),
        "asks": sorted(levels("asks"), key=lambda l: l[0]),
    }


def place_order(account: str, symbol: str, side: str, outcome: str,
                price: float, qty: int) -> str:
    """Good-til-cancel limit order. Returns the order id as a string."""
    assert side in ("buy", "sell") and outcome in ("yes", "no")
    if not 0 < price < 1:
        raise ValueError(f"price must be in (0, 1), got {price}")
    resp = private(account, "/v1/prediction-markets/order", {
        "symbol": symbol,
        "orderType": "limit",
        "side": side,
        "outcome": outcome,
        "quantity": str(qty),
        "price": f"{price:.{PRICE_DECIMALS}f}",
        "timeInForce": "good-til-cancel",
    })
    return str(resp["orderId"])


def cancel_order(account: str, order_id: str) -> None:
    private(account, "/v1/prediction-markets/order/cancel", {"orderId": int(order_id)})


def get_positions(account: str) -> list[dict]:
    return private(account, "/v1/prediction-markets/positions").get("positions", [])


def get_active_orders(account: str, symbol: str | None = None) -> list[dict]:
    fields = {"symbol": symbol} if symbol else {}
    return private(account, "/v1/prediction-markets/orders/active", fields).get("orders", [])


def get_order_history(account: str, symbol: str | None = None) -> list[dict]:
    fields = {"symbol": symbol} if symbol else {}
    return private(account, "/v1/prediction-markets/orders/history", fields).get("orders", [])


__all__ = ["get_events", "get_book", "place_order", "cancel_order", "get_positions",
           "get_active_orders", "get_order_history", "PROD_URL", "SANDBOX_URL"]
