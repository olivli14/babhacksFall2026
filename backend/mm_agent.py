"""Market maker agent: quotes a bid and an ask around fair value on each symbol.

Every `interval` seconds, for each symbol:
  1. fair value from contracts.fair_value (forecast.prob_above),
  2. cancel its stale quotes,
  3. bid = fair - half_spread, ask = fair + half_spread,
  4. skew both against inventory (long YES -> lower both, short -> raise both).

Gemini has no naked shorts, so the ask is posted as "buy NO @ 1 - ask"
unless we already hold enough YES to sell outright.
Teammate owns the pricing; tune MMConfig or replace `quote()`.
"""
import logging
import math
import threading
import time
from dataclasses import dataclass, field
from types import ModuleType
from typing import Callable

import contracts
import market

log = logging.getLogger("mm")
ACCOUNT = "mm"


@dataclass
class MMConfig:
    half_spread: float = 0.03
    size: int = 500                    # contracts per side
    skew_per_contract: float = 0.0001  # price shift per contract of net inventory
    max_skew: float = 0.05
    interval: float = 5.0              # seconds between requotes


@dataclass
class MarketMaker:
    symbols: list[str]
    config: MMConfig = field(default_factory=MMConfig)
    fair_value_fn: Callable[[str], float] = contracts.fair_value
    exchange: ModuleType = market  # market (MODE-based), or gemini_client / mock_book directly
    state: dict = field(default_factory=dict)  # symbol -> latest quote info, for the API
    _live: dict = field(default_factory=dict)  # symbol -> [order ids]
    _stop: threading.Event = field(default_factory=threading.Event)
    _thread: threading.Thread | None = None

    def inventory(self, symbol: str) -> tuple[float, float]:
        """(YES held, NO held) for this symbol."""
        yes = no = 0.0
        for p in self.exchange.get_positions(ACCOUNT):
            if p["symbol"] == symbol:
                if p["outcome"] == "yes":
                    yes += float(p["totalQuantity"])
                else:
                    no += float(p["totalQuantity"])
        return yes, no

    def quote(self, fair: float, net_inventory: float) -> tuple[float, float]:
        c = self.config
        skew = max(-c.max_skew, min(c.max_skew, -c.skew_per_contract * net_inventory))
        bid = math.floor((fair - c.half_spread + skew) * 100) / 100
        ask = math.ceil((fair + c.half_spread + skew) * 100) / 100
        return max(bid, 0.01), min(ask, 0.99)

    def requote(self, symbol: str) -> None:
        for oid in self._live.pop(symbol, []):
            try:
                self.exchange.cancel_order(ACCOUNT, oid)
            except Exception:
                pass  # already filled or gone
        fair = self.fair_value_fn(symbol)
        yes, no = self.inventory(symbol)
        bid, ask = self.quote(fair, yes - no)
        size = self.config.size
        ids = [self.exchange.place_order(ACCOUNT, symbol, "buy", "yes", bid, size)]
        if yes >= size:
            ids.append(self.exchange.place_order(ACCOUNT, symbol, "sell", "yes", ask, size))
        else:
            ids.append(self.exchange.place_order(ACCOUNT, symbol, "buy", "no", round(1 - ask, 2), size))
        self._live[symbol] = ids
        self.state[symbol] = {"fair_value": round(fair, 4), "bid": bid, "ask": ask, "size": size,
                              "inventory_yes": yes, "inventory_no": no, "updated": time.time()}

    def step(self) -> None:
        for s in self.symbols:
            try:
                self.requote(s)
            except Exception:
                log.exception("requote failed for %s", s)

    def run(self) -> None:
        while not self._stop.is_set():
            self.step()
            self._stop.wait(self.config.interval)

    def start(self) -> None:
        self._stop.clear()
        self._thread = threading.Thread(target=self.run, daemon=True, name="mm-loop")
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=10)
        for s in list(self._live):
            for oid in self._live.pop(s):
                try:
                    self.exchange.cancel_order(ACCOUNT, oid)
                except Exception:
                    pass

    @property
    def running(self) -> bool:
        return bool(self._thread and self._thread.is_alive())


if __name__ == "__main__":
    # Quote tomorrow's NYC event a few times and print the quotes.
    logging.basicConfig(level=logging.INFO)
    syms = contracts.event_symbols(contracts.find_event("NYC"))
    mm = MarketMaker(syms)
    for _ in range(2):
        mm.step()
        for s, q in mm.state.items():
            print(f"{s:<36} fair {q['fair_value']:.3f}  bid {q['bid']:.2f}  ask {q['ask']:.2f}")
        print()
    mm.stop()
