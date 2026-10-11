// AI-generated with Claude (Anthropic).
"use client";

import {
  Area, CartesianGrid, ComposedChart, Line, ReferenceLine, ResponsiveContainer,
  Tooltip, XAxis, YAxis,
} from "recharts";
import { Bucket, Dashboard, Side, shortDate, usd, usdSigned } from "@/lib/api";

const C = {
  ink: "#0b0b0b", ink2: "#52514e", muted: "#898781", line: "#e7e6e1", base: "#c3c2b7",
  brand: "#4a3aa7", cold: "#2a78d6", heat: "#eb6834", prior: "#bdbcb4",
};

/* ---------- Tomorrow's forecast: one bar per Gemini bucket ---------- */

export function ForecastBars({ buckets, side, baseline }: { buckets: Bucket[]; side: Side; baseline: number }) {
  const max = Math.max(...buckets.map((b) => b.model_prob), 0.01);
  const hurts = (b: Bucket) => (side === "heat_hurt" ? b.temp_f > baseline : side === "cold_hurt" ? b.temp_f < baseline : false);
  const hurtColor = side === "cold_hurt" ? C.cold : C.heat;
  return (
    <div>
      <ul className="space-y-2.5">
        {buckets.map((b) => (
          <li key={b.label} className="group grid grid-cols-[112px_1fr_88px] items-center gap-4 text-[13px]"
              title={`${b.label}: ${Math.round(b.model_prob * 100)}% chance${b.market_price != null ? `, market ${Math.round(b.market_price * 100)}¢` : ""}`}>
            <span className="tabular text-ink-2">{b.label.replace("°F to ", "–").replace(" or below", " or less").replace(" or above", "+")}</span>
            <span className="relative h-6 rounded-[4px] bg-wash">
              <span className="absolute inset-y-0 left-0 rounded-[4px] transition-[width] duration-500"
                    style={{ width: `${(b.model_prob / max) * 100}%`, background: hurts(b) ? hurtColor : C.prior }} />
              {b.market_price != null && (
                <span className="absolute -inset-y-1 w-0.5 rounded bg-ink" style={{ left: `${Math.min(b.market_price / max, 1) * 100}%` }}
                      aria-label={`market ${Math.round(b.market_price * 100)} cents`} />
              )}
            </span>
            <span className="tabular text-right font-medium text-ink">{Math.round(b.model_prob * 100)}%</span>
          </li>
        ))}
      </ul>
      <div className="mt-4 flex flex-wrap gap-x-5 gap-y-2 text-[13px] text-ink-2">
        <span className="inline-flex items-center gap-2"><span className="size-2.5 rounded-sm" style={{ background: hurtColor }} />Costs you money</span>
        <span className="inline-flex items-center gap-2"><span className="size-2.5 rounded-sm" style={{ background: C.prior }} />Normal or better</span>
        {buckets.some((b) => b.market_price != null) && (
          <span className="inline-flex items-center gap-2"><span className="h-3 w-0.5 rounded bg-ink" />Gemini market price</span>
        )}
      </div>
    </div>
  );
}

/* ---------- Temperature history: this year vs. the range of the last four ---------- */

type HistRow = { date: string; now?: number; range?: [number, number]; normal?: number };

export function HistoryChart({ rows, baseline, side }: {
  rows: Dashboard["temperature_history"]; baseline: number | null; side: Side;
}) {
  const byDate = new Map<string, { now?: number; prior: number[] }>();
  for (const r of rows) {
    const e = byDate.get(r.date) ?? { prior: [] };
    if (r.years_back === 0) e.now = r.high_f; else e.prior.push(r.high_f);
    byDate.set(r.date, e);
  }
  const data: HistRow[] = [...byDate.entries()]
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([date, e]) => ({
      date,
      now: e.now,
      range: e.prior.length ? [Math.min(...e.prior), Math.max(...e.prior)] : undefined,
      normal: e.prior.length ? e.prior.reduce((a, b) => a + b, 0) / e.prior.length : undefined,
    }));
  const lineColor = side === "cold_hurt" ? C.cold : side === "heat_hurt" ? C.heat : C.ink;

  return (
    <ResponsiveContainer width="100%" height={300}>
      <ComposedChart data={data} margin={{ top: 8, right: 12, bottom: 0, left: -8 }}>
        <CartesianGrid vertical={false} stroke={C.line} />
        <XAxis dataKey="date" tickFormatter={shortDate} minTickGap={48} tickLine={false} axisLine={{ stroke: C.base }} />
        <YAxis tickFormatter={(v) => `${Math.round(v)}°`} tickLine={false} axisLine={false} width={44}
               domain={[(min: number) => Math.floor(min / 5) * 5 - 5, (max: number) => Math.ceil(max / 5) * 5 + 5]} />
        <Tooltip content={<HistoryTip />} cursor={{ stroke: C.base, strokeWidth: 1 }} />
        <Area dataKey="range" stroke="none" fill={C.prior} fillOpacity={0.35} isAnimationActive={false} activeDot={false} />
        <Line dataKey="normal" stroke={C.muted} strokeWidth={1} dot={false} isAnimationActive={false} activeDot={false} />
        {baseline != null && <ReferenceLine y={baseline} stroke={C.ink2} strokeDasharray="4 4" />}
        <Line dataKey="now" stroke={lineColor} strokeWidth={2} dot={false} activeDot={{ r: 4, strokeWidth: 2, stroke: "#fff" }} connectNulls />
      </ComposedChart>
    </ResponsiveContainer>
  );
}

