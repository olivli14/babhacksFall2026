#!/usr/bin/env python3
# AI-generated with Claude (Anthropic). Review before relying on it.
"""Onboard a business from its website URL into data/businesses.json.

Usage: python onboard.py <url> [--refresh] [--city "City, ST"] [--annual-revenue USD]
"""
import argparse
import hashlib
import json
import math
import re
import sys
import time
import warnings
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

warnings.filterwarnings("ignore", message="urllib3 v2 only supports OpenSSL")

import keyring  # noqa: E402
import requests  # noqa: E402
from context.dev import ContextDev  # noqa: E402

import db  # noqa: E402

# ---------------------------------------------------------------------------
# Config: tweak these
# ---------------------------------------------------------------------------

# Business types. side: which weather hurts. Keywords: phrase -> weight.
# baseline_temp_f: daily high where the business is neutral.
# revenue_drop_pct_per_degree: share of daily revenue lost per degree F past
# baseline (above baseline for heat_hurt, below for cold_hurt). Used when
# --annual-revenue is given: dollars_per_degree = annual_revenue / 365 * pct.
# dollars_per_degree: flat fallback when revenue is unknown.
BUSINESS_TYPES = {
    "noodle_soup": {
        "side": "heat_hurt", "baseline_temp_f": 72, "dollars_per_degree": 60, "revenue_drop_pct_per_degree": 0.015,
        "keywords": {"ramen": 3, "pho": 3, "noodle": 2, "soup": 1, "hot pot": 3, "udon": 2, "tonkotsu": 2},
    },
    "hot_coffee_bakery": {
        "side": "heat_hurt", "baseline_temp_f": 75, "dollars_per_degree": 30, "revenue_drop_pct_per_degree": 0.010,
        "keywords": {"hot coffee": 3, "espresso": 2, "bakery": 2, "latte": 1, "pastry": 1, "pastries": 1},
    },
    "perishable_shipper": {
        "side": "heat_hurt", "baseline_temp_f": 80, "dollars_per_degree": 80, "revenue_drop_pct_per_degree": 0.020,
        "keywords": {"perishable shipping": 3, "meal kit": 3, "shipped cold": 3, "ice packs": 3, "perishable": 2},
    },
    "frozen_dessert": {
        "side": "cold_hurt", "baseline_temp_f": 78, "dollars_per_degree": 50, "revenue_drop_pct_per_degree": 0.025,
        "keywords": {"ice cream": 3, "gelato": 3, "frozen yogurt": 3, "shaved ice": 3, "popsicle": 2, "sorbet": 1, "scoop": 1},
    },
    "cold_drinks": {
        "side": "cold_hurt", "baseline_temp_f": 75, "dollars_per_degree": 40, "revenue_drop_pct_per_degree": 0.020,
        "keywords": {"boba": 3, "bubble tea": 3, "smoothie": 2, "cold brew": 2, "juice": 1, "iced": 1},
    },
}

CONFIDENCE_THRESHOLD = 0.6
MAX_HITS_PER_KEYWORD = 5  # cap so one repeated word can't dominate
MENU_HINTS = ["menu", "products", "shop"]  # priority order
LOCATION_HINTS = ["locations", "location", "visit", "find-us", "stores", "contact"]  # priority order

# Gemini stations whose coordinates we pin instead of geocoding the city name.
STATION_OVERRIDES = {
    "Los Angeles": {"lat": 33.9425, "lon": -118.4081, "station": "LAX"},
}
# Gemini title names that Open-Meteo won't geocode as written.
CITY_ALIASES = {"NYC": "New York", "Washington DC": "Washington"}

GEMINI_EVENTS_URL = "https://api.gemini.com/v1/prediction-markets/events"
GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"

ROOT = Path(__file__).resolve().parent
CACHE_DIR = ROOT / "cache"
DATA_FILE = ROOT / "data" / "businesses.json"

US_STATES = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas", "CA": "California",
    "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware", "DC": "District of Columbia",
    "FL": "Florida", "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho", "IL": "Illinois",
    "IN": "Indiana", "IA": "Iowa", "KS": "Kansas", "KY": "Kentucky", "LA": "Louisiana",
    "ME": "Maine", "MD": "Maryland", "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota",
    "MS": "Mississippi", "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada",
    "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York",
    "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma", "OR": "Oregon",
    "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina", "SD": "South Dakota",
    "TN": "Tennessee", "TX": "Texas", "UT": "Utah", "VT": "Vermont", "VA": "Virginia",
    "WA": "Washington", "WV": "West Virginia", "WI": "Wisconsin", "WY": "Wyoming",
}


