<!-- AI-generated with Claude (Anthropic). Paste everything below the line into a new Claude chat. -->

---

You're helping me build the frontend for a 5-hour hackathon project. Work fast, keep it simple, get it working end to end before polishing.

## Project
"Weather hedging on autopilot" for small businesses. Businesses hurt by heat (ramen shops, hot coffee) and businesses hurt by cold (ice cream, boba) in the same city are pooled. Their opposite exposures cancel out, and only the leftover is hedged on Gemini's daily high-temperature prediction markets. Pooling makes each business's hedge much cheaper than hedging alone.

A teammate's backend (Python) already does the analysis. You build the UI only.

## Hard rules
- Work only inside `/Users/satya/git-practice/babhacksFall2026/frontend/`. Another session is editing the Python files in the parent folder at the same time; don't touch them.
- The frontend calls **only** our backend API (below). Never call Supabase, Context.dev, Gemini, or weather APIs from the browser, and never put an API key in frontend code.
- Build against a mock JSON file first (`public/mock/dashboard.json`, shaped exactly like the contract below), behind a `USE_MOCK` flag. Switching to the real API should be a one-line change.
- Stack: Vite + React + TypeScript + Recharts. No other UI libraries unless clearly needed.
- Only install npm packages published more than 7 days ago: `npm install --before="$(date -v-7d +%Y-%m-%d)" <pkg>` (macOS `date`). Pin exact versions.
- Add a header comment to each file you create noting it was AI-generated with Claude.
- Don't promise outcomes in UI copy. Say "reduces swings" and show the numbers; never "guarantees" or "protects your revenue." Copy should be direct and plain, no marketing filler.

## Screens

### 1. Onboard
One form, centered:
- Website URL (required)
- City, "City, ST" (optional, but recommend it: "Needed if you have more than one location")
- Annual revenue in USD (optional: "Used to size your exposure. Without it we use a typical shop your size.")

Submit calls `POST /api/onboard`. The first run for a new website can take 30-60 seconds, so show a step list while waiting: "Reading your website", "Classifying your business", "Finding your nearest weather market". On success, go to the dashboard for that domain. Show API errors inline.

### 2. Dashboard (`/dashboard/:domain`)
Top to bottom:

1. **Header**: logo, name, a badge for `side` ("Hurt by heat" / "Hurt by cold" / "Needs review"), and the `reason_codes` as small chips ("ramen x57") so people can see why we classified them that way.
2. **Your weather hub**: Gemini city, station (e.g. LAX), distance in miles from the business.
3. **Forecast**: next market date, forecast high, and a horizontal bar chart of each temperature bucket's probability. Where `market_price` is not null, show it next to our probability.
4. **Temperature history** (main chart): daily high over the selected date range, current year as a bold line, prior years as faint overlaid lines on the same month-day x-axis. Draw a horizontal line at the business's `baseline_temp_f` labeled "Your break-even temp". A date-range picker (presets: 30 days, 90 days, 1 year) drives this chart and the P&L chart.
5. **Recommendation** card: "Hedge cost for {date}: ${your_daily_cost}". Underneath: "Alone it would cost ${standalone_daily_cost}. Pooling with {pool_size} nearby businesses saves {pool_savings_pct}%." A collapsible table lists the contracts (bucket, contracts, price).
6. **Hedged vs unhedged** chart: daily weather-driven profit over the range, two lines (unhedged, hedged), zero line. Below it, three stats: worst day unhedged vs hedged, daily swing (stdev) unhedged vs hedged, total cost of hedging over the period.

## API contract

Base URL: `http://localhost:8000`

`POST /api/onboard`
```json
{"url": "https://www.dkramen.com", "city": "Los Angeles, CA", "annual_revenue": 1500000}
```
returns `200 {"domain": "dkramen.com"}` or `4xx {"error": "message"}`.

`GET /api/dashboard?domain=dkramen.com&from=2025-10-11&to=2026-10-11` returns:
```json
{
  "business": {
    "domain": "dkramen.com", "name": "Daikokuya", "logo_url": "https://...png",
    "address": "Los Angeles, CA", "side": "heat_hurt", "confidence": 1.0,
    "reason_codes": ["ramen x57", "noodle x6", "soup x2"],
    "business_type": "noodle_soup", "baseline_temp_f": 72,
    "dollars_per_degree": 61.64, "annual_revenue": 1500000
  },
  "hub": {"gemini_city": "Los Angeles", "station": "LAX", "distance_miles": 12.1},
  "forecast": {
    "date": "2026-10-12", "mean_high_f": 65.2,
    "buckets": [
      {"label": "63°F or below", "model_prob": 0.13, "market_price": null},
      {"label": "64°F to 65°F", "model_prob": 0.42, "market_price": 0.38}
    ]
  },
  "temperature_history": [
    {"date": "2026-10-08", "year": 2026, "month_day": "10-08", "high_f": 74.1}
  ],
  "recommendation": {
    "date": "2026-10-12", "your_daily_cost": 12.40, "standalone_daily_cost": 47.10,
    "pool_savings_pct": 74, "pool_size": 3,
    "contracts": [{"bucket": "74°F to 75°F", "contracts": 40, "price": 0.44}]
  },
  "pnl_series": [
    {"date": "2026-10-03", "high_f": 99.1, "unhedged": -1665.0, "hedged": -310.0}
  ],
  "summary": {
    "worst_day": {"date": "2026-10-03", "unhedged": -1665.0, "hedged": -310.0},
    "stdev_unhedged": 240.5, "stdev_hedged": 98.2, "total_hedge_cost": 4380.0
  }
}
```
`temperature_history` includes the selected range for the current year plus the same month-day range for up to 4 prior years. Generate realistic mock data from this shape (LA highs mostly 60-80°F with a few heat spikes).

Start by scaffolding the app with the mock, get both screens rendering, then show me.
