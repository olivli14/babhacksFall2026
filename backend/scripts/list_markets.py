"""List active prediction-market events on Gemini sandbox and production.

Prints a count by category and every weather/temperature event with its contracts.
Public endpoint, no API key needed.

Usage: python scripts/list_markets.py
"""
import re
from collections import Counter

import requests

HOSTS = {
    "sandbox": "https://api.sandbox.gemini.com",
    "production": "https://api.gemini.com",
}
PAGE = 500  # API max per the OpenAPI spec
WEATHER_RE = re.compile(r"weather|temperature|°F|WXHIGH|WXLOW", re.I)


def fetch_active_events(base: str) -> list[dict]:
    events, offset = [], 0
    while True:
        r = requests.get(
            f"{base}/v1/prediction-markets/events",
            params={"status": "active", "limit": PAGE, "offset": offset},
            timeout=30,
        )
        r.raise_for_status()
        body = r.json()
        batch = body.get("data", [])
        events.extend(batch)
        total = body.get("pagination", {}).get("total", 0)
        offset += len(batch)
        if not batch or offset >= total:
            return events


def is_weather(ev: dict) -> bool:
    return (ev.get("category") == "Weather"
            or bool(WEATHER_RE.search(f"{ev.get('title', '')} {ev.get('ticker', '')}")))


def report(name: str, base: str) -> None:
    print(f"\n=== {name.upper()} ({base}) ===")
    events = fetch_active_events(base)
    print(f"{len(events)} active events")
    for cat, n in Counter(e.get("category", "?") for e in events).most_common():
        print(f"  {cat:<30} {n}")

    weather = [e for e in events if is_weather(e)]
    print(f"\nWeather/temperature events: {len(weather)}")
    for ev in weather:
        print(f"  - [{ev.get('ticker')}] {ev.get('title')}")
        for c in ev.get("contracts", []):
            p = c.get("prices", {})
            print(f"      {c.get('instrumentSymbol'):<40} {c.get('label', ''):<20} "
                  f"state={c.get('marketState')} bid={p.get('bestBid')} ask={p.get('bestAsk')}")


if __name__ == "__main__":
    for name, base in HOSTS.items():
        report(name, base)
