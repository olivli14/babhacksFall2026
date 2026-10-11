// AI-generated with Claude (Anthropic).
"use client";

import { useEffect, useRef, useState } from "react";
import {
  ExecuteResult, LiveStatus, PoolMarket, SandboxAccount, SandboxAccounts, SandboxOrder, executePool, getLive,
  getPoolMarket, getSandboxAccounts, startLive, strikeLabel, usd,
} from "@/lib/api";
import { Button, Card } from "@/components/ui";

const WHO: Record<string, string> = { shop: "Pool agent", mm: "Market maker" };

export function ModeBadge({ live }: { live?: boolean }) {
  return live ? (
    <span className="inline-flex items-center gap-1.5 whitespace-nowrap text-[13px] font-medium text-good">
      <span className="size-1.5 animate-pulse rounded-full bg-good" />Live on Gemini sandbox
    </span>
  ) : (
    <span className="inline-flex items-center gap-1.5 whitespace-nowrap text-[13px] text-muted">
      Simulated exchange · real Gemini contracts
    </span>
  );
}

export function AgentsCard({ domain }: { domain: string }) {
  const [m, setM] = useState<PoolMarket | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<ExecuteResult | null>(null);
  const prev = useRef<Record<string, number | null>>({});
  const [flash, setFlash] = useState<Record<string, "up" | "down">>({});

  useEffect(() => {
    let alive = true;
    const tick = () =>
      getPoolMarket(domain)
        .then((next) => {
          if (!alive) return;
          const changed: Record<string, "up" | "down"> = {};
          for (const q of next.quotes) {
            const before = prev.current[q.symbol];
            if (before != null && q.ask != null && q.ask !== before) changed[q.symbol] = q.ask > before ? "up" : "down";
            prev.current[q.symbol] = q.ask;
          }
          if (Object.keys(changed).length) {
            setFlash(changed);
            setTimeout(() => alive && setFlash({}), 1600);
          }
          setM(next);
          setErr(null);
        })
        .catch((e) => alive && setErr(e.message));
    tick();
    const id = setInterval(tick, 3000);
    return () => { alive = false; clearInterval(id); };
  }, [domain]);

  async function buy() {
    setBusy(true);
    try {
      setResult(await executePool(domain));
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Order failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <div className="grid gap-10 xl:grid-cols-[1.2fr_1fr]">
        <div>
          <table className="w-full text-[13px]">
            <thead className="text-left text-muted">
              <tr>
                <th className="pb-2 font-normal">Tomorrow&apos;s high</th>
                <th className="pb-2 text-right font-normal">Forecast</th>
                <th className="pb-2 text-right font-normal">Bid</th>
                <th className="pb-2 text-right font-normal">Ask</th>
                <th className="pb-2 text-right font-normal">MM position</th>
              </tr>
            </thead>
            <tbody className="tabular divide-y divide-line">
              {(m?.quotes ?? []).map((q) => (
                <tr key={q.symbol}>
                  <td className="py-2.5 text-ink">{strikeLabel(q.bucket)}</td>
                  <td className="py-2.5 text-right text-ink-2">{q.fair_value != null ? `${Math.round(q.fair_value * 100)}%` : "–"}</td>
                  <td className="py-2.5 text-right text-ink-2">{q.bid != null ? `${Math.round(q.bid * 100)}¢` : "–"}</td>
                  <td className={`py-2.5 text-right font-medium transition-colors duration-700 ${
                    flash[q.symbol] === "up" ? "text-good" : flash[q.symbol] === "down" ? "text-bad" : "text-ink"}`}>
                    {flash[q.symbol] === "up" ? "▲ " : flash[q.symbol] === "down" ? "▼ " : ""}
                    {q.ask != null ? `${Math.round(q.ask * 100)}¢` : "–"}
                  </td>
                  <td className="py-2.5 text-right text-ink-2">{q.inventory === 0 ? "flat" : q.inventory < 0 ? `short ${-q.inventory}` : `long ${q.inventory}`}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {!m && !err && <p className="py-6 text-[13px] text-muted">Connecting to the market maker…</p>}
          {err && <p className="mt-3 text-[13px] text-bad">{err}</p>}
          <p className="mt-3 text-[12px] text-muted">Each contract pays $1 if tomorrow&apos;s high lands in its range. Prices refresh every few seconds.</p>
        </div>

        <div className="flex flex-col">
          <Button onClick={buy} disabled={busy || !m} className="w-full py-3">
            {busy ? "Placing orders…" : "Buy the pool's hedge"}
          </Button>
          {result && (
            <p className="mt-3 text-[13px] text-ink-2">
              {result.orders.filter((o) => o.status === "filled").length} of {result.orders.length} orders filled for{" "}
              <span className="font-medium text-ink">{usd(result.total_cost, 2)}</span>. Watch the market maker&apos;s asks move up as it takes on risk.
            </p>
          )}
          <p className="mt-6 text-[13px] font-medium text-ink">Trades</p>
          <ul className="mt-2 max-h-56 flex-1 space-y-2 overflow-auto">
            {(m?.fills ?? []).length === 0 && <li className="text-[13px] text-muted">No trades yet for this market.</li>}
            {(m?.fills ?? []).map((f, i) => (
              <li key={`${f.time}-${i}`} className="border-b border-line pb-2 text-[13px] text-ink-2">
                <span className="tabular text-muted">{new Date(f.time * 1000).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" })}</span>{" "}
                <span className="text-ink">{WHO[f.yes_buyer] ?? f.yes_buyer}</span> bought{" "}
                <span className="tabular font-medium text-ink">{f.qty.toLocaleString()} × {strikeLabel(f.bucket)}</span> from{" "}
                {WHO[f.yes_seller] ?? f.yes_seller} at <span className="tabular">{Math.round(f.yes_price * 100)}¢</span>
              </li>
            ))}
          </ul>
        </div>
      </div>
      <Card className="mt-10"><LivePanel /></Card>
    </div>
  );
}

function LivePanel() {
  const [token, setToken] = useState("");
  const [status, setStatus] = useState<LiveStatus | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    const tick = () => getLive().then((s) => alive && setStatus(s)).catch(() => {});
    tick();
    const id = setInterval(tick, 2500);
    return () => { alive = false; clearInterval(id); };
  }, []);

  async function start() {
    setErr(null);
    try {
      await startLive(token.trim());
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Couldn't start");
    }
  }

  return (
    <details className="group">
      <summary className="flex cursor-pointer list-none items-center justify-between gap-4 px-6 py-4 sm:px-8">
        <span>
          <span className="block text-[15px] font-medium">Same agents, real Gemini orders</span>
          <span className="block text-[13px] text-ink-2">Gemini&apos;s sandbox has no weather markets yet, so this runs the agents on a live sandbox contract.</span>
        </span>
        <span className="flex items-center gap-3">
          <ModeBadge live />
          <span className="text-muted transition-transform group-open:rotate-180" aria-hidden>▾</span>
        </span>
      </summary>
      <div className="px-6 pb-6 sm:px-8">
        <div className="flex flex-wrap gap-2">
          <input type="password" value={token} onChange={(e) => setToken(e.target.value)} placeholder="Admin token"
                 aria-label="Admin token" autoComplete="off"
                 className="w-56 rounded-md border border-line-strong bg-white px-3 py-2 text-[13px] outline-none focus:border-ink" />
          <Button onClick={start} disabled={!token || status?.running}>
            {status?.running ? "Running…" : "Start a 3-minute live run"}
          </Button>
        </div>
        {err && <p className="mt-2 text-[13px] text-bad">{err}</p>}
        <pre className="mt-3 max-h-56 overflow-auto rounded-md bg-ink p-4 font-mono text-[12px] leading-relaxed text-[#e4e4e0]">
          {status?.log?.length ? status.log.join("\n") : "No live run yet."}
        </pre>
        <SandboxAccountsView running={!!status?.running} />
      </div>
    </details>
  );
}

// --- Real Gemini sandbox accounts (GET /sandbox/accounts) ---

const SANDBOX_WHO: Record<string, string> = { shop: "Shop agent", mm: "Market maker", other: "another sandbox trader", unknown: "earlier counterparty" };
const clock = (t: number | null) =>
  t ? new Date(t * 1000).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" }) : "–";
const cents = (p: number) => `${Math.round(p * 100)}¢`;

function SandboxAccountsView({ running }: { running: boolean }) {
  const [d, setD] = useState<SandboxAccounts | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    const tick = () => getSandboxAccounts()
      .then((x) => { if (alive) { setD(x); setErr(null); } })
      .catch((e) => alive && setErr(e instanceof Error ? e.message : "Couldn't reach Gemini sandbox"));
    tick();
    const id = setInterval(tick, running ? 4000 : 15000);
    return () => { alive = false; clearInterval(id); };
  }, [running]);

  return (
    <div className="mt-8">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <p className="text-[15px] font-medium">Both agents&apos; real Gemini sandbox accounts</p>
        <span className="text-[12px] text-muted">
          Read from Gemini&apos;s API{d ? ` · updated ${clock(d.fetched_at)}` : ""}
        </span>
      </div>
      <p className="mt-1 text-[13px] text-ink-2">
        The same balances, positions and orders the Gemini sandbox website shows. Order IDs are Gemini&apos;s own.
      </p>
      {(err || d?.error) && <p className="mt-2 text-[13px] text-bad">{err ?? `Showing last good data: ${d?.error}`}</p>}
      {!d && !err && <p className="mt-3 text-[13px] text-muted">Loading sandbox accounts…</p>}
      {d && (
        <>
          <div className="mt-4 grid gap-4 md:grid-cols-2">
            <AccountColumn a={d.accounts.mm} />
            <AccountColumn a={d.accounts.shop} />
          </div>
          <p className="mt-6 text-[13px] font-medium text-ink">Fills on Gemini</p>
          <ul className="mt-2 max-h-56 space-y-2 overflow-auto">
            {d.fills.length === 0 && <li className="text-[13px] text-muted">No fills yet. Start a live run.</li>}
            {d.fills.map((f, i) => (
              <li key={`${f.orders.shop ?? f.orders.mm}-${i}`} className="border-b border-line pb-2 text-[13px] text-ink-2">
                <span className="tabular text-muted">{clock(f.time)}</span>{" "}
                <span className="text-ink">{SANDBOX_WHO[f.yes_buyer] ?? f.yes_buyer}</span> bought{" "}
                <span className="tabular font-medium text-ink">{f.qty} YES</span> on &ldquo;{f.event}: {f.contract}&rdquo; from{" "}
                {SANDBOX_WHO[f.yes_seller] ?? f.yes_seller} at <span className="tabular">{cents(f.yes_price)}</span>
                {f.between_our_agents && (
                  <span className="ml-2 whitespace-nowrap text-[12px] font-medium text-good">● agent-to-agent</span>
                )}
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}

function orderText(o: SandboxOrder) {
  return `${o.side} ${o.outcome.toUpperCase()} ${o.qty} @ ${cents(o.price)}`;
}

function AccountColumn({ a }: { a: SandboxAccount }) {
  const change = a.usd.change ?? 0;
  return (
    <div className="rounded-md border border-line p-4">
      <div className="flex items-baseline justify-between gap-2">
        <span className="text-[14px] font-medium text-ink">{a.label}</span>
        <span className="tabular text-[13px] text-ink-2">
          {a.usd.amount != null ? usd(a.usd.amount, 2) : "–"}{" "}
          <span className={change >= 0 ? "text-good" : "text-bad"}>({change >= 0 ? "+" : ""}{usd(change, 2)})</span>
        </span>
      </div>
      <p className="text-[12px] text-muted">
        USD balance (started at $100,000) · {a.stats.contracts_filled} contracts filled across {a.stats.filled_orders} of its last {a.stats.orders} orders
      </p>

      <p className="mt-3 text-[12px] font-medium uppercase tracking-wide text-muted">Positions</p>
      {a.positions.length === 0 ? <p className="text-[13px] text-muted">None</p> : (
        <ul className="text-[13px] text-ink-2">
          {a.positions.map((p) => (
            <li key={`${p.symbol}-${p.outcome}`} className="flex justify-between gap-2">
              <span className="truncate">{p.event}: {p.contract}</span>
              <span className="tabular whitespace-nowrap text-ink">{p.qty} {p.outcome.toUpperCase()} @ {cents(p.avg_price)}</span>
            </li>
          ))}
        </ul>
      )}

      <p className="mt-3 text-[12px] font-medium uppercase tracking-wide text-muted">Open orders</p>
      {a.open_orders.length === 0 ? <p className="text-[13px] text-muted">None</p> : (
        <ul className="text-[13px] text-ink-2">
          {a.open_orders.map((o) => (
            <li key={o.order_id} className="flex justify-between gap-2">
              <span className="tabular text-ink">{orderText(o)}</span>
              <span className="tabular text-muted">#{o.order_id.slice(-6)}</span>
            </li>
          ))}
        </ul>
      )}

      <p className="mt-3 text-[12px] font-medium uppercase tracking-wide text-muted">Recent orders</p>
      <ul className="max-h-40 overflow-auto text-[13px] text-ink-2">
        {a.orders.slice(0, 8).map((o) => (
          <li key={o.order_id} className="flex justify-between gap-2">
            <span className="tabular">
              <span className="text-muted">{clock(o.created)}</span> {orderText(o)}
            </span>
            <span className={`tabular whitespace-nowrap ${o.filled > 0 ? "font-medium text-good" : "text-muted"}`}>
              {o.filled > 0 ? `filled ${o.filled}/${o.qty}` : o.status}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
