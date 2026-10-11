<!-- AI-generated with Claude (Anthropic). -->
# Weather hedging on autopilot: onboarding

`onboard.py` turns a business's website into a weather-exposure profile and upserts it into `data/businesses.json`.

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

Store the Context.dev API key in the OS keychain (prompts for the value, nothing hits shell history):

```bash
.venv/bin/python -m keyring set contextdev api_key
```

## Usage

```bash
.venv/bin/python onboard.py https://www.example-ramen.com
.venv/bin/python onboard.py example-ramen.com --refresh   # bypass cache/
.venv/bin/python onboard.py starbucks.com --city "Los Angeles, CA"   # pick the branch city
.venv/bin/python onboard.py dkramen.com --annual-revenue 1500000     # size exposure to revenue
```

Prints the profile JSON to stdout, logs to stderr. Exit codes: `0` ok, `1` unexpected error, `2` config/input error (missing key, bad URL, no data).

## What it does

1. **Context.dev**: brand lookup by domain (name, logo, address, industry), Map to find a `menu`/`products`/`shop` page, scrape homepage and menu page as markdown.
2. **Classify**: weighted keyword hits over brand description and scraped text. Confidence = winning side's share of total score. Below 0.6 the side is `needs_review`.
3. **Sensitivity**: `BUSINESS_TYPES` at the top of `onboard.py` sets keywords and `baseline_temp_f` per type. With `--annual-revenue`, `dollars_per_degree = annual_revenue / 365 * revenue_drop_pct_per_degree`; without it, the type's flat `dollars_per_degree` default is used. `dollars_per_degree_source` says which. The percentages are placeholder guesses; edit them there.
4. **Location**: `--city` if given, else the brand address, else the most-cited "City, ST 12345" on the homepage, menu, or locations page. `location_source` records which (`cli`, `brand`, `site_text`).
5. **Gemini city**: nearest active Gemini weather city by haversine distance. Gemini cities and the business city are geocoded with Open-Meteo; Los Angeles is pinned to the LAX station.
6. **Write**: upsert by `domain` into `data/businesses.json`.

## Caching

Every Context.dev, Gemini, and Open-Meteo response is cached in `cache/`, keyed by request. `cache/` is committed so the demo businesses run without an API key or network. It contains API responses only, never the key. Repeat runs are served from disk in well under a second. The first run geocodes ~49 Gemini cities and takes about a minute; warm the cache before a demo.

## Limits

- Brand profiles for small shops often have no address. Chains with many cities need `--city`; otherwise they map to whichever city the site lists most.
- Profiles are keyed by `domain`, so two branches of one chain overwrite each other.
- Open-Meteo geocodes city names, not street addresses, so `lat`/`lon` are city centroids.

## Profile schema

`domain, name, logo_url, address, lat, lon, side, confidence, reason_codes, business_type, baseline_temp_f, annual_revenue, dollars_per_degree, dollars_per_degree_source, gemini_city, distance_miles, location_source, menu_url, onboarded_at`
