# Weather Hedging Agents on Gemini Prediction Markets

## TL;DR

Small businesses lose money when the weather goes against them. We built two AI agents that trade weather contracts on Gemini's prediction markets so the business can buy protection.

Think of a **weather insurance booth**:

- **Market maker (account 1, `mm`)** runs the booth. It always posts two prices for a weather contract, what it will pay and what it will sell for, and earns the small gap between them.
- **Ice cream shop (account 2, `shop`)** is the customer. It buys "it'll be cold" contracts. If the day is cold, each contract pays $1, which makes up for the ice cream it didn't sell.

A weather contract looks like *"NYC high temperature will be 61°F or below on Oct 12"*. It pays $1 if true and $0 if not. Its price (say $0.40) is the market's estimate of the chance it happens (40%).

### What's real vs. simulated

Gemini's **sandbox** (fake money) has no weather contracts. Gemini's **production** site (real money) does. So:

| Piece | Source |
|---|---|
| Weather contracts (names, temperature ranges, dates) | Real, read from Gemini production (free, public) |
| Weather forecast | Stub for now; teammate is building the real one from NWS data |
| Agents trading weather contracts with each other | **Simulated** on our own practice exchange (`mock_book.py`) |
| Placing and filling real orders through Gemini's API | **Live** on the Gemini sandbox, using crypto contracts |

The agents' code is identical in both cases. `MODE=mock` or `MODE=sandbox` in `backend/.env` picks the exchange.

### One Gemini rule to know

**You can't sell a contract you don't own.** To sell "YES, it'll be cold", the market maker instead *buys* "NO, it won't be cold" at (1 − price). Financially it comes to the same thing, and a YES buyer and a NO buyer are matched together (their prices add up to $1). That's why the market maker's holdings show up as NO contracts.

### What exists so far

| File | What it does |
|---|---|
| `backend/gemini_client.py` | Talks to Gemini's sandbox as either account: list contracts, read prices, place and cancel orders, check holdings |
| `backend/mock_book.py` | Our practice exchange: same functions and same rules, running in memory |
| `backend/market.py` | **What the agents import.** Switches between the two based on `MODE` |
| `backend/forecast.py` | Stub forecast. **Teammate replaces this** with the real model |
| `backend/scripts/` | `list_markets.py`, `check_accounts.py`, `test_client.py`, `test_mock_book.py` |

So far the accounts have only made a test trade: the shop bought 1 YES for $0.87 and the market maker bought the matching NO for $0.13, on a sandbox SOL contract. The agents themselves come next.

### What's next

1. **Market maker agent:** every few seconds, reads the forecast and posts prices around it (40% chance → buy at $0.37, sell at $0.43).
2. **Shop agent:** estimates what a cold day costs the shop (say $300) and buys enough "cold" contracts to cover it, within a budget.
3. **API + website:** the business describes itself in plain English, sees the forecast, the prices and the hedge, and compares a hot day with a cold day.

See [`CLAUDE.md`](CLAUDE.md) for the full spec, current status, and API findings.

## Setup

```bash
cd backend
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env   # ask Jason for the values; never commit .env
.venv/bin/python scripts/test_mock_book.py   # offline, should end with ALL MOCK BOOK CHECKS PASSED
.venv/bin/python scripts/check_accounts.py   # needs .env; both accounts accepted + $100k
```

## Onboarding, pooling, and hedge sizing (Satya)

<!-- AI-generated with Claude (Anthropic). -->
All commands run from `backend/`. Keys live in the OS keychain, not `.env`: Context.dev (`contextdev`/`api_key`) and Supabase (`supabase`/`secret_key`). Tables are in `backend/supabase/schema.sql`.

`backend/onboard.py` turns a business's website into a weather-exposure profile and upserts it into `data/businesses.json`.

### Setup

