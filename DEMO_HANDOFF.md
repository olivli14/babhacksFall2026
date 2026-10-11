# Demo handoff: end-to-end flow + visibility features

<!-- AI-generated with Claude (Anthropic). -->

For: whoever builds the demo frontend. **The backend for everything below already exists.** You only build panels.

- **API base URL:** `https://api-production-2173.up.railway.app` (or `http://localhost:8000` locally: `cd backend && .venv/bin/uvicorn api:app --port 8000`)
- **CORS allows:** `localhost:3000`, `localhost:5173` (Vite), and whatever is in Railway's `FRONTEND_ORIGINS`. Tell Jason your deployed URL so it can be added.
- **Every response has `mode`.** `"mock"` means the panel is SIMULATED, `"sandbox"` means LIVE SANDBOX. Show that badge on every panel.
- **Copy rules:** don't promise outcomes. Say "reduces swings" and show the numbers; never "guarantees" or "protects your revenue".

---

## 1. The story in one sentence

A business loses sales when the weather goes against it, so an AI agent buys Gemini temperature contracts sized to that loss from an AI market maker. On bad days the contracts pay out, which makes the bad days less bad.

## 2. What's real vs. simulated

| Piece | Real or simulated |
|---|---|
| Gemini weather contracts (NYC high temp, buckets like `≤68°F`, `69–70°F` … `≥77°F`) | **Real**, read from Gemini production |
| Forecast probability per bucket | **Real**: Open-Meteo GFS + ECMWF ensemble, 82 members (`forecast.py`) |
| Market maker agent quoting every bucket every 5 s | Real agent, **simulated exchange** (`mock_book.py`, same rules as Gemini) |
| Shop agent sizing + buying the hedge | Real agent, **simulated exchange** |
| Live run: same two agents placing signed orders | **LIVE on Gemini sandbox** (crypto/commodity contract, because the sandbox has no weather markets) |

## 3. End-to-end demo flow (what judges see, ~3 min)

1. **Pick a business.** Click the "Ice cream shop" preset: NYC, ~$2,000/day, loses ~$40 per °F below 72°F, $150 hedge budget. → `GET /presets`
2. **Forecast & market.** Six real Gemini contracts for tomorrow's NYC high. Each shows our forecast chance (peaks around 71–72°F) and the market maker's live bid/ask, refreshing every 2.5 s. → `GET /market`
3. **Get recommendation.** The shop agent explains: *"60% chance of a high below 72°F … Spending $62 on 3 temperature contracts pays out up to $240 on a bad day."* → `POST /hedge`
4. **Execute hedge.** 3 orders fill against the market maker. **NEW:** the trade feed shows each fill (feature A). → `POST /hedge/execute`, `GET /trades`
5. **Hot vs. cold day.** Toggle: hot day −$62 (the insurance cost), cold day **+$178**. → `GET /scenarios`
6. **NEW: Simulate 1,000 days** (feature B). The chart shows hedging narrows the spread of outcomes: worst day $1,680 → $1,858, daily swing $64 → $24. → `POST /simulate`
7. **NEW: "Settle tomorrow"** (feature C). It rolls one temperature from the forecast; the bucket that pays out lights up and the P&L updates. → `POST /settle`
8. **Live sandbox.** Paste the admin token and start a 3-minute live run. The log shows the same agents placing real signed orders on Gemini's sandbox. → `POST /live/start`, `GET /live`

Lines to say:
- After step 2: *"These are Gemini's actual contracts, priced from a live weather forecast."*
- After step 5: *"On a cold day the contracts pay out and recover most of the lost sales."*
- After step 6: *"Across a thousand possible days the average barely moves, but the bad days get much less bad."*
- After step 8: *"When Gemini lists weather in the sandbox, it's a config switch."*

---

## 4. Features to build (priority order)

### A. Live trade feed: "Agents in action" (~20 min, high impact)

Shows the two agents actually trading. Poll every 2–3 s.

`GET /trades?limit=20`
```json
{"mode": "mock", "trades": [
  {"time": 1791753123.4, "symbol": "GEMI-WXHIGH-NYC-2610130359-LO68", "bucket": "LO68",
   "yes_buyer": "shop", "yes_seller": "mm", "yes_price": 0.13, "no_price": 0.87, "qty": 240,
   "notional": 31.2, "buyer_order": "buy yes", "seller_order": "buy no",
   "taker": "shop", "maker": "mm", "taker_order": "51", "maker_order": "12"}
]}
```
Render each row as: `14:02:11  🍦 Shop bought 240 × "≤68°F" from 🤖 Market Maker @ $0.13`
- Bucket labels: `LO68` → `≤ 68°F`, `69TO70` → `69–70°F`, `HI77` → `≥ 77°F`.
- `seller_order: "buy no"` is how the market maker sells YES without holding it (Gemini has no naked shorts). It's a nice detail to show as a tooltip.
- Pair it with the market maker's inventory per bucket from `GET /market` (`contracts[].mm_quotes.inventory_yes / inventory_no`). After the shop buys, the market maker is short, and its quotes move **up** within 5 s. Highlighting that change is the "agent reacting" moment.