class OnboardError(Exception):
    pass


def log(msg):
    print(msg, file=sys.stderr)


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------

REFRESH = False


def cached(key, fetch):
    """Return the cached JSON for key, or call fetch() and cache its result."""
    path = CACHE_DIR / (hashlib.sha1(key.encode()).hexdigest() + ".json")
    if not REFRESH and path.exists():
        return json.loads(path.read_text())["response"]
    result = fetch()
    CACHE_DIR.mkdir(exist_ok=True)
    path.write_text(json.dumps({"key": key, "response": result}))
    return result


def http_get_json(url, params):
    key = url + "?" + "&".join(f"{k}={v}" for k, v in sorted(params.items()))

    def fetch():
        r = requests.get(url, params=params, timeout=30)
        r.raise_for_status()
        return r.json()

    return cached(key, fetch)


# ---------------------------------------------------------------------------
# Context.dev
# ---------------------------------------------------------------------------

_client = None


def client():
    global _client
    if _client is None:
        api_key = keyring.get_password("contextdev", "api_key")
        if not api_key:
            raise OnboardError(
                "Context.dev API key not found in keychain. Run: "
                "python -m keyring set contextdev api_key"
            )
        _client = ContextDev(api_key=api_key, timeout=90.0, max_retries=1)
    return _client


def get_brand(domain):
    def fetch():
        try:
            resp = client().brand.retrieve(
                type="by_domain", domain=domain,
                timeout_opts={"milliseconds": 60000, "behavior": "return-partial"},
            )
            return resp.to_dict()
        except Exception as e:  # NOT_FOUND comes back as a 400
            log(f"warn: brand lookup failed for {domain}: {e}")
            return {}

    return (cached(f"contextdev:brand:{domain}", fetch) or {}).get("brand") or {}


def map_pages(domain):
    """Return (menu_url, location_url) picked from the site's URL map."""
    def fetch():
        try:
            resp = client().web.map_urls(
                domain=domain, max_links=200, url_regex="|".join(MENU_HINTS + LOCATION_HINTS),
            )
            return resp.to_dict()
        except Exception as e:
            log(f"warn: map failed for {domain}: {e}")
            return {}

    urls = [u.get("url", "") for u in cached(f"contextdev:map:{domain}:v2", fetch).get("urls", [])]

    def pick(hints):
        for hint in hints:
            hits = sorted((u for u in urls if hint in urlparse(u).path.lower()), key=len)
            if hits:
                return hits[0]
        return None

    return pick(MENU_HINTS), pick(LOCATION_HINTS)


def scrape_markdown(url):
    def fetch():
        try:
            resp = client().web.scrape(url=url, formats={"markdown": True})
            return resp.to_dict()
        except Exception as e:
            log(f"warn: scrape failed for {url}: {e}")
            return {}

    md = cached(f"contextdev:scrape:{url}", fetch).get("markdown") or {}
    return md.get("data") or ""


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------

def classify(text):
    text = text.lower()
    side_scores = {"heat_hurt": 0.0, "cold_hurt": 0.0}
    type_scores = {}
    hits = []  # (score, keyword, count)
    for btype, cfg in BUSINESS_TYPES.items():
        for kw, weight in cfg["keywords"].items():
            n = len(re.findall(r"\b" + re.escape(kw) + r"s?\b", text))
            if not n:
                continue
            score = weight * min(n, MAX_HITS_PER_KEYWORD)
            side_scores[cfg["side"]] += score
            type_scores[btype] = type_scores.get(btype, 0) + score
            hits.append((score, kw, n, cfg["side"]))

    total = sum(side_scores.values())
    if total == 0:
        return {"side": "needs_review", "confidence": 0.0, "reason_codes": [], "business_type": None}

    winner = max(side_scores, key=side_scores.get)
    confidence = round(side_scores[winner] / total, 3)
    btype = max((t for t in type_scores if BUSINESS_TYPES[t]["side"] == winner), key=type_scores.get)
    reasons = [f"{kw} x{n}" for _, kw, n, side in sorted(hits, reverse=True) if side == winner][:5]
    side = winner if confidence >= CONFIDENCE_THRESHOLD else "needs_review"
    return {"side": side, "confidence": confidence, "reason_codes": reasons, "business_type": btype}


# ---------------------------------------------------------------------------
# Geography
# ---------------------------------------------------------------------------

