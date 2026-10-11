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
