// AI-generated with Claude (Anthropic).
"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { Dashboard, getDashboard, labelBounds, longDate, shortDate, usd, usdSigned } from "@/lib/api";
import { Card, LegendItem, SectionHead, Segmented, SideBadge, Stat, Wordmark } from "@/components/ui";
import { CostCompare, ForecastBars, HistoryChart, SimHistogram } from "@/components/charts";
import { AgentsCard } from "@/components/agents";

const RANGES = [
  { value: 30, label: "30 days" },
  { value: 90, label: "90 days" },
  { value: 365, label: "1 year" },
];

export default function DashboardPage() {
  const { domain } = useParams<{ domain: string }>();
  const [days, setDays] = useState(365);
  const [data, setData] = useState<Dashboard | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let live = true;
    setLoading(true);
    getDashboard(decodeURIComponent(domain), days)
      .then((d) => { if (live) { setData(d); setError(null); } })
      .catch((e) => { if (live) setError(e.message); })
      .finally(() => { if (live) setLoading(false); });
    return () => { live = false; };
  }, [domain, days]);

  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-10 border-b border-line bg-page/85 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4 sm:px-10">
          <Wordmark />
          <Link href="/" className="rounded-lg px-3 py-1.5 text-[13px] font-medium text-ink-2 transition-colors hover:bg-wash hover:text-ink">
            Analyze another business
          </Link>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-6 pb-24 pt-10 sm:px-10">
        {error && !data && <ErrorState message={error} />}
        {!data && !error && <Skeleton />}
        {data && <Body d={data} days={days} setDays={setDays} loading={loading} />}
      </main>
    </div>
  );
}