def haversine_miles(lat1, lon1, lat2, lon2):
    r = 3958.8
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def geocode(city, state_code=None, country_code="US", strict=False):
    """Geocode a city name, preferring a result in the given state.

    strict=True returns None unless a result is in that state.
    """
    data = http_get_json(GEOCODE_URL, {"name": city, "count": 10, "language": "en", "format": "json"})
    results = [r for r in data.get("results", []) if not country_code or r.get("country_code") == country_code]
    if state_code and state_code in US_STATES:
        in_state = [r for r in results if r.get("admin1") == US_STATES[state_code]]
        results = in_state if (in_state or strict) else results
    if not results:
        return None
    best = max(results, key=lambda r: r.get("population") or 0)
    return best["latitude"], best["longitude"]


CITY_STATE_ZIP = re.compile(r"([A-Z][A-Za-z.' ]{1,40}),\s*([A-Z]{2})\.?,?\s+\d{5}\b")


def city_from_text(text):
    """Most-cited US 'City, ST 12345' in the text, validated by geocoding."""
    counts = {}
    for raw, state in CITY_STATE_ZIP.findall(text):
        if state not in US_STATES:
            continue
        words = raw.split()
        # Trim leading junk ("Visit us Los Angeles") until the tail geocodes.
        for i in range(max(0, len(words) - 4), len(words)):
            city = " ".join(words[i:]).strip(" .")
            if city and geocode(city, state, "US", strict=True):
                counts[(city, state)] = counts.get((city, state), 0) + 1
                break
    if not counts:
        return None
    return max(counts, key=counts.get)


def gemini_stations():
    """Return [{city, state, lat, lon}] for every active Gemini weather city."""
    data = http_get_json(GEMINI_EVENTS_URL, {"status": "active", "category": "Weather", "limit": 200})
    stations = {}
    for ev in data.get("data", []):
        m = re.search(r"Highest temperature in (.+?) on ", ev.get("title", ""))
        if not m or m.group(1) in stations:
            continue
        city = m.group(1)
        state = None
        try:
            desc = ev["contracts"][0]["description"]["content"][0]["value"]
            sm = re.search(r"recorded at .+?, ([A-Z]{2}) on ", desc)
            state = sm.group(1) if sm else None
        except (KeyError, IndexError, TypeError):
            pass
        if city in STATION_OVERRIDES:
            o = STATION_OVERRIDES[city]
            stations[city] = {"city": city, "state": state, "lat": o["lat"], "lon": o["lon"]}
            continue
        coords = geocode(CITY_ALIASES.get(city, city), state)
        if coords:
            stations[city] = {"city": city, "state": state, "lat": coords[0], "lon": coords[1]}
        else:
            log(f"warn: could not geocode Gemini city {city}")
    if not stations:
        raise OnboardError("no active Gemini weather cities found")
    return list(stations.values())


# ---------------------------------------------------------------------------
# Main flow
# ---------------------------------------------------------------------------

def normalize_domain(url):
    if "://" not in url:
        url = "https://" + url
    host = urlparse(url).netloc.lower().split(":")[0]
    if host.startswith("www."):
        host = host[4:]
    if not host or "." not in host:
        raise OnboardError(f"invalid URL: {url}")
    return host, url


def pick_logo(brand):
    logos = brand.get("logos") or []
    for want in ("logo", "icon"):
        for lg in logos:
            if lg.get("type") == want and lg.get("url"):
                return lg["url"]
    return logos[0]["url"] if logos and logos[0].get("url") else None


