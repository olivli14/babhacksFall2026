"""Parse Gemini weather contracts and price them from forecast.prob_above.

Ticker format (docs: Weather Ticker Format): GEMI-WXHIGH-{LOC}-{YYMMDDHHmm}-{LO61|62TO63|HI70}
All bounds are inclusive whole °F, so a contract pays if lo <= high <= hi.
"""
import re
from datetime import datetime, timedelta, timezone

import market
from forecast import prob_above

TICKER_RE = re.compile(r"^GEMI-(WX[A-Z]+)-([A-Z]{2,4})-(\d{10})-(LO\d+|\d+TO\d+|HI\d+)$")

# Profile location text -> Gemini location code (codes as listed in production).
LOCATION_CODES = {"new york": "NYC", "nyc": "NYC", "chicago": "CHI", "los angeles": "LA",
                  "miami": "MIA", "boston": "BOS", "austin": "AUS", "houston": "HOU",
                  "san diego": "SAN", "washington": "DCA", "seattle": "SEA", "denver": "DEN"}


def location_code(location: str) -> str:
    loc = location.strip().lower()
    for name, code in LOCATION_CODES.items():
        if name in loc:
            return code
    return location.strip().upper()


def parse(symbol: str) -> dict:
    m = TICKER_RE.match(symbol)
    if not m:
        raise ValueError(f"Not a weather ticker: {symbol}")
    etype, loc, expiry, strike = m.groups()
    exp = datetime.strptime(expiry, "%y%m%d%H%M").replace(tzinfo=timezone.utc)
    if strike.startswith("LO"):
        lo, hi = None, int(strike[2:])
    elif strike.startswith("HI"):
        lo, hi = int(strike[2:]), None
    else:
        lo, hi = (int(x) for x in strike.split("TO"))
    return {"symbol": symbol, "type": etype, "location": loc, "expiry": exp,
            # Expiry is 03:59 UTC the day after the observed day.
            "date": (exp - timedelta(days=1)).date().isoformat(),
            "strike": strike, "lo": lo, "hi": hi}


def fair_value(symbol: str) -> float:
    """P(lo <= high <= hi) from the forecast."""
    c = parse(symbol)
    p_ge_lo = 1.0 if c["lo"] is None else prob_above(c["location"], c["lo"], c["date"])
    p_gt_hi = 0.0 if c["hi"] is None else prob_above(c["location"], c["hi"] + 1, c["date"])
    return min(max(p_ge_lo - p_gt_hi, 0.0), 1.0)


def representative_temp(c: dict) -> float:
    """A single temperature to stand in for the bucket (tails extend 2°F out)."""
    if c["lo"] is None:
        return c["hi"] - 2
    if c["hi"] is None:
        return c["lo"] + 2
    return (c["lo"] + c["hi"]) / 2


def pays_out(c: dict, temp_f: float) -> bool:
    t = round(temp_f)
    return (c["lo"] is None or t >= c["lo"]) and (c["hi"] is None or t <= c["hi"])


def find_event(location: str, date: str | None = None) -> dict:
    """The WXHIGH event for a location; latest-expiring one if no date given."""
    code = location_code(location)
    events = [e for e in market.get_events("Weather")
              if e.get("ticker", "").startswith(f"WXHIGH-{code}-")]
    if date:
        events = [e for e in events
                  if parse(e["contracts"][0]["instrumentSymbol"])["date"] == date]
    if not events:
        raise LookupError(f"No active WXHIGH event for {location} ({code}) {date or ''}")
    return max(events, key=lambda e: e["ticker"])


def event_symbols(event: dict) -> list[str]:
    """Contract symbols ordered from coldest to hottest bucket."""
    cs = [parse(c["instrumentSymbol"]) for c in event["contracts"]
          if c.get("marketState", "open") == "open"]
    cs.sort(key=lambda c: c["hi"] if c["hi"] is not None else 10_000)
    return [c["symbol"] for c in cs]