function HistoryTip({ active, payload }: { active?: boolean; payload?: { payload: HistRow }[] }) {
  if (!active || !payload?.length) return null;
  const r = payload[0].payload;
  return (
    <div className="rounded-lg border border-line bg-card px-3 py-2.5 text-[13px] shadow-sm">
      <p className="mb-1.5 font-medium text-ink">{shortDate(r.date)}</p>
      {r.now != null && <p className="tabular flex justify-between gap-6"><span className="text-ink">High</span><span className="font-medium text-ink">{r.now.toFixed(0)}°F</span></p>}
      {r.normal != null && <p className="tabular flex justify-between gap-6"><span className="text-ink-2">Normal</span><span className="text-ink-2">{r.normal.toFixed(0)}°F</span></p>}
      {r.range && <p className="tabular flex justify-between gap-6"><span className="text-muted">Last 4 years</span><span className="text-muted">{r.range[0].toFixed(0)}–{r.range[1].toFixed(0)}°F</span></p>}
    </div>
  );
}

/* ---------- Weather P&L vs a normal day: unhedged vs hedged ---------- */

export function PnlChart({ rows }: { rows: Dashboard["pnl_series"] }) {
  return (
    <ResponsiveContainer width="100%" height={300}>
      <ComposedChart data={rows} margin={{ top: 8, right: 12, bottom: 0, left: 4 }}>
        <defs>
          <linearGradient id="unhedged" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={C.prior} stopOpacity={0.45} />
            <stop offset="100%" stopColor={C.prior} stopOpacity={0.45} />
          </linearGradient>
        </defs>
        <CartesianGrid vertical={false} stroke={C.line} />
        <XAxis dataKey="date" tickFormatter={shortDate} minTickGap={48} tickLine={false} axisLine={false} />
        <YAxis tickFormatter={(v) => usd(v)} tickLine={false} axisLine={false} width={64} />
        <Tooltip content={<PnlTip />} cursor={{ stroke: C.base, strokeWidth: 1 }} />
        <ReferenceLine y={0} stroke={C.base} />
        <Area dataKey="unhedged" type="linear" stroke={C.muted} strokeWidth={1} fill="url(#unhedged)" isAnimationActive={false} />
        <Line dataKey="hedged" type="linear" stroke={C.brand} strokeWidth={2} dot={false} activeDot={{ r: 4, strokeWidth: 2, stroke: "#fff" }} />
      </ComposedChart>
    </ResponsiveContainer>
  );
}

function PnlTip({ active, payload }: { active?: boolean; payload?: { payload: Dashboard["pnl_series"][number] }[] }) {
  if (!active || !payload?.length) return null;
  const r = payload[0].payload;
  return (
    <div className="rounded-lg border border-line bg-card px-3 py-2.5 text-[13px] shadow-sm">
      <p className="font-medium text-ink">{shortDate(r.date)}</p>
      <p className="mb-1.5 text-muted">High {r.high_f.toFixed(0)}°F · normal {r.normal_high_f.toFixed(0)}°F</p>
      <p className="tabular flex justify-between gap-6"><span className="text-ink-2">Without hedge</span><span className="text-ink">{usdSigned(r.unhedged)}</span></p>
      <p className="tabular flex justify-between gap-6"><span className="text-ink-2">With hedge</span><span className="font-medium text-brand">{usdSigned(r.hedged)}</span></p>
    </div>
  );
}

/* ---------- Two-bar comparison: alone vs pooled ---------- */

export function CostCompare({ alone, pooled }: { alone: number; pooled: number }) {
  const max = Math.max(alone, pooled, 0.01);
  const rows = [
    { label: "Hedging alone", value: alone, color: C.prior, ink: "text-ink-2" },
    { label: "In the pool", value: pooled, color: C.brand, ink: "text-ink" },
  ];
  return (
    <ul className="space-y-3">
      {rows.map((r) => (
        <li key={r.label} className="grid grid-cols-[104px_1fr_72px] items-center gap-4 text-[13px]">
          <span className="text-ink-2">{r.label}</span>
          <span className="h-7 rounded-[4px] bg-wash">
            <span className="block h-full rounded-[4px] transition-[width] duration-500" style={{ width: `${(r.value / max) * 100}%`, background: r.color }} />
          </span>
          <span className={`tabular text-right font-medium ${r.ink}`}>{usd(r.value, 2)}</span>
        </li>
      ))}
    </ul>
  );
}