def onboard(url, city_override=None, annual_revenue=None):
    domain, url = normalize_domain(url)
    brand = get_brand(domain)

    home_md = scrape_markdown(url)
    menu_url, location_url = map_pages(domain)
    same_as_home = lambda u: u and u.rstrip("/") == url.rstrip("/")
    menu_md = scrape_markdown(menu_url) if menu_url and not same_as_home(menu_url) else ""
    if not brand and not home_md:
        raise OnboardError(f"no brand data or homepage content for {domain}")

    industries = " ".join(
        f"{i.get('industry', '')} {i.get('subindustry', '')}"
        for i in (brand.get("industries") or {}).get("eic", []) or []
    )
    text = "\n".join([brand.get("title") or "", brand.get("description") or "", industries, home_md, menu_md])
    cls = classify(text)

    addr = brand.get("address") or {}
    address = ", ".join(
        p for p in [addr.get("street"), addr.get("city"), addr.get("state_code") or addr.get("state_province"),
                    addr.get("postal_code")] if p
    ) or None
    lat = lon = None
    location_source = None
    if city_override:
        city, _, state = city_override.partition(",")
        coords = geocode(city.strip(), state.strip().upper() or None)
        if not coords:
            raise OnboardError(f"could not geocode --city {city_override!r}")
        lat, lon = coords
        address, location_source = city_override, "cli"
    if lat is None and addr.get("city"):
        coords = geocode(addr["city"], addr.get("state_code"), addr.get("country_code") or None)
        if coords:
            lat, lon = coords
            location_source = "brand"
    if lat is None:
        site_text = home_md + "\n" + menu_md
        if location_url and not same_as_home(location_url):
            site_text += "\n" + scrape_markdown(location_url)
        found = city_from_text(site_text)
        if found:
            lat, lon = geocode(*found)
            address, location_source = f"{found[0]}, {found[1]}", "site_text"
    if lat is None:
        log(f"warn: no usable address for {domain}; pass --city 'City, ST' to set one")

    gemini_city = distance = None
    if lat is not None:
        stations = gemini_stations()
        best = min(stations, key=lambda s: haversine_miles(lat, lon, s["lat"], s["lon"]))
        gemini_city = best["city"]
        distance = round(haversine_miles(lat, lon, best["lat"], best["lon"]), 1)

    sens = BUSINESS_TYPES[cls["business_type"]] if cls["business_type"] else {}
    dollars_per_degree, dpd_source = sens.get("dollars_per_degree"), "default"
    if annual_revenue and sens:
        dollars_per_degree = round(annual_revenue / 365 * sens["revenue_drop_pct_per_degree"], 2)
        dpd_source = "revenue"
    return {
        "domain": domain,
        "name": brand.get("title") or domain,
        "logo_url": pick_logo(brand),
        "address": address,
        "lat": lat,
        "lon": lon,
        "side": cls["side"],
        "confidence": cls["confidence"],
        "reason_codes": cls["reason_codes"],
        "business_type": cls["business_type"],
        "baseline_temp_f": sens.get("baseline_temp_f"),
        "annual_revenue": annual_revenue,
        "dollars_per_degree": dollars_per_degree,
        "dollars_per_degree_source": dpd_source if sens else None,
        "gemini_city": gemini_city,
        "distance_miles": distance,
        "location_source": location_source,
        "menu_url": menu_url,
        "onboarded_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def location_key(profile):
    return (profile.get("address") or "").strip().lower()


def upsert(profile):
    """Save to Supabase (businesses) and the local JSON mirror, keyed by domain + location."""
    key = (profile["domain"], location_key(profile))
    DATA_FILE.parent.mkdir(exist_ok=True)
    rows = json.loads(DATA_FILE.read_text()) if DATA_FILE.exists() else []
    rows = [r for r in rows if (r.get("domain"), location_key(r)) != key] + [profile]
    rows.sort(key=lambda r: (r["domain"], location_key(r)))
    DATA_FILE.write_text(json.dumps(rows, indent=2) + "\n")
    try:
        db.upsert("businesses", [{**profile, "location_key": key[1]}], on_conflict="domain,location_key")
    except Exception as e:
        log(f"warn: Supabase write to businesses failed: {e}")


def run(url, city=None, annual_revenue=None):
    """Record the raw input, onboard, save the profile, and mark the input ok/error."""
    input_id = None
    try:
        rows = db.insert("business_inputs", [{"url": url, "city": city, "annual_revenue": annual_revenue}])
        input_id = rows[0]["id"]
    except Exception as e:
        log(f"warn: Supabase write to business_inputs failed: {e}")

    def mark(values):
        if input_id is not None:
            try:
                db.update("business_inputs", {"id": input_id}, values)
            except Exception as e:
                log(f"warn: Supabase update of business_inputs failed: {e}")

    try:
        profile = onboard(url, city, annual_revenue)
        upsert(profile)
    except Exception as e:
        mark({"status": "error", "error": str(e)[:500]})
        raise
    mark({"status": "ok", "domain": profile["domain"]})
    return profile


def main():
    global REFRESH
    ap = argparse.ArgumentParser(description="Onboard a business into data/businesses.json")
    ap.add_argument("url")
    ap.add_argument("--refresh", action="store_true", help="bypass cache/")
    ap.add_argument("--city", help="override location, e.g. 'Los Angeles, CA' (for one branch of a chain)")
    ap.add_argument("--annual-revenue", type=float, help="annual revenue in USD; scales dollars_per_degree")
    args = ap.parse_args()
    REFRESH = args.refresh
    if args.annual_revenue is not None and args.annual_revenue <= 0:
        log("error: --annual-revenue must be positive")
        return 2

    start = time.time()
    try:
        profile = run(args.url, args.city, args.annual_revenue)
    except OnboardError as e:
        log(f"error: {e}")
        return 2
    except Exception as e:
        log(f"error: {type(e).__name__}: {e}")
        return 1
    print(json.dumps(profile, indent=2))
    log(f"done in {time.time() - start:.2f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