```bash
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

Store the Context.dev API key in the OS keychain (prompts for the value, nothing hits shell history):

```bash
.venv/bin/python -m keyring set contextdev api_key
```

### Usage

```bash
.venv/bin/python onboard.py https://www.example-ramen.com
.venv/bin/python onboard.py example-ramen.com --refresh   # bypass cache/
.venv/bin/python onboard.py starbucks.com --city "Los Angeles, CA"   # pick the branch city
.venv/bin/python onboard.py dkramen.com --annual-revenue 1500000     # size exposure to revenue
```

Prints the profile JSON to stdout, logs to stderr. Exit codes: `0` ok, `1` unexpected error, `2` config/input error (missing key, bad URL, no data).

### What it does

1. **Context.dev**: brand lookup by domain (name, logo, address, industry), Map to find a `menu`/`products`/`shop` page, scrape homepage and menu page as markdown.
2. **Classify**: weighted keyword hits over brand description and scraped text. Confidence = winning side's share of total score. Below 0.6 the side is `needs_review`.
3. **Sensitivity**: `BUSINESS_TYPES` at the top of `onboard.py` sets keywords and `baseline_temp_f` per type. With `--annual-revenue`, `dollars_per_degree = annual_revenue / 365 * revenue_drop_pct_per_degree`; without it, the type's flat `dollars_per_degree` default is used. `dollars_per_degree_source` says which. The percentages are placeholder guesses; edit them there.
4. **Location**: `--city` if given, else the brand address, else the most-cited "City, ST 12345" on the homepage, menu, or locations page. `location_source` records which (`cli`, `brand`, `site_text`).
5. **Gemini city**: nearest active Gemini weather city by haversine distance. Gemini cities and the business city are geocoded with Open-Meteo; Los Angeles is pinned to the LAX station.
6. **Write**: upsert by `domain` into `data/businesses.json`.

### Caching

Every Context.dev, Gemini, and Open-Meteo response is cached in `cache/`, keyed by request. `cache/` is committed so the demo businesses run without an API key or network. It contains API responses only, never the key. Repeat runs are served from disk in well under a second. The first run geocodes ~49 Gemini cities and takes about a minute; warm the cache before a demo.

### Limits

- Brand profiles for small shops often have no address. Chains with many cities need `--city`; otherwise they map to whichever city the site lists most.
- Profiles are keyed by `domain`, so two branches of one chain overwrite each other.
- Open-Meteo geocodes city names, not street addresses, so `lat`/`lon` are city centroids.

### Profile schema

`domain, name, logo_url, address, lat, lon, side, confidence, reason_codes, business_type, baseline_temp_f, annual_revenue, dollars_per_degree, dollars_per_degree_source, gemini_city, distance_miles, location_source, menu_url, onboarded_at`

### Hedging: `hedge.py`

```bash
.venv/bin/python hedge.py                                  # Los Angeles, latest open market
.venv/bin/python hedge.py --city "Los Angeles" --date 2026-10-11
```

Reads `data/businesses.json`, writes a plan to `data/hedge_plans.json` (upsert by city + date), prints it as JSON.

**Model.** Each business's daily profit is linear in the day's high: heat_hurt loses `dollars_per_degree` per °F above baseline and gains below; cold_hurt is the mirror. Summing a city's businesses cancels opposite exposures, leaving `net_dollars_per_degree`.

**Odds.** Gemini weather markets are thin; most buckets have no quote. Bucket probabilities come from the Open-Meteo GFS ensemble (31 members) at the station. `price` is the market ask when quoted, else the model probability (`price_source` says which). `edge` = model probability minus price.

**Hedge.** For each bucket where the pool does worse than its expected P&L, buy YES contracts ($1 payout) to cover the shortfall. `hedge_cost_standalone` is the cost if each business hedged alone; `netting_savings` is the difference.

**Backtest.** Last 365 days of daily highs (Open-Meteo archive) at the station: daily P&L spread and worst day, unhedged vs hedged at fair price.

**Limits.** Forecast and history are gridded model data, not the NWS station report Gemini settles on. Unquoted buckets can't actually be bought at the model price. Backtest assumes fair-price hedges with no spread.
