// AI-generated with Claude (Anthropic).
"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { Dashboard, getDashboard, labelBounds, longDate, usd, usdSigned } from "@/lib/api";
import { Button, LegendItem, Section, Segmented, SideBadge, Stat, Swatch, Wordmark } from "@/components/ui";
import { C, CostCompare, ForecastBars, HistoryChart, OutcomeRanges } from "@/components/charts";
import { AgentsCard, ModeBadge } from "@/components/agents";

const RANGES = [
  { value: 30, label: "30 days" },
  { value: 90, label: "90 days" },
  { value: 365, label: "12 months" },
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
      <header className="mx-auto flex max-w-[1180px] items-end justify-between px-6 pb-4 pt-8 sm:px-10">
        <Wordmark />
        <Link href="/" className="text-[14px] text-ink-2 underline-offset-4 hover:text-ink hover:underline">
          Analyze another business
        </Link>
      </header>
      <div className="mx-auto max-w-[1180px] px-6 sm:px-10"><div className="border-t border-line" /></div>

      <main className="mx-auto max-w-[1180px] px-6 pb-24 pt-10 sm:px-10">
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
  const city = d.hub?.gemini_city ?? "your city";
  const hurtColor = b.side === "cold_hurt" ? "text-cold" : "text-heat";
  const ready = rec && fc && b.dollars_per_degree != null && b.baseline_temp_f != null;

  return (
    <div>
      {/* Masthead */}
      <div className="flex flex-wrap items-start justify-between gap-8">
        <div className="flex items-start gap-5">
          {b.logo_url
            ? <img src={b.logo_url} alt="" className="size-14 rounded-lg border border-line bg-white object-contain p-1" />
            : <span className="size-14 rounded-lg bg-wash" />}
          <div>
            <h1 className="display text-[40px] leading-none">{b.name || b.domain}</h1>
            <p className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-[14px] text-ink-2">
              <SideBadge side={b.side} />
              <span>{[b.domain, b.address].filter(Boolean).join(" · ")}</span>
            </p>
            {b.reason_codes?.length > 0 && (
              <p className="mt-1.5 text-[13px] text-muted">
                From your website: {b.reason_codes.map((r) => r.replace(" x", " ×")).join(", ")}
              </p>
            )}
          </div>
        </div>
        {d.hub && (
          <dl className="grid grid-cols-[auto_auto] gap-x-5 gap-y-1 text-[13px]">
            <dt className="text-muted">Weather market</dt><dd className="text-ink">{d.hub.gemini_city}</dd>
            <dt className="text-muted">Station</dt><dd className="text-ink">{d.hub.station}</dd>
            {d.hub.distance_miles != null && (<><dt className="text-muted">Distance</dt><dd className="text-ink">{d.hub.distance_miles} mi</dd></>)}
          </dl>
        )}
      </div>

      {b.side === "needs_review" && (
        <p className="display mt-12 max-w-3xl text-[24px] leading-snug">
          We couldn&apos;t tell whether hot or cold weather hurts this business. Try its menu page, or another URL.
        </p>
      )}

      {ready && (
        <>
          {/* The lede: the whole story in one sentence */}
          <p className="mb-14 mt-12 max-w-[50rem] text-[24px] font-normal leading-[1.45] tracking-[-0.01em] text-ink-2 sm:text-[28px]">
            {b.name || b.domain} loses about{" "}
            <span className={`font-semibold ${hurtColor}`}>{usd(b.dollars_per_degree!)}</span> for every degree {city} goes{" "}
            {b.side === "cold_hurt" ? "below" : "above"} {b.baseline_temp_f}°F. Tomorrow should reach{" "}
            <span className="font-semibold text-ink">{fc!.mean_high_f.toFixed(0)}°F</span>. Hedged alone, that protection costs{" "}
            <span className="text-muted line-through decoration-1">{usd(rec!.standalone_daily_cost, 2)}</span>; in the pool,{" "}
            <span className="font-semibold text-ink">{usd(rec!.your_daily_cost, 2)}</span>.
          </p>

          <Section n="01" title={<>Tomorrow in {city}</>}
                   note={<>{longDate(fc!.date)}. Chance of each range Gemini trades, from {fc!.members} forecast runs. Colored ranges cost you money.</>}>
            <ForecastBars buckets={fc!.buckets} side={b.side} baseline={b.baseline_temp_f!} />
          </Section>

          <Section n="02" title="Your pool"
                   note={`Businesses hurt by heat and businesses hurt by cold cancel out. The pool only hedges what's left, which is why it costs ${rec!.pool_savings_pct}% less.`}>
            <div className="grid gap-10 xl:grid-cols-2">
              <div>
                <CostCompare alone={rec!.standalone_daily_cost} pooled={rec!.your_daily_cost} />
                <p className="mt-5 text-[14px] leading-relaxed text-ink-2">
                  Net, the pool is hurt by <span className="font-medium text-ink">{rec!.net_dollars_per_degree < 0 ? "heat" : "cold"}</span>{" "}
                  at <span className="tabular font-medium text-ink">{usd(Math.abs(rec!.net_dollars_per_degree))} per °F</span>. That leftover is what goes to Gemini.
                </p>
              </div>
              <table className="w-full self-start text-[14px]">
                <thead><tr className="border-b border-line-strong text-left text-[13px] text-muted"><th className="pb-2 font-normal">Member</th><th className="pb-2 font-normal">Hurt by</th><th className="pb-2 text-right font-normal">Per °F</th></tr></thead>
                <tbody>
                  {d.pool.map((p) => (
                    <tr key={p.domain} className="border-b border-line">
                      <td className="py-2.5 font-medium text-ink">{p.name}{p.domain === b.domain && <span className="ml-2 text-[13px] font-normal text-muted">you</span>}</td>
                      <td className="py-2.5"><SideBadge side={p.side} /></td>
                      <td className="tabular py-2.5 text-right text-ink-2">{usd(p.dollars_per_degree)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Section>

          <Section n="03" title="The last twelve months" dim={loading}
                   note={`Daily highs at ${d.hub?.station}. The band is the range of the four years before; the dashed line is your break-even.`}
                   aside={<Segmented label="Date range" options={RANGES} value={days} onChange={setDays} />}>
            <HistoryChart rows={d.temperature_history} baseline={b.baseline_temp_f} side={b.side} />
            <div className="mt-3 flex flex-wrap gap-5">
              <LegendItem color={b.side === "cold_hurt" ? C.cold : C.heat} label={days === 365 ? "Past 12 months" : `Past ${days} days`} />
              <Swatch color={C.prior} label="Range, four years before" />
              <LegendItem color={C.muted} label="Normal for the date" />
              <LegendItem color={C.ink2} label={`Break-even, ${b.baseline_temp_f}°F`} dashed />
            </div>
          </Section>

          {d.simulation && <Simulation d={d} />}

          <WhatIf d={d} />

          <Section n="06" title="Agents at work" aside={<ModeBadge />}
                   note="Two AI agents trade Gemini's real contracts for tomorrow. The market maker prices every range from the forecast and quotes both sides; the pool's agent buys the ranges that protect the pool.">
            <AgentsCard domain={b.domain} />
          </Section>

          <Section n="07" title="How it works"
                   note="Each contract pays $1 if tomorrow's high lands in its range.">
            {rec!.contracts.length ? (
              <table className="w-full text-[14px]">
                <thead>
                  <tr className="border-b border-line-strong text-left text-[13px] text-muted">
                    <th className="pb-2 font-normal">The pool buys</th><th className="pb-2 text-right font-normal">Contracts</th>
                    <th className="pb-2 text-right font-normal">Price</th><th className="pb-2 text-right font-normal">Cost</th>
                  </tr>
                </thead>
                <tbody className="tabular">
                  {rec!.contracts.map((c) => (
                    <tr key={c.bucket} className="border-b border-line">
                      <td className="py-2.5 text-ink">{c.bucket}</td>
                      <td className="py-2.5 text-right">{c.contracts.toLocaleString()}</td>
                      <td className="py-2.5 text-right">{Math.round(c.price * 100)}¢</td>
                      <td className="py-2.5 text-right">{usd(c.cost, 2)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : <p className="text-[14px] text-ink-2">No contracts needed: the forecast doesn&apos;t threaten the pool tomorrow.</p>}
            <div className="mt-8 grid gap-6 text-[14px] leading-relaxed text-ink-2 sm:grid-cols-3">
              <p><span className="font-medium text-ink">Odds.</span> 82 runs of two weather models, GFS and ECMWF, at the station Gemini settles on.</p>
              <p><span className="font-medium text-ink">Prices.</span> The market maker&apos;s current asks: its forecast odds plus a small spread.</p>
              <p><span className="font-medium text-ink">Pooling.</span> Members swap their weather swings with the pool. A good day pays into it; a bad day is paid from it.</p>
            </div>
          </Section>
        </>
      )}
    </div>
  );
}

function Simulation({ d }: { d: Dashboard }) {
  const sim = d.simulation!;
  const cut = Math.round((1 - sim.hedged.stdev / sim.unhedged.stdev) * 100);
  return (
    <Section n="04" title="A thousand tomorrows"
             note={`We drew 1,000 possible highs for tomorrow from the forecast (${sim.forecast_mean_f}°F, give or take ${sim.forecast_sd_f.toFixed(1)}°) and worked out your result each time, with and without the pool's hedge.`}>
      <OutcomeRanges unhedged={sim.unhedged} hedged={sim.hedged} />
      <p className="mt-4 text-[13px] text-muted">
        Thick bar: where 9 days in 10 land. Thin line: the worst and best day. Results are compared with a day at the forecast.
      </p>
      <div className="mt-10 grid gap-8 sm:grid-cols-3 sm:gap-0 sm:divide-x sm:divide-line">
        <div className="sm:pr-8">
          <Stat label="Worst day" value={<><span className="text-muted">{usd(sim.unhedged.worst)}</span> → {usd(sim.hedged.worst)}</>}
                note="Without the hedge, then with it" />
        </div>
        <div className="sm:px-8">
          <Stat label="Day-to-day swings" value={`${cut}% smaller`}
                note={`A typical day moves ${usd(sim.unhedged.stdev)} unhedged, ${usd(sim.hedged.stdev)} hedged.`} />
        </div>
        <div className="sm:pl-8">
          <Stat label="What it costs" value={`${usd(sim.avg_cost, 2)} a day`}
                note={`on average. You pay ${usd(sim.premium, 2)} up front; the contracts pay out on ${sim.days_hedge_paid} of ${sim.days.toLocaleString()} days and return most of it.`} />
        </div>
      </div>
    </Section>
  );
}

/* What if tomorrow's high is X? Same pool math as the simulation. */
function WhatIf({ d }: { d: Dashboard }) {
  const b = d.business, fc = d.forecast!, rec = d.recommendation!, sim = d.simulation;
  const mean = Math.round(fc.mean_high_f);
  const [t, setT] = useState(mean + (b.side === "cold_hurt" ? -6 : 6));
  const [rolled, setRolled] = useState<number | null>(null);
  if (!sim) return null;
  const sign = b.side === "heat_hurt" ? -1 : 1;
  const unhedged = sign * b.dollars_per_degree! * (t - fc.mean_high_f);
  const payout = rec.contracts
    .filter((c) => { const { lo, hi } = labelBounds(c.bucket); return (lo == null || t >= lo) && (hi == null || t <= hi); })
    .reduce((sum, c) => sum + c.contracts, 0);
  const hedged = sim.share * (rec.net_dollars_per_degree * (t - fc.mean_high_f) + payout - rec.pool_daily_cost);
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
    <Section n="05" title="What if tomorrow surprises us?"
             note={`Pick a high, or roll one from the forecast. Results are compared with a day at the forecast of ${fc.mean_high_f.toFixed(0)}°F.`}
             aside={<Button variant="outline" onClick={roll}>Roll tomorrow&apos;s weather</Button>}>
      <div className="grid gap-12 xl:grid-cols-[1fr_1.15fr] xl:items-center">
        <div>
          <p className="flex items-baseline gap-4">
            <span className="display tabular text-[64px] leading-none">{t}°F</span>
            {rolled === t && <span className="text-[13px] text-muted">rolled from the forecast</span>}
          </p>
          <input type="range" min={lo} max={hi} value={t} onChange={(e) => { setT(Number(e.target.value)); setRolled(null); }}
                 aria-label="Tomorrow's high temperature" className="mt-6 w-full" />
          <div className="tabular mt-1 flex justify-between text-[12px] text-muted"><span>{lo}°F</span><span>forecast {mean}°F</span><span>{hi}°F</span></div>
          <p className="mt-5 text-[14px] text-ink-2">
            {payout > 0
              ? <>The pool&apos;s contracts pay out <span className="tabular font-medium text-ink">{usd(payout)}</span> at this temperature.</>
              : <>None of the pool&apos;s contracts pay out at this temperature.</>}
          </p>
        </div>
        <ul className="space-y-5">
          {[
            { label: "Without the hedge", v: unhedged, color: C.prior },
            { label: "With the hedge", v: hedged, color: C.ink },
          ].map((r) => (
            <li key={r.label}>
              <div className="flex items-baseline justify-between text-[13px]">
                <span className="text-ink-2">{r.label}</span>
                <span className="display tabular text-[22px] leading-none text-ink">{usdSigned(r.v)}</span>
              </div>
              <span className="relative mt-2 block h-7 bg-wash">
                <span className="absolute inset-y-0 left-1/2 w-px bg-line-strong" />
                <span className="absolute inset-y-0 transition-all duration-300"
                      style={{ background: r.color, width: `${(Math.abs(r.v) / max) * 50}%`, left: r.v < 0 ? `${50 - (Math.abs(r.v) / max) * 50}%` : "50%" }} />
              </span>
            </li>
          ))}
          <li className="text-[13px] text-muted">Left of center is a loss, right is a gain, compared with a day at the forecast.</li>
        </ul>
      </div>
    </Section>
  );
}

function Skeleton() {
  return (
    <div className="animate-pulse space-y-8" aria-label="Loading">
      <div className="flex gap-5"><div className="size-14 bg-wash" /><div className="space-y-3"><div className="h-12 w-80 bg-wash" /><div className="h-4 w-56 bg-wash" /></div></div>
      <div className="h-24 max-w-3xl bg-wash" />
      <div className="h-64 bg-wash" />
    </div>
  );
}

function ErrorState({ message }: { message: string }) {
  return (
    <div className="mx-auto max-w-xl py-20 text-center">
      <p className="display text-[24px]">We couldn&apos;t load this dashboard.</p>
      <p className="mt-2 text-[15px] text-ink-2">{message}</p>
      <Link href="/" className="mt-6 inline-block text-[14px] underline underline-offset-4">Start over</Link>
    </div>
  );
}
