"""LIVE sandbox run of both agents on a real Gemini sandbox crypto contract.

The sandbox has no weather markets, so this proves the same agent code trades
for real:
- Market maker: mm_agent.MarketMaker against gemini_client. Fair value = mid
  of the same contract on Gemini PRODUCTION (public prices; every sandbox
  contract is listed there under the same symbol). Sandbox books are often
  empty, because the sandbox bots only quote contracts expiring within the hour.
- Shop: shop_agent's sizing (loss to protect -> contracts, capped by budget),
  buying YES from the market maker's ask.
All open orders are cancelled when the run ends.

Used by api.py (POST /live/start) and scripts/live_demo.py.
"""
import threading
import time
from datetime import datetime, timedelta, timezone

import gemini_client as gc
import mm_agent

SHOP_PROFILE = {"loss_to_protect": 10.0, "premium_budget": 6.0}
MM_CONFIG = mm_agent.MMConfig(half_spread=0.02, size=5, skew_per_contract=0.004,
                              max_skew=0.03, interval=10)


def cancel_all_open() -> int:
    """Cancel every open order on both sandbox accounts (e.g. left by a crash)."""
    n = 0
    for acct in ("mm", "shop"):
        for o in gc.get_active_orders(acct):
            try:
                gc.cancel_order(acct, str(o["orderId"]))
                n += 1
            except Exception:
                pass
    return n


