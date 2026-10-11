"""Shop agent: turns a business profile into a weather hedge and executes it.

Sales model: lost revenue = loss_per_degree * degrees past threshold_f in the
bad direction ("below" = cold hurts, "above" = heat hurts).

Gemini splits each day's high into buckets (LO68, 69TO70, ..., HI77). The shop
buys YES on every bucket where it would lose money, sized so a bucket's payout
($1 per contract) covers the loss at that bucket's temperature: a "strip"
that pays out whichever cold (or hot) outcome happens. If the strip costs more
than the premium budget, every leg is scaled down evenly.
"""
import math
from datetime import date as Date

import contracts
import market

ACCOUNT = "shop"
MAX_CONTRACTS_PER_ORDER = 2000  # safety cap on any single hedge order

ICE_CREAM_PRESET = {
    "business_type": "ice cream shop",
    "location": "New York",
    "baseline_revenue": 2000.0,
    "weather_variable": "temperature_high",
    "bad_direction": "below",
    "threshold_f": 72.0,
    "loss_per_degree": 40.0,
    "premium_budget": 150.0,
}


def lost_revenue(profile: dict, temp_f: float) -> float:
    gap = (profile["threshold_f"] - temp_f if profile["bad_direction"] == "below"
           else temp_f - profile["threshold_f"])
    return min(max(gap, 0.0) * profile["loss_per_degree"], profile["baseline_revenue"])


def best_ask(symbol: str) -> float | None:
    asks = market.get_book(symbol)["asks"]
    return asks[0][0] if asks else None


def recommend(profile: dict, date: str | None = None) -> dict:
    event = contracts.find_event(profile["location"], date)
    legs, expected_loss, p_bad = [], 0.0, 0.0
    for sym in contracts.event_symbols(event):
        c = contracts.parse(sym)
        prob = contracts.fair_value(sym)
        loss = lost_revenue(profile, contracts.representative_temp(c))
        expected_loss += prob * loss
        if loss <= 0:
            continue
        p_bad += prob
        legs.append({"symbol": sym, "bucket": c["strike"], "prob": round(prob, 4),
                     "loss_if_hit": round(loss, 2), "ask": best_ask(sym),
                     "target_qty": math.ceil(loss)})

    buyable = [l for l in legs if l["ask"] is not None]
    full_cost = sum(l["target_qty"] * l["ask"] for l in buyable)
    scale = min(1.0, profile["premium_budget"] / full_cost) if full_cost else 0.0
    for l in legs:
        qty = math.floor(l["target_qty"] * scale) if l["ask"] is not None else 0
        l["qty"] = min(qty, MAX_CONTRACTS_PER_ORDER)
        l["cost"] = round(l["qty"] * (l["ask"] or 0), 2)
    legs = [l for l in legs if l["qty"] > 0]

    c0 = contracts.parse(legs[0]["symbol"]) if legs else contracts.parse(
        contracts.event_symbols(event)[0])
    rec = {
        "event": event["ticker"], "event_title": event.get("title"),
        "location": c0["location"], "date": c0["date"],
        "prob_bad_weather": round(p_bad, 4),
        "expected_lost_revenue": round(expected_loss, 2),
        "premium": round(sum(l["cost"] for l in legs), 2),
        "max_payout": max((l["qty"] for l in legs), default=0),
        "coverage": round(scale, 3),
        "legs": legs,
    }
    rec["explanation"] = explain(profile, rec)
    return rec


def explain(profile: dict, rec: dict) -> str:
    word = "below" if profile["bad_direction"] == "below" else "above"
    t = profile["threshold_f"]
    if not rec["legs"]:
        return (f"No hedge needed or available: the market sees little chance of a high "
                f"{word} {t:.0f}°F in {rec['location']} on {rec['date']}.")
    cover = ("fully covers" if rec["coverage"] >= 0.999
             else f"covers about {rec['coverage']:.0%} of")
    day = Date.fromisoformat(rec["date"]).strftime("%A, %b %-d")
    return (f"{day} in {rec['location']} has a {rec['prob_bad_weather']:.0%} chance of a "
            f"high {word} {t:.0f}°F, which would cost the {profile['business_type']} "
            f"${rec['expected_lost_revenue']:.0f} in expected lost sales. Spending "
            f"${rec['premium']:.0f} on {len(rec['legs'])} temperature contracts pays out up to "
            f"${rec['max_payout']:.0f} on a bad day, which {cover} the loss.")


def execute(rec: dict) -> list[dict]:
    """Buy each leg with a limit order at the ask. Returns per-leg order results."""
    results = []
    for l in rec["legs"]:
        oid = market.place_order(ACCOUNT, l["symbol"], "buy", "yes", l["ask"], l["qty"])
        open_ids = {str(o["orderId"]): o for o in market.get_active_orders(ACCOUNT, l["symbol"])}
        o = open_ids.get(oid)
        filled = l["qty"] - float(o["remainingQuantity"]) if o else l["qty"]
        results.append({"symbol": l["symbol"], "order_id": oid, "qty": l["qty"],
                        "price": l["ask"], "filled": filled,
                        "status": "filled" if not o else ("partial" if filled else "open")})
    return results


def scenario(profile: dict, rec: dict, temp_f: float) -> dict:
    """Revenue, hedge P&L and net result if the day's high is temp_f."""
    revenue = profile["baseline_revenue"] - lost_revenue(profile, temp_f)
    payout = sum(l["qty"] for l in rec["legs"]
                 if contracts.pays_out(contracts.parse(l["symbol"]), temp_f))
    hedge_pnl = payout - rec["premium"]
    unhedged = revenue
    return {"temp_f": temp_f, "revenue": round(revenue, 2), "hedge_payout": payout,
            "premium": rec["premium"], "hedge_pnl": round(hedge_pnl, 2),
            "net": round(revenue + hedge_pnl, 2), "net_unhedged": round(unhedged, 2)}


if __name__ == "__main__":
    import json

    import mm_agent

    p = ICE_CREAM_PRESET
    syms = contracts.event_symbols(contracts.find_event(p["location"]))
    mm = mm_agent.MarketMaker(syms)
    mm.step()  # market maker posts quotes
    rec = recommend(p)
    print(json.dumps({k: v for k, v in rec.items() if k != "legs"}, indent=1))
    for l in rec["legs"]:
        print(f"  {l['bucket']:<8} p={l['prob']:.2f} loss=${l['loss_if_hit']:<6} ask={l['ask']} qty={l['qty']} cost=${l['cost']}")
    print("\nexecute:", execute(rec))
    print("shop positions:", market.get_positions("shop"))
    for name, t in (("hot", p["threshold_f"] + 6), ("cold", p["threshold_f"] - 8)):
        print(f"{name:>4}:", scenario(p, rec, t))
    mm.stop()
