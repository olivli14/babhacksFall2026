# Project: Weather Hedging Agents on Gemini Prediction Markets

Hackathon project for the "Best Use of Gemini Prediction API" track. We have about one day. A demo that works smoothly matters more than generality or polish.

## The idea in one paragraph

Small businesses lose revenue when the weather goes against them. An ice cream shop sells less on cold days, so it can **buy a contract that pays out if it's cold** to offset those lost sales. That's a hedge, not a bet. We build two AI agents that trade with each other in Gemini's prediction market sandbox:

1. **Market maker agent**: prices temperature contracts from weather forecasts and continuously quotes bids and asks.
2. **Ice cream shop agent**: models how temperature affects its revenue, computes its exposure, and buys contracts sized to cover the expected loss, within a premium budget.

A web app lets a business describe how weather affects it, then shows the forecast, the market maker's quotes, the hedge filling, and P&L for a hot-day scenario and a cold-day scenario. Judges open it from a public link.

## Team and ownership

- **Jason (me, the one you're working with)**: the Gemini API wrapper (`gemini_client.py`), the mock order book, the shop agent, the intake, the FastAPI layer, the Next.js frontend, and deployment.
- **Teammate**: the forecast and probability module (`forecast.py`) and the market maker's pricing logic. **Do not implement the real forecast model.** Create only the stub described below so the rest of the code can run.

## Current status (keep this section updated)

_Last updated 2026-10-11._

| Step | Status | How to test (from `/backend`, after `python3 -m venv .venv && .venv/bin/pip install -r requirements.txt`) |
|---|---|---|
| 1. `scripts/list_markets.py` | ✅ done | `.venv/bin/python scripts/list_markets.py`: sandbox has 0 weather events; production has ~98 |
| 2. Request signing + terms check | ✅ done | `.venv/bin/python scripts/check_accounts.py`: both accounts `hasAcceptedLatest: True`, $100k USD each |
| 3. `gemini_client.py` | ✅ done | `.venv/bin/python scripts/test_client.py`: places, cancels and fills a real 1-contract trade between `mm` and `shop` on a sandbox crypto contract |
| 4. `mock_book.py` + `market.py` | ✅ done | `.venv/bin/python scripts/test_mock_book.py` ends with `ALL MOCK BOOK CHECKS PASSED` |
| 5. `forecast.py` stub | ✅ done (stub) | `.venv/bin/python -c "from forecast import prob_above; print(prob_above('NYC', 66, '2026-10-12'))"` prints ~0.5. Normal curve around a fixed 66°F mean (sd 5°F, small jitter); location and date are ignored. **Teammate replaces it.** |
| 6. `mm_agent.py`, `shop_agent.py`, `contracts.py` | ✅ done (branch `agents`) | `MODE=mock .venv/bin/python mm_agent.py` prints bid/ask for all 6 NYC buckets. `MODE=mock .venv/bin/python shop_agent.py` prints a recommendation, 3 filled orders, and hot/cold scenarios |
| 6b. Live sandbox run of both agents | ✅ done | `.venv/bin/python scripts/live_demo.py 300`: real `MarketMaker` + shop sizing on a sandbox crypto contract for 300 s, then cancels everything. Fair value = mid of other traders' quotes |
| 7. `api.py` (FastAPI) | ✅ done | `.venv/bin/uvicorn api:app --port 8000`, then `curl localhost:8000/health` returns `{"mode":"mock","mm_running":true,…,"sandbox_ok":true}`. See endpoint notes below |
| 8. Deploy backend to Railway | ✅ done | `curl https://api-production-2173.up.railway.app/health` returns `mode: mock, mm_running: true, sandbox_ok: true`. Railway project `weather-hedge`, service `api`; deploy with `cd backend && railway up --service api --ci`. Start command comes from the `RAILPACK_START_CMD` variable (railway.json alone was ignored) |
| 9. Next.js frontend | ✅ done | `cd frontend && npm run dev -- -p 3005` with `NEXT_PUBLIC_API_URL`. One page: profile, market, hedge, scenario toggle, live sandbox panel |
| 10. Deploy frontend to Vercel | next | |
| 11. Intake chat | not started (preset is enough for the demo) | |

**Backend files so far**
- `config.py`: loads `backend/.env` (template in `backend/.env.example`). Holds `MODE` and per-agent credentials.
- `gemini_auth.py`: `private(account, path, fields, method)` signs and sends private REST calls.
- `gemini_client.py`: the real sandbox implementation of the interface below.
- `mock_book.py`: the in-memory implementation of the same interface, with matching, positions and cash. It also has mock-only helpers: `get_trades()`, `get_cash()` and `reset()`.
- `contracts.py`: parses weather tickers (`LO68`, `69TO70`, `HI77`), `fair_value(symbol)` from `prob_above`, and finds a city's event. **Teammate: this is where forecast probabilities become contract prices.**
- `mm_agent.py`: `MarketMaker(symbols, MMConfig)` quotes every bucket of an event. `step()` runs one round; `start()`/`stop()` run it in a background thread. Pricing knobs are in `MMConfig`; the quote logic is in `quote()`.
- `shop_agent.py`: `recommend(profile)`, `execute(rec)`, `scenario(profile, rec, temp_f)`, and `ICE_CREAM_PRESET`. It buys a **strip**: YES on every bucket where the business loses money, each sized to that bucket's loss and scaled down evenly to fit the premium budget.
- `live.py`: `LiveRun` runs both agents on the real sandbox (used by `/live/start` and `scripts/live_demo.py`). The live market maker's fair value is the **production** mid for the same symbol, because every sandbox contract is also listed on production and sandbox books are usually empty. `cancel_all_open()` clears orders left behind by a crash; the API calls it on startup.
- `api.py`: the FastAPI app. The market maker quotes every bucket of the preset city's event from startup.
- **`market.py`: what agents should import** (`import market`). It re-exports either `gemini_client` or `mock_book` depending on `MODE`.

### What we learned (these override anything below that disagrees)
1. **The sandbox has no weather markets** in any status, even though "Weather" appears in its category list. The sandbox has crypto (BTC/ETH/SOL…) and commodities only. **Production has ~98 `WXHIGH` events** (about 50 cities, today and tomorrow). We go with the fallback plan below.
2. **Weather contracts are buckets, not just thresholds.** Each event has one `LO{T}` (≤T), several 2°F ranges `{A}TO{B}`, and one `HI{T}` (≥T), e.g. `GEMI-WXHIGH-NYC-2610120359-LO61`. A "pays if cold" hedge = **buy YES on the `LO{T}` contract**. `P(LO{T})` = `1 - prob_above(T + 1)` (bounds are inclusive and use whole °F).
3. **Location codes differ from the docs' table.** Production uses `NYC, CHI, LA, SAN, DCA, MIA, AUS, HOU, …`, not `MDW`/`LAX`. Always take symbols from `get_events()`, never build them by hand.
4. **No naked shorts.** "sell YES" is rejected unless you hold YES (`Cannot sell YES contracts. No YES position found.`). A YES buy matches a NO buy, and the two prices sum to $1. **So a flat market maker posts its ask as `buy NO @ (1 - ask)`.** Its short-YES inventory then shows up as a **NO position**. The mock book enforces the same rule.
5. **Order books are in YES space.** `get_book` returns YES bids and asks. A NO buy at q appears as a YES ask at 1-q.
6. Both API keys are **master keys**, and the sandbox requires an explicit `"account": "primary"` in every private payload (the docs say it's optional; it isn't). `config.py` adds it automatically. Each sandbox group is capped at 1 account, so the two agents use two separate sandbox logins.
7. Production book liquidity on weather contracts is thin (often no bid or ask), so don't rely on it for fair value.
8. **Gemini nets YES against NO** in the same account (a YES+NO pair redeems for $1). So positions show only the net side. `mock_book` does the same.
9. **Live run (2026-10-11, 5 min):** the shop's YES buy matched the market maker's ask on the sandbox. But a sandbox bot kept selling into the market maker's bid, and with `max_skew=0.03` it built up 50 YES. **Pricing to-do for teammate:** stronger inventory skew, an inventory limit, or stopping the bid past a max position.
10. **Sandbox liquidity comes and goes.** Bots quote only the contracts expiring within about the hour; later contracts have empty books. Every sandbox symbol also exists on production with real prices, so we price off production.
11. Gemini docs are available as markdown: `https://developer.gemini.com/llms.txt`. The OpenAPI spec is at `https://developer.gemini.com/specs/openapi/prediction-markets.yaml`.

## Stack and repo layout

```
/backend    Python 3.11+: agents, Gemini wrapper, forecast, FastAPI. Deployed on Railway.
/frontend   Next.js (TypeScript, App Router, Tailwind). Deployed on Vercel.
```

- **Backend:** `requests` for Gemini REST (use polling rather than WebSockets unless I ask otherwise) and FastAPI for the HTTP API the frontend calls. The market maker runs as a long-lived background loop in the same Railway service, started on FastAPI startup, because Vercel's serverless functions cannot host a loop that runs continuously.
- **Frontend:** a thin client. It holds no secrets and no trading logic, and it only calls the backend API. The backend URL comes from `NEXT_PUBLIC_API_URL`.
- Credentials go in `backend/.env`, loaded with `python-dotenv`, and are set as Railway environment variables in production. Never hardcode or print secrets, and never send them to the frontend.

## Gemini API facts (verify against the docs; do not guess)

The Gemini MCP server is connected. Check endpoint paths, request fields and response shapes against the official docs before writing code. If something below conflicts with the docs, the docs win, so tell me about the discrepancy.

- **Sandbox base URL:** `https://api.sandbox.gemini.com`. Production market data (`https://api.gemini.com`) is public and needs no key, which is useful for reading real contract definitions.
- **Market discovery (public):** `GET /v1/prediction-markets/events?status=active` returns events, and each event has a `contracts` array. Orders use the contract's `instrumentSymbol`. Yes/no is chosen with a separate outcome field, not by appending it to the symbol.
- **Auth for private endpoints:** headers `X-GEMINI-APIKEY`, `X-GEMINI-PAYLOAD` and `X-GEMINI-SIGNATURE`. The signature is a hex-encoded HMAC-SHA384 of the payload, signed with the API secret. The payload is a base64 JSON body that includes `request` (the path) and a strictly increasing `nonce`. Confirm the exact payload format in the docs.
- **The API key needs the Trader role.**
- **Prediction Markets terms must be accepted** before an account can trade, or orders fail with `TERMS_NOT_ACCEPTED`. There is a terms-status endpoint to check this.
- **Relevant private endpoints** (confirm their paths): place order, place batch orders (`POST /v1/prediction-markets/order/batch`, 1 to 20 orders), cancel order, get active orders, and positions (`POST /v1/prediction-markets/positions`).
- **Prices are in the 0 to 1 range**, meaning dollars per contract that pays $1.
- **Weather contracts** are temperature-threshold contracts (°F) tied to weather stations, using Gemini-specific location codes. These are different from airport codes and NWS office codes. Contracts resolve on National Weather Service data. Read the "Weather Ticker Format" page in the docs for the exact ticker structure.

## Confirmed: the sandbox does not list weather markets

Checked 2026-10-11: no weather events in the sandbox in any status. So:

1. Write a script, `scripts/list_markets.py`, that pulls active events from **both** the sandbox and production and prints a count by category and the titles of any weather or temperature events.
2. Every trading path must also work against a **mock order book** with the same interface. Set the mode in config: `MODE=sandbox` or `MODE=mock`.
3. If the sandbox has no weather markets, the demo plan is:
   - run the weather hedging story on the mock order book, using real NWS forecasts and real Gemini contract definitions taken from production, and
   - separately show the Gemini wrapper placing and filling real sandbox orders on whatever contract does exist (for example the BTC 5-minute contracts).

   The dashboard must clearly label which parts are live and which are simulated.

## We use two sandbox accounts

The market maker and the shop are separate accounts so they actually trade with each other. Credentials go in `.env`:

```
GEMINI_MM_API_KEY=
GEMINI_MM_API_SECRET=
GEMINI_MM_ACCOUNT=primary
GEMINI_SHOP_API_KEY=
GEMINI_SHOP_API_SECRET=
GEMINI_SHOP_ACCOUNT=primary
MODE=mock
```

Both accounts are set up: terms are accepted and each has $100k of sandbox USD. Ask Jason for the `.env` values; they are never committed.

## Interfaces (keep these stable; my teammate codes against them)

```python
# gemini_client.py  (also implemented by mock_book.py with identical signatures)
get_events(category: str | None = None) -> list[dict]
get_book(symbol: str) -> dict            # {"bids": [(price, qty), ...], "asks": [...]}
place_order(account: str, symbol: str, side: str, outcome: str,
            price: float, qty: int) -> str   # returns order_id; account is "mm" or "shop"
cancel_order(account: str, order_id: str) -> None
get_positions(account: str) -> list[dict]   # [{"symbol","outcome","totalQuantity","avgPrice"}, ...] (strings)
get_active_orders(account: str, symbol: str | None = None) -> list[dict]   # added; both implementations

# Import these via `import market`, not gemini_client/mock_book directly.
# In sandbox mode get_events() hits the sandbox; in mock mode it returns real production events.

# forecast.py  (teammate owns this; you create only a stub)
prob_above(location: str, threshold_f: float, date: str) -> float   # probability, 0 to 1
```

The stub `prob_above` can return a fixed or slightly random value around 0.5. Mark it clearly as a stub.

## Agent logic

**Market maker (`mm_agent.py`):** a loop that every N seconds:
1. gets the fair value from `prob_above`,
2. cancels its stale quotes,
3. posts a bid at fair value minus the half-spread and an ask at fair value plus the half-spread. The bid is `buy YES @ bid`. The ask is `buy NO @ (1 - ask)` (see "No naked shorts" above); only sell YES outright when holding YES,
4. skews both prices against its inventory (when long, lower both). Net inventory = YES quantity − NO quantity from `get_positions("mm")` for that symbol.

Make the spread, size and skew configurable. My teammate will refine the pricing; keep the structure simple and readable.

**Ice cream shop (`shop_agent.py`):**
1. Uses a sales model with configurable values: baseline daily revenue, and revenue lost per °F below a comfort threshold (for example 80°F).
2. Computes expected lost revenue across temperature scenarios, using `prob_above` at several thresholds.
3. Picks the contract that pays when it's cold and sizes the quantity so the payout covers the loss, capped by a premium budget.
4. Places the order and records the reasoning.
5. Produces a short plain-language explanation, for example: "Saturday has a 35% chance of a high under 72°F. Spending $40 to protect $300 of revenue."

**Business intake (`intake.py`):** this is the product's front door. A business owner describes in plain language how weather affects them (for example: "we sell about 40% less ice cream when it's under 70°F, and a normal Saturday is about $2k"). Use the Claude API (key in `.env` as `ANTHROPIC_API_KEY`) to turn that into a structured profile:

```python
{"business_type": str, "location": str, "baseline_revenue": float,
 "weather_variable": "temperature_high", "bad_direction": "below" | "above",
 "threshold_f": float, "loss_per_degree": float, "premium_budget": float}
```

- Ask Claude to return JSON only, and validate the JSON against this schema.
- If a required field is missing, ask the user one follow-up question rather than guessing.
- Show the parsed profile back to the user for confirmation before hedging.

The shop agent must take this profile as input, not hardcoded ice cream values, so the same flow works for, say, a ski rental shop (`bad_direction: "above"`). Keep the ice cream profile as a preset for a reliable demo.

**Backend API (`backend/api.py`, FastAPI):**

```
POST /intake          {messages}       -> {reply, profile | null}   # Claude-backed chat
POST /hedge           {profile}        -> {recommendation, explanation}
POST /hedge/execute   {profile}        -> {order_id, status}
GET  /market          ?symbol=         -> {fair_value, book, mm_quotes}
GET  /positions       ?account=        -> [...]
GET  /scenarios       ?profile_id=     -> {hot: {...}, cold: {...}}  # revenue, hedge P&L, net
GET  /health                           -> {mode, mm_running, sandbox_ok}
```

- Enable CORS for the Vercel domain and localhost only. (Done: `localhost:3000` plus the comma-separated `FRONTEND_ORIGINS` env var.)

**As built:**
- `/hedge` also returns `profile_id`, which `/scenarios` needs.
- `/market` without `symbol` returns every bucket as `contracts: [{symbol, bucket, lo, hi, fair_value, book, mm_quotes}]`.
- Extra endpoints:
  - `GET /presets` returns the ice cream profile.
  - `GET /live` returns the live sandbox run's status and log. It's public.
  - `POST /live/start {seconds}` and `POST /live/stop` require the header `X-Demo-Admin-Token: $DEMO_ADMIN_TOKEN`.
- `/intake` is a placeholder until step 11.
- Validation: `premium_budget` ≤ $1000 and any single order ≤ 2000 contracts.
- Every response includes `mode: "sandbox" | "mock"` so the UI can label it.

**Frontend (`/frontend`, Next.js), a single page:**
- a chat-style intake at the top, followed by the confirmed profile with an "Edit" option and an "Ice cream shop" preset button
- the forecast probability
- the market maker's current quotes and the order book
- the hedge recommendation, an "Execute hedge" button, the order status and the explanation
- a **scenario toggle (hot day / cold day)** showing revenue, hedge P&L and net result side by side. This is the core of the demo.
- a "LIVE SANDBOX" or "SIMULATED" badge on every panel
- Keep it clean and simple. Use polling (every 2 to 3 seconds) for the market panel.

## Deployment and public-link safety

- **Backend on Railway:** one always-on service (no free tier that sleeps) running uvicorn, with the market maker loop started on startup.
- **Frontend on Vercel**, with `NEXT_PUBLIC_API_URL` set to the Railway URL.
- The public link **defaults to `MODE=mock`**. Live sandbox trading is enabled only with a `DEMO_ADMIN_TOKEN` header that I send during the presentation.
- Rate-limit `/intake` per IP (for example, 20 messages per hour) and cap the size of a single hedge order.
- Check `/health` before demoing.

## Build order

All Python paths below are under `/backend`.

1. `scripts/list_markets.py`, then report what the sandbox and production list.
2. Request signing, plus a terms-status check for both accounts.
3. `gemini_client.py`: place, cancel and book first, then positions.
4. `mock_book.py` with the same interface, plus a simple matching engine so orders between the two agents actually fill.
5. The `forecast.py` stub.
6. `mm_agent.py`, then `shop_agent.py`.
7. `api.py` (FastAPI) with the market maker loop on startup. Test it with curl.
8. Deploy the backend to Railway early, as soon as `/health` works, so deployment problems show up early rather than at the end.
9. The Next.js frontend: market panel and scenario toggle first, intake chat last.
10. Deploy the frontend to Vercel and run end to end against the Railway URL.
11. `intake.py` plus the chat UI, added only after steps 1 to 10 work with the ice cream preset.

After each step, give me a short way to test it (a command and its expected output) before moving on.

## Rules

- Keep it simple. Hardcode one location and one date if that helps. Don't generalize until I ask.
- No secrets in code, logs or commits.
- When something about the API is uncertain, check the docs or ask me rather than assuming.
- Don't touch `forecast.py` beyond the stub unless I ask.