### B. "Simulate 1,000 days" (~30 min, highest impact)

Needs a `profile_id` from `POST /hedge` or `POST /hedge/execute`.

`POST /simulate` with body `{"profile_id": "1179237e0c50", "days": 1000}`
```json
{"mode": "mock", "days": 1000,
 "forecast": {"mean_f": 71.9, "sd_f": 2.6, "source": "ensemble"},
 "hedged":   {"mean": 1944.66, "worst": 1858.2, "best": 2018.2, "stdev": 24.29, "p5": 1918.2},
 "unhedged": {"mean": 1954.56, "worst": 1680.0, "best": 2000.0, "stdev": 64.04, "p5": 1840.0},
 "days_hedge_paid": 602, "premium": 61.8,
 "histogram": [{"from": 1680.0, "to": 1696.9, "hedged": 0, "unhedged": 12}, "... 20 bins"],
 "temperatures": [{"temp_f": 64, "days": 1}, {"temp_f": 65, "days": 6}, "..."],
 "sample": ["first 30 scenario objects, same shape as /scenarios hot/cold"]}
```
UI:
- **Overlaid histogram** of daily net result, unhedged (grey) vs hedged (blue). Hedged is visibly narrower.
- **Stat tiles:** worst day, daily swing (stdev), average day, each showing unhedged → hedged, plus "hedge paid out on 602 of 1,000 days".
- Optional: a small chart of `temperatures`, the forecast distribution the days were drawn from.
- The seed is fixed, so the picture is stable across clicks.
- Suggested caption: *"1,000 possible days drawn from tomorrow's forecast. Hedging costs about $10/day on average and cuts the worst day from $1,680 to $1,858."*

### C. "Settle tomorrow" button (~15 min)

`POST /settle` with body `{"profile_id": "..."}`
```json
{"mode": "mock", "temp_f": 67, "forecast": {"mean_f": 71.9, "sd_f": 2.6, "source": "ensemble"},
 "paying_buckets": ["LO68"],
 "result": {"temp_f": 67, "revenue": 1800.0, "hedge_payout": 240, "premium": 61.8,
            "hedge_pnl": 178.2, "net": 1978.2, "net_unhedged": 1800.0}}
```
UI: a big "🎲 Settle tomorrow" button. Show the rolled temperature, highlight the paying bucket in the market table, and show revenue / hedge P&L / net vs. unhedged. It's random each click, so it's good for one dramatic moment.

### D. Market maker reaction highlight (~10 min, optional)

No new endpoint. Diff `GET /market` between polls and flash the bid/ask cells that changed, ▲ green or ▼ red.

---

## 5. Existing endpoints (reference)

| Endpoint | Purpose |
|---|---|
| `GET /health` | `{mode, mm_running, mm_event, sandbox_ok, live_running}`. Check before demoing |
| `GET /presets` | `{ice_cream: Profile}` |
| `GET /market[?symbol=]` | `{mode, event, event_title, contracts: [{symbol, bucket, lo, hi, fair_value, book, mm_quotes}]}` |
| `POST /hedge {profile}` | `{mode, profile_id, recommendation, explanation}` |
| `POST /hedge/execute {profile}` | `{mode, profile_id, order_ids, orders, status, recommendation, explanation}` |
| `GET /scenarios?profile_id=` | `{mode, executed, hot, cold}` |
| `GET /positions?account=mm\|shop` | positions on the simulated book |
| `GET /live` | live sandbox run status and log (public) |
| `POST /live/start {seconds}` / `POST /live/stop` | header `X-Demo-Admin-Token`. Real sandbox orders; get the token from Jason |
| `POST /intake` | placeholder; returns `profile: null` |

`Profile` = `{business_type, location, baseline_revenue, weather_variable: "temperature_high", bad_direction: "below"|"above", threshold_f, loss_per_degree, premium_budget}`. `premium_budget` ≤ 1000.

The current Next.js dashboard at https://weather-hedge.vercel.app (`frontend/app/page.tsx`) already calls all of these. Use it as a working reference.

## 6. Gotchas

- **The simulated book is in memory.** Every Railway redeploy resets it, and every "Execute hedge" adds to positions. Redeploy before the real demo for a clean state.
- **Wait a couple of seconds after page load before the first click.**
- **The live sandbox run takes ~10 s to pick a contract,** the shop buys ~30 s in, and the run auto-stops and cancels everything.
- **Pooling (`hedge.py`) has no endpoint yet.** If you want the pooling dashboard from `FRONTEND_PROMPT.md`, `/api/onboard` and `/api/dashboard` still need building in `api.py`.