class LiveRun:
    def __init__(self, duration: int = 300, echo: bool = False):
        self.duration, self.echo = duration, echo
        self.symbol: str | None = None
        self.description = ""
        self.log: list[str] = []
        self.started = self.ended = None
        self.error: str | None = None
        self.mm: mm_agent.MarketMaker | None = None
        self._last_fair: dict[str, float] = {}
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    # --- helpers ---
    def say(self, msg: str) -> None:
        line = f"[{datetime.now().strftime('%H:%M:%S')}] {msg}"
        self.log.append(line)
        if self.echo:
            print(line, flush=True)

    def external_book(self, symbol: str) -> dict:
        """The sandbox book minus the market maker's own resting orders."""
        book = gc.get_book(symbol)
        bids, asks = dict(book["bids"]), dict(book["asks"])
        for o in gc.get_active_orders("mm", symbol):
            rem, px = float(o["remainingQuantity"]), float(o["price"])
            yes_px = px if o["outcome"] == "yes" else round(1 - px, 2)
            side = bids if (o["side"], o["outcome"]) in (("buy", "yes"), ("sell", "no")) else asks
            side[yes_px] = side.get(yes_px, 0) - rem
        return {"bids": sorted([(p, q) for p, q in bids.items() if q > 1e-9], key=lambda l: -l[0]),
                "asks": sorted([(p, q) for p, q in asks.items() if q > 1e-9], key=lambda l: l[0])}

    def mid_fair_value(self, symbol: str) -> float:
        """Production mid for the same symbol; else the sandbox book without our orders."""
        for book in (gc.get_book(symbol, base=gc.PROD_URL), self.external_book(symbol)):
            if book["bids"] and book["asks"]:
                self._last_fair[symbol] = (book["bids"][0][0] + book["asks"][0][0]) / 2
                break
        return self._last_fair[symbol]

    def pick_contract(self) -> None:
        """Sandbox contract expiring well after the run whose production price is
        most uncertain (closest to 0.50)."""
        later = datetime.now(timezone.utc) + timedelta(seconds=self.duration + 15 * 60)
        sandbox = {c["instrumentSymbol"] for ev in gc.get_events() for c in ev["contracts"]
                   if c.get("marketState") == "open"
                   and datetime.fromisoformat(c["expiryDate"].replace("Z", "+00:00")) >= later}
        best = None
        for ev in gc.get_events(base=gc.PROD_URL):
            for c in ev["contracts"]:
                p = c.get("prices", {})
                if c["instrumentSymbol"] not in sandbox or not (p.get("bestBid") and p.get("bestAsk")):
                    continue
                mid = (float(p["bestBid"]) + float(p["bestAsk"])) / 2
                if 0.2 <= mid <= 0.8 and (best is None or abs(mid - 0.5) < best[0]):
                    best = (abs(mid - 0.5), c["instrumentSymbol"], f"{ev['title']} / {c['label']}")
        if not best:
            raise RuntimeError("No suitable sandbox contract right now")
        _, self.symbol, self.description = best

    def shop_hedge(self) -> None:
        ask = self.mm.state[self.symbol]["ask"]
        target = int(SHOP_PROFILE["loss_to_protect"])  # $1 payout per contract
        qty = min(target, int(SHOP_PROFILE["premium_budget"] // ask))
        self.say(f"SHOP  wants ${target} of protection; mm ask {ask:.2f}; budget "
                 f"${SHOP_PROFILE['premium_budget']:.0f} -> buying {qty} YES @ {ask:.2f}")
        oid = gc.place_order("shop", self.symbol, "buy", "yes", ask, qty)
        time.sleep(2)
        still_open = [o for o in gc.get_active_orders("shop", self.symbol)
                      if str(o["orderId"]) == oid]
        if still_open:
            self.say(f"SHOP  order {oid} filled {still_open[0]['filledQuantity']}/{qty}; cancelling rest")
            gc.cancel_order("shop", oid)
        else:
            self.say(f"SHOP  order {oid} FILLED {qty}/{qty}")

    def positions(self) -> dict:
        if not self.symbol:
            return {}
        return {acct: [{"outcome": p["outcome"], "qty": p["totalQuantity"], "avg_price": p["avgPrice"]}
                       for p in gc.get_positions(acct) if p["symbol"] == self.symbol]
                for acct in ("mm", "shop")}

    def cleanup(self) -> None:
        if self.mm:
            self.mm._live.clear()
        for acct in ("mm", "shop"):
            for o in gc.get_active_orders(acct, self.symbol):
                try:
                    gc.cancel_order(acct, str(o["orderId"]))
                except Exception:
                    pass

    # --- lifecycle ---
    def run(self) -> None:
        self.started = time.time()
        try:
            if n := cancel_all_open():
                self.say(f"cancelled {n} leftover open order(s)")
            self.pick_contract()
            self.say(f"LIVE SANDBOX run for {self.duration}s on {self.symbol} ({self.description})")
            self.mm = mm_agent.MarketMaker([self.symbol], MM_CONFIG,
                                           fair_value_fn=self.mid_fair_value, exchange=gc)
            end, hedged = time.time() + self.duration, False
            while time.time() < end and not self._stop.is_set():
                self.mm.step()
                q = self.mm.state.get(self.symbol)
                if q:
                    self.say(f"MM    fair {q['fair_value']:.3f}  bid {q['bid']:.2f}  ask {q['ask']:.2f}  "
                             f"inv YES {q['inventory_yes']:g} / NO {q['inventory_no']:g}")
                if not hedged and q and time.time() - self.started > 30:
                    self.shop_hedge()
                    hedged = True
                self._stop.wait(MM_CONFIG.interval)
        except Exception as e:  # surface to the API instead of dying silently
            self.error = str(e)
            self.say(f"ERROR {e}")
        finally:
            if self.symbol:
                self.cleanup()
                self.say(f"stopped; open orders cancelled. Positions: {self.positions()}")
            self.ended = time.time()

    def start(self) -> None:
        self._thread = threading.Thread(target=self.run, daemon=True, name="live-run")
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    @property
    def running(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    def status(self) -> dict:
        q = self.mm.state.get(self.symbol) if self.mm and self.symbol else None
        return {"running": self.running, "symbol": self.symbol, "description": self.description,
                "started": self.started, "ended": self.ended, "error": self.error,
                "mm_quote": q, "log": self.log[-50:]}