function Body({ d, days, setDays, loading }: {
  d: Dashboard; days: number; setDays: (n: number) => void; loading: boolean;
}) {
  const b = d.business;
  const rec = d.recommendation;
  const fc = d.forecast;
  const direction = b.side === "cold_hurt" ? "below" : "above";

  return (
    <div className="space-y-6">
      {/* Business header */}
      <div className="flex flex-wrap items-start justify-between gap-6 pb-2">
        <div className="flex items-start gap-4">
          {b.logo_url
            ? <img src={b.logo_url} alt="" className="size-14 rounded-xl border border-line bg-white object-contain p-1" />
            : <span className="size-14 rounded-xl bg-wash" />}
          <div>
            <div className="flex flex-wrap items-center gap-3">
              <h1 className="text-[28px] font-semibold tracking-tight">{b.name || b.domain}</h1>
              <SideBadge side={b.side} />
            </div>
            <p className="mt-1 text-[15px] text-ink-2">{[b.domain, b.address].filter(Boolean).join(" · ")}</p>
            {b.reason_codes?.length > 0 && (
              <p className="mt-3 flex flex-wrap items-center gap-1.5 text-[13px] text-muted">
                <span>Why we think so:</span>
                {b.reason_codes.map((r) => (
                  <span key={r} className="rounded-md border border-line bg-card px-2 py-0.5 text-ink-2">{r.replace(" x", " ×")}</span>
                ))}
              </p>
            )}
          </div>
        </div>
        {d.hub && (
          <div className="rounded-xl border border-line bg-card px-4 py-3 text-[13px]">
            <p className="text-muted">Your weather market</p>
            <p className="mt-0.5 font-medium text-ink">{d.hub.gemini_city} · {d.hub.station} station</p>
            {d.hub.distance_miles != null && <p className="text-ink-2">{d.hub.distance_miles} mi from you</p>}
          </div>
        )}
      </div>

      {b.side === "needs_review" && (
        <Card className="p-8">
          <p className="font-medium">We couldn&apos;t tell whether hot or cold weather hurts this business.</p>
          <p className="mt-1 text-ink-2">The website didn&apos;t mention enough of what you sell. Try your menu page, or a different URL.</p>
        </Card>
      )}

      {rec && fc && b.dollars_per_degree != null && b.baseline_temp_f != null && (
        <>
          {/* Headline numbers */}
          <Card className="grid grid-cols-1 divide-y divide-line sm:grid-cols-2 sm:divide-y-0 lg:grid-cols-4 lg:divide-x">
            <div className="p-6 sm:p-7">
              <Stat label={`Forecast high, ${shortDate(fc.date)}`} value={`${fc.mean_high_f.toFixed(0)}°F`}
                    note={`±${fc.sd_f.toFixed(1)}°F · ${fc.source === "ensemble" ? `${fc.members} forecast runs` : "seasonal average"}`} />
            </div>
            <div className="p-6 sm:p-7">
              <Stat label="What weather costs you" value={`${usd(b.dollars_per_degree)}/°F`}
                    note={`for each degree ${direction} ${b.baseline_temp_f}°F${b.dollars_per_degree_source === "default" ? " · typical shop" : ""}`} />
            </div>
            <div className="p-6 sm:p-7">
              <Stat label="Your hedge for tomorrow" tone="brand" value={usd(rec.your_daily_cost, 2)}
                    note={<>Alone it would cost {usd(rec.standalone_daily_cost, 2)}</>} />
            </div>
            <div className="p-6 sm:p-7">
              <Stat label="Saved by pooling" value={`${rec.pool_savings_pct}%`}
                    note={`${rec.pool_size} businesses in ${d.hub?.gemini_city}`} />
            </div>
          </Card>

          {/* Forecast + pool */}
          <div className="grid gap-6 lg:grid-cols-[1.25fr_1fr]">
            <Card>
              <SectionHead eyebrow={longDate(fc.date)} title={`Tomorrow's high in ${d.hub?.gemini_city}`}
                           sub="Chance of each temperature range Gemini trades. Colored ranges are the ones that cost you money." />
              <div className="px-6 pb-7 sm:px-8"><ForecastBars buckets={fc.buckets} side={b.side} baseline={b.baseline_temp_f} /></div>
            </Card>
            <Card>
              <SectionHead eyebrow="Pooling" title="Why your hedge is cheaper"
                           sub="Businesses hurt by heat and businesses hurt by cold cancel out. The pool only hedges what's left." />
              <div className="space-y-6 px-6 pb-7 sm:px-8">
                <CostCompare alone={rec.standalone_daily_cost} pooled={rec.your_daily_cost} />
                <ul className="divide-y divide-line rounded-xl border border-line">
                  {d.pool.map((p) => (
                    <li key={p.domain} className={`flex items-center justify-between gap-3 px-3.5 py-2.5 text-[13px] ${p.domain === b.domain ? "bg-brand-wash/50" : ""}`}>
                      <span className="min-w-0 truncate font-medium text-ink">{p.name}{p.domain === b.domain && <span className="ml-1.5 font-normal text-muted">(you)</span>}</span>
                      <span className="flex shrink-0 items-center gap-3">
                        <span className="tabular text-ink-2">{usd(p.dollars_per_degree)}/°F</span>
                        <SideBadge side={p.side} />
                      </span>
                    </li>
                  ))}
                </ul>
                <p className="text-[13px] leading-relaxed text-ink-2">
                  Net, the pool is hurt by <span className="font-medium text-ink">{rec.net_dollars_per_degree < 0 ? "heat" : "cold"}</span> at{" "}
                  <span className="tabular font-medium text-ink">{usd(Math.abs(rec.net_dollars_per_degree))}/°F</span>.
                  That remainder is what goes to Gemini.
                </p>
              </div>
            </Card>
          </div>

          {/* History */}
          <Card className={loading ? "opacity-60 transition-opacity" : "transition-opacity"}>
            <SectionHead eyebrow={`${d.hub?.station} station`} title="Daily highs against the last four years"
                         sub="The dashed line is your break-even temperature. Days past it cost you money."
                         right={<Segmented label="Date range" options={RANGES} value={days} onChange={setDays} />} />
            <div className="px-3 pb-4 sm:px-5">
              <HistoryChart rows={d.temperature_history} baseline={b.baseline_temp_f} side={b.side} />
            </div>
            <div className="flex flex-wrap gap-5 border-t border-line px-6 py-4 sm:px-8">
              <LegendItem color={b.side === "cold_hurt" ? "#2a78d6" : "#eb6834"} label={days === 365 ? "Past 12 months" : `Past ${days} days`} />
              <span className="inline-flex items-center gap-2 text-[13px] text-ink-2"><span className="h-2.5 w-4 rounded-sm bg-[#bdbcb4]/60" />Range of the four years before</span>
              <LegendItem color="#898781" label="Normal for the date" />
              <LegendItem color="#52514e" label={`Your break-even, ${b.baseline_temp_f}°F`} dashed />
            </div>
          </Card>

          {d.simulation && <SimulationCard d={d} />}

          <WhatIf d={d} />

          <AgentsCard domain={b.domain} />

          {/* Under the hood */}
          <Card>
            <details className="group">
              <summary className="flex cursor-pointer list-none items-center justify-between px-6 py-5 sm:px-8">
                <span>
                  <span className="block text-[15px] font-medium">Under the hood</span>
                  <span className="block text-[13px] text-ink-2">Contracts the pool buys for {longDate(rec.date)}, and how prices are set</span>
                </span>
                <span className="text-muted transition-transform group-open:rotate-180" aria-hidden>▾</span>
              </summary>
              <div className="border-t border-line px-6 py-6 sm:px-8">
                {rec.contracts.length ? (
                  <table className="w-full text-[13px]">
                    <thead className="text-left text-muted">
                      <tr><th className="pb-2 font-normal">Buy YES on</th><th className="pb-2 text-right font-normal">Contracts</th><th className="pb-2 text-right font-normal">Price</th><th className="pb-2 text-right font-normal">Cost</th><th className="pb-2 pl-6 font-normal">Price from</th></tr>
                    </thead>
                    <tbody className="tabular divide-y divide-line">
                      {rec.contracts.map((c) => (
                        <tr key={c.bucket}>
                          <td className="py-2.5 text-ink">{c.bucket}</td>
                          <td className="py-2.5 text-right">{c.contracts.toLocaleString()}</td>
                          <td className="py-2.5 text-right">{Math.round(c.price * 100)}¢</td>
                          <td className="py-2.5 text-right">{usd(c.cost, 2)}</td>
                          <td className="py-2.5 pl-6 text-ink-2">{c.price_source === "market maker" ? "Market maker's ask" : c.price_source === "market" ? "Gemini order book" : "Our forecast (no quote yet)"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                ) : <p className="text-[13px] text-ink-2">No contracts needed: the forecast doesn&apos;t threaten the pool tomorrow.</p>}
                <p className="mt-5 max-w-3xl text-[13px] leading-relaxed text-ink-2">
                  Each contract pays $1 if tomorrow&apos;s high lands in its range. Odds come from 82 runs of two weather
                  models (GFS and ECMWF) at the station Gemini settles on. Prices are the market maker&apos;s current asks:
                  its forecast odds plus a spread. Members swap their weather swings with the pool, so a heat-hurt
                  shop&apos;s bad day is partly paid by a cold-hurt shop&apos;s good day, and only the pool&apos;s net
                  leftover is hedged.
                </p>
              </div>
            </details>
          </Card>
        </>
      )}
    </div>
  );
}

/* What if tomorrow's high is X? Same pool math as the simulation. */
function WhatIf({ d }: { d: Dashboard }) {
  const b = d.business, fc = d.forecast!, rec = d.recommendation!, sim = d.simulation!;
  const mean = Math.round(fc.mean_high_f);
  const [t, setT] = useState(mean + (b.side === "cold_hurt" ? -6 : 6));
  const [rolled, setRolled] = useState<number | null>(null);
  const sign = b.side === "heat_hurt" ? -1 : 1;
  const unhedged = sign * b.dollars_per_degree! * (t - fc.mean_high_f);
  const payout = rec.contracts
    .filter((c) => { const { lo, hi } = labelBounds(c.bucket); return (lo == null || t >= lo) && (hi == null || t <= hi); })
    .reduce((sum, c) => sum + c.contracts, 0);
  const poolSwing = rec.net_dollars_per_degree * (t - fc.mean_high_f);
  const hedged = sim.share * (poolSwing + payout - rec.pool_daily_cost);
  const max = Math.max(Math.abs(unhedged), Math.abs(hedged), 50);
  const lo = mean - 12, hi = mean + 12;

  function roll() {
    // One draw from the forecast: Normal(mean, sd), rounded like NWS reports.
    const u = 1 - Math.random(), v = Math.random();
    const z = Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v);
    const x = Math.min(hi, Math.max(lo, Math.round(fc.mean_high_f + z * fc.sd_f)));
    setT(x);
    setRolled(x);
  }

  return (
    <Card>
      <SectionHead eyebrow="Try it" title="What if tomorrow surprises us?"
                   sub={`Pick tomorrow's high, or roll one from the forecast. Results are compared with a day at the forecast of ${fc.mean_high_f.toFixed(0)}°F.`}
                   right={<button onClick={roll} className="rounded-lg border border-line-strong/70 bg-card px-3.5 py-2 text-[13px] font-medium text-ink transition-colors hover:bg-wash">Roll tomorrow&apos;s weather</button>} />
      <div className="grid gap-8 px-6 pb-8 sm:px-8 lg:grid-cols-[1fr_1.2fr] lg:items-center">
        <div>
          <p className="flex items-baseline gap-3">
            <span className="text-[56px] font-semibold leading-none tracking-tight tabular">{t}°F</span>
            {rolled === t && <span className="rounded-full bg-brand-wash px-2.5 py-1 text-xs font-medium text-brand">Rolled from the forecast</span>}
          </p>
          <input type="range" min={lo} max={hi} value={t} onChange={(e) => { setT(Number(e.target.value)); setRolled(null); }}
                 aria-label="Tomorrow's high temperature" className="mt-6 w-full accent-[var(--color-brand)]" />
          <div className="mt-1 flex justify-between text-[12px] text-muted tabular"><span>{lo}°F</span><span>forecast {mean}°F</span><span>{hi}°F</span></div>
          <p className="mt-4 text-[13px] text-ink-2">
            {payout > 0
              ? <>The pool&apos;s contracts pay out <span className="tabular font-medium text-ink">{usd(payout)}</span> at this temperature.</>
              : <>None of the pool&apos;s contracts pay out at this temperature.</>}
          </p>
        </div>
        <ul className="space-y-4">
          {[
            { label: "Without hedge", v: unhedged, color: "#bdbcb4" },
            { label: "With hedge", v: hedged, color: "#4a3aa7" },
          ].map((r) => (
            <li key={r.label} className="grid grid-cols-[104px_1fr_80px] items-center gap-4 text-[13px]">
              <span className="text-ink-2">{r.label}</span>
              <span className="relative h-8 rounded-[4px] bg-wash">
                <span className="absolute inset-y-0 left-1/2 w-px bg-line-strong" />
                <span className="absolute inset-y-0 rounded-[4px] transition-all duration-300"
                      style={{ background: r.color, width: `${(Math.abs(r.v) / max) * 50}%`, left: r.v < 0 ? `${50 - (Math.abs(r.v) / max) * 50}%` : "50%" }} />
              </span>
              <span className={`tabular text-right text-[15px] font-medium ${r.label === "With hedge" ? "text-brand" : "text-ink"}`}>{usdSigned(r.v)}</span>
            </li>
          ))}
          <li className="pl-[120px] text-[13px] text-muted">vs. a day at the forecast</li>
        </ul>
      </div>
    </Card>
  );
}

function SimulationCard({ d }: { d: Dashboard }) {
  const sim = d.simulation!;
  const cut = Math.round((1 - sim.hedged.stdev / sim.unhedged.stdev) * 100);
  const avgCost = sim.unhedged.mean - sim.hedged.mean;
  return (
    <Card>
      <SectionHead eyebrow={`${sim.days.toLocaleString()} possible tomorrows`} title="How much the hedge evens things out"
                   sub={`Each simulated day draws tomorrow's high from the forecast (${sim.forecast_mean_f}°F ± ${sim.forecast_sd_f.toFixed(1)}°F) and settles the pool's real contracts. In the pool, good days fund other members' bad days, so your results bunch up near the middle.`} />
      <div className="px-3 pb-2 sm:px-5"><SimHistogram bins={sim.histogram} /></div>
      <div className="flex flex-wrap gap-5 px-6 pb-5 sm:px-8">
        <span className="inline-flex items-center gap-2 text-[13px] text-ink-2"><span className="size-2.5 rounded-sm bg-[#bdbcb4]" />Without hedge</span>
        <span className="inline-flex items-center gap-2 text-[13px] text-ink-2"><span className="size-2.5 rounded-sm bg-brand" />With hedge</span>
        <span className="text-[13px] text-muted">Days per result, vs. a day at the forecast</span>
      </div>
      <div className="grid grid-cols-1 divide-y divide-line border-t border-line sm:grid-cols-3 sm:divide-x sm:divide-y-0">
        <div className="p-6 sm:p-7">
          <Stat label="Worst day" value={<>{usd(sim.unhedged.worst)} <span className="text-muted">→</span> <span className="text-brand">{usd(sim.hedged.worst)}</span></>}
                note="Without the hedge, then with it" />
        </div>
        <div className="p-6 sm:p-7">
          <Stat label="Day-to-day swings" value={`${cut}% smaller`}
                note={`Typical swing ${usd(sim.unhedged.stdev)} unhedged, ${usd(sim.hedged.stdev)} hedged`} />
        </div>
        <div className="p-6 sm:p-7">
          <Stat label="Average cost" value={`${usd(avgCost, 2)}/day`}
                note={`You pay ${usd(sim.premium, 2)} up front; payouts on ${sim.days_hedge_paid.toLocaleString()} of ${sim.days.toLocaleString()} days bring most of it back.`} />
        </div>
      </div>
    </Card>
  );
}

function Skeleton() {
  return (
    <div className="animate-pulse space-y-6" aria-label="Loading">
      <div className="flex gap-4"><div className="size-14 rounded-xl bg-wash" /><div className="space-y-3"><div className="h-7 w-64 rounded bg-wash" /><div className="h-4 w-48 rounded bg-wash" /></div></div>
      <div className="h-32 rounded-2xl bg-wash" />
      <div className="grid gap-6 lg:grid-cols-2"><div className="h-72 rounded-2xl bg-wash" /><div className="h-72 rounded-2xl bg-wash" /></div>
    </div>
  );
}

function ErrorState({ message }: { message: string }) {
  return (
    <Card className="mx-auto max-w-lg p-8 text-center">
      <p className="font-medium">We couldn&apos;t load this dashboard.</p>
      <p className="mt-1 text-[15px] text-ink-2">{message}</p>
      <Link href="/" className="mt-5 inline-block rounded-lg bg-brand px-4 py-2 text-[13px] font-medium text-white hover:bg-brand-ink">Start over</Link>
    </Card>
  );
}
