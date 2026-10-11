"use client";

import { useCallback, useEffect, useState } from "react";
import {
  api, bucketLabel, pct, usd,
  type Health, type LiveStatus, type MarketResp, type Mode, type Profile,
  type Recommendation, type Scenario,
} from "@/lib/api";

// ---------- small building blocks ----------

function Badge({ mode }: { mode: Mode }) {
  return mode === "sandbox" ? (
    <span className="rounded-full bg-emerald-100 px-2.5 py-0.5 text-xs font-semibold tracking-wide text-emerald-800">
      ● LIVE SANDBOX
    </span>
  ) : (
    <span className="rounded-full bg-amber-100 px-2.5 py-0.5 text-xs font-semibold tracking-wide text-amber-800">
      SIMULATED
    </span>
  );
}

function Panel({ title, mode, subtitle, children }: {
  title: string; mode?: Mode; subtitle?: string; children: React.ReactNode;
}) {
  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <div>
          <h2 className="text-lg font-semibold text-slate-900">{title}</h2>
          {subtitle && <p className="text-sm text-slate-500">{subtitle}</p>}
        </div>
        {mode && <Badge mode={mode} />}
      </div>
      {children}
    </section>
  );
}

function Stat({ label, value, tone = "neutral", hint }: {
  label: string; value: string; tone?: "neutral" | "good" | "bad"; hint?: string;
}) {
  const color = tone === "good" ? "text-emerald-600" : tone === "bad" ? "text-rose-600" : "text-slate-900";
  return (
    <div className="rounded-xl bg-slate-50 p-4">
      <div className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</div>
      <div className={`mt-1 text-2xl font-semibold tabular-nums ${color}`}>{value}</div>
      {hint && <div className="mt-1 text-xs text-slate-500">{hint}</div>}
    </div>
  );
}

const btn = "rounded-lg px-4 py-2 text-sm font-semibold transition disabled:cursor-not-allowed disabled:opacity-50";
const btnPrimary = `${btn} bg-slate-900 text-white hover:bg-slate-700`;
const btnGhost = `${btn} border border-slate-300 text-slate-700 hover:bg-slate-100`;

// ---------- profile ----------

const FIELDS: { key: keyof Profile; label: string; type: "text" | "number" }[] = [
  { key: "business_type", label: "Business", type: "text" },
  { key: "location", label: "City", type: "text" },
  { key: "baseline_revenue", label: "Normal daily revenue ($)", type: "number" },
  { key: "threshold_f", label: "Comfort threshold (°F)", type: "number" },
  { key: "loss_per_degree", label: "Revenue lost per °F ($)", type: "number" },
  { key: "premium_budget", label: "Hedge budget ($)", type: "number" },
];

function ProfilePanel({ profile, setProfile, mode }: {
  profile: Profile | null; setProfile: (p: Profile) => void; mode: Mode;
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState<Profile | null>(profile);
  useEffect(() => setDraft(profile), [profile]);

  const loadPreset = async () => {
    const r = await api<{ ice_cream: Profile }>("/presets");
    setProfile(r.ice_cream);
    setEditing(false);
  };

  return (
    <Panel title="1 · Your business" subtitle="How does the weather affect your sales?" mode={mode}>
      {!profile ? (
        <div className="flex flex-wrap items-center gap-3">
          <button className={btnPrimary} onClick={loadPreset}>🍦 Ice cream shop preset</button>
          <span className="text-sm text-slate-500">Chat intake coming soon. Start with the preset.</span>
        </div>
      ) : editing && draft ? (
        <div className="space-y-3">
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {FIELDS.map((f) => (
              <label key={f.key} className="text-sm">
                <span className="text-slate-600">{f.label}</span>
                <input
                  className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 tabular-nums"
                  type={f.type}
                  value={String(draft[f.key])}
                  onChange={(e) => setDraft({
                    ...draft,
                    [f.key]: f.type === "number" ? Number(e.target.value) : e.target.value,
                  })}
                />
              </label>
            ))}
            <label className="text-sm">
              <span className="text-slate-600">Bad weather is</span>
              <select
                className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2"
                value={draft.bad_direction}
                onChange={(e) => setDraft({ ...draft, bad_direction: e.target.value as "below" | "above" })}
              >
                <option value="below">colder than the threshold</option>
                <option value="above">hotter than the threshold</option>
              </select>
            </label>
          </div>
          <div className="flex gap-2">
            <button className={btnPrimary} onClick={() => { setProfile(draft); setEditing(false); }}>Save</button>
            <button className={btnGhost} onClick={() => { setDraft(profile); setEditing(false); }}>Cancel</button>
          </div>
        </div>
      ) : (
        <div className="flex flex-wrap items-start justify-between gap-4">
          <p className="max-w-2xl text-slate-700">
            A <b>{profile.business_type}</b> in <b>{profile.location}</b> making about{" "}
            <b>{usd(profile.baseline_revenue)}</b> a day. Every °F the high is{" "}
            {profile.bad_direction === "below" ? "below" : "above"} <b>{profile.threshold_f}°F</b> costs about{" "}
            <b>{usd(profile.loss_per_degree)}</b> in sales. Hedge budget: <b>{usd(profile.premium_budget)}</b>.
          </p>
          <div className="flex gap-2">
            <button className={btnGhost} onClick={() => setEditing(true)}>Edit</button>
            <button className={btnGhost} onClick={loadPreset}>Reset preset</button>
          </div>
        </div>
      )}
    </Panel>
  );
}

// ---------- market ----------

function MarketPanel({ market, error }: { market: MarketResp | null; error: string | null }) {
  return (
    <Panel
      title="2 · Forecast & market"
      subtitle={market ? `${market.event_title} · real Gemini contracts, quoted by our market-maker agent` : "Loading…"}
      mode={market?.mode}
    >
      {error && <p className="text-sm text-rose-600">{error}</p>}
      {market && (
        <div className="overflow-x-auto">
          <table className="w-full text-sm tabular-nums">
            <thead className="text-left text-xs uppercase tracking-wide text-slate-500">
              <tr>
                <th className="py-2 pr-4">Daily high</th>
                <th className="py-2 pr-4">Forecast chance</th>
                <th className="py-2 pr-4 text-right">MM bid</th>
                <th className="py-2 pr-4 text-right">MM ask</th>
                <th className="py-2 pr-4 text-right">MM inventory</th>
                <th className="py-2 text-left font-mono normal-case text-slate-400">Gemini symbol</th>
              </tr>
            </thead>
            <tbody>
              {market.contracts.map((c) => {
                const q = c.mm_quotes;
                const net = q ? q.inventory_yes - q.inventory_no : 0;
                return (
                  <tr key={c.symbol} className="border-t border-slate-100">
                    <td className="py-2 pr-4 font-medium text-slate-900">{bucketLabel(c.bucket)}</td>
                    <td className="py-2 pr-4">
                      <div className="flex items-center gap-2">
                        <div className="h-2 w-28 rounded-full bg-slate-100">
                          <div className="h-2 rounded-full bg-sky-500" style={{ width: pct(c.fair_value) }} />
                        </div>
                        <span>{pct(c.fair_value)}</span>
                      </div>
                    </td>
                    <td className="py-2 pr-4 text-right text-emerald-700">{q ? `$${q.bid.toFixed(2)}` : "—"}</td>
                    <td className="py-2 pr-4 text-right text-rose-700">{q ? `$${q.ask.toFixed(2)}` : "—"}</td>
                    <td className="py-2 pr-4 text-right text-slate-600">
                      {net === 0 ? "flat" : net > 0 ? `long ${net}` : `short ${-net}`}
                    </td>
                    <td className="py-2 font-mono text-xs text-slate-400">{c.symbol}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          <p className="mt-2 text-xs text-slate-400">
            Prices are $ per contract that pays $1. Updates every 2.5 s. Forecast is a placeholder model until the NWS
            model lands.
          </p>
        </div>
      )}
    </Panel>
  );
}

// ---------- hedge ----------

function HedgePanel({ profile, mode, onHedged }: {
  profile: Profile | null; mode: Mode; onHedged: (pid: string, executed: boolean) => void;
}) {
  const [rec, setRec] = useState<Recommendation | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => { setRec(null); setStatus(null); setErr(null); }, [profile]);

  const recommend = async () => {
    if (!profile) return;
    setBusy(true); setErr(null); setStatus(null);
    try {
      const r = await api<{ recommendation: Recommendation; profile_id: string }>("/hedge", {
        method: "POST", body: JSON.stringify({ profile }),
      });
      setRec(r.recommendation);
      onHedged(r.profile_id, false);
    } catch (e) { setErr(String(e)); } finally { setBusy(false); }
  };

  const execute = async () => {
    if (!profile) return;
    setBusy(true); setErr(null);
    try {
      const r = await api<{ recommendation: Recommendation; profile_id: string; status: string; order_ids: string[] }>(
        "/hedge/execute", { method: "POST", body: JSON.stringify({ profile }) });
      setRec(r.recommendation);
      setStatus(`${r.status.toUpperCase()} · ${r.order_ids.length} orders (${r.order_ids.join(", ")})`);
      onHedged(r.profile_id, true);
    } catch (e) { setErr(String(e)); } finally { setBusy(false); }
  };

  return (
    <Panel title="3 · The hedge" subtitle="Our shop agent sizes protection to the revenue at risk" mode={mode}>
      {!profile && <p className="text-sm text-slate-500">Pick a business first.</p>}
      {profile && (
        <div className="space-y-4">
          <div className="flex flex-wrap gap-2">
            <button className={btnPrimary} onClick={recommend} disabled={busy}>Get recommendation</button>
            <button className={btnPrimary} onClick={execute} disabled={busy || !rec}>Execute hedge</button>
          </div>
          {err && <p className="text-sm text-rose-600">{err}</p>}
          {rec && (
            <>
              <blockquote className="rounded-xl border-l-4 border-sky-500 bg-sky-50 p-4 text-slate-800">
                {rec.explanation}
              </blockquote>
              <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
                <Stat label="Chance of bad weather" value={pct(rec.prob_bad_weather)} />
                <Stat label="Expected lost sales" value={usd(rec.expected_lost_revenue)} />
                <Stat label="Premium paid" value={usd(rec.premium)} />
                <Stat label="Max payout" value={usd(rec.max_payout)} hint={`covers ${pct(rec.coverage)} of target`} />
              </div>
              <table className="w-full text-sm tabular-nums">
                <thead className="text-left text-xs uppercase tracking-wide text-slate-500">
                  <tr>
                    <th className="py-2">Buy YES on</th><th>Chance</th><th className="text-right">Loss if it happens</th>
                    <th className="text-right">Contracts</th><th className="text-right">Price</th><th className="text-right">Cost</th>
                  </tr>
                </thead>
                <tbody>
                  {rec.legs.map((l) => (
                    <tr key={l.symbol} className="border-t border-slate-100">
                      <td className="py-2 font-medium">{bucketLabel(l.bucket)}</td>
                      <td>{pct(l.prob)}</td>
                      <td className="text-right">{usd(l.loss_if_hit)}</td>
                      <td className="text-right">{l.qty}</td>
                      <td className="text-right">${l.ask.toFixed(2)}</td>
                      <td className="text-right">{usd(l.cost)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {status && <p className="text-sm font-medium text-emerald-700">Order status: {status}</p>}
            </>
          )}
        </div>
      )}
    </Panel>
  );
}

// ---------- scenarios ----------

function ScenarioPanel({ profileId, executed, mode }: { profileId: string | null; executed: boolean; mode: Mode }) {
  const [data, setData] = useState<{ hot: Scenario; cold: Scenario } | null>(null);
  const [which, setWhich] = useState<"hot" | "cold">("cold");

  useEffect(() => {
    if (!profileId) { setData(null); return; }
    api<{ hot: Scenario; cold: Scenario }>(`/scenarios?profile_id=${profileId}`).then(setData).catch(() => setData(null));
  }, [profileId, executed]);

  const s = data?.[which];
  const max = s ? Math.max(s.net, s.net_unhedged, 1) : 1;

  return (
    <Panel title="4 · What happens on the day" subtitle="Toggle the weather and compare hedged vs. unhedged" mode={mode}>
      {!data && <p className="text-sm text-slate-500">Get a recommendation to see the scenarios.</p>}
      {data && s && (
        <div className="space-y-4">
          <div className="inline-flex rounded-xl bg-slate-100 p-1">
            {(["hot", "cold"] as const).map((k) => (
              <button
                key={k}
                onClick={() => setWhich(k)}
                className={`rounded-lg px-5 py-2 text-sm font-semibold transition ${
                  which === k ? "bg-white text-slate-900 shadow" : "text-slate-500 hover:text-slate-700"}`}
              >
                {k === "hot" ? "☀️ Hot day" : "🌧️ Cold day"} · {data[k].temp_f}°F
              </button>
            ))}
          </div>
          <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
            <Stat label="Store revenue" value={usd(s.revenue)} />
            <Stat
              label="Hedge P&L"
              value={(s.hedge_pnl >= 0 ? "+" : "") + usd(s.hedge_pnl)}
              tone={s.hedge_pnl >= 0 ? "good" : "bad"}
              hint={`payout ${usd(s.hedge_payout)} − premium ${usd(s.premium)}`}
            />
            <Stat label="Net result" value={usd(s.net)} hint={`without hedge: ${usd(s.net_unhedged)}`} />
          </div>
          <div className="space-y-2">
            {[["Without hedge", s.net_unhedged, "bg-slate-400"], ["With hedge", s.net, "bg-sky-500"]].map(([label, v, c]) => (
              <div key={label as string} className="flex items-center gap-3 text-sm">
                <span className="w-28 text-slate-600">{label}</span>
                <div className="h-6 flex-1 rounded bg-slate-100">
                  <div className={`h-6 rounded ${c}`} style={{ width: `${(100 * (v as number)) / max}%` }} />
                </div>
                <span className="w-20 text-right font-semibold tabular-nums">{usd(v as number)}</span>
              </div>
            ))}
          </div>
          <p className="text-sm text-slate-600">
            {which === "cold"
              ? "On a cold day the contracts pay out and soften the hit to sales."
              : "On a hot day sales are fine and the premium is the cost of the insurance."}
            {!executed && " (Preview: hedge not executed yet.)"}
          </p>
        </div>
      )}
    </Panel>
  );
}

// ---------- live sandbox ----------

function LivePanel() {
  const [live, setLive] = useState<LiveStatus | null>(null);
  const [token, setToken] = useState("");
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    try { setToken(sessionStorage.getItem("demoToken") || ""); } catch {}
    const tick = () => api<LiveStatus>("/live").then(setLive).catch(() => {});
    tick();
    const id = setInterval(tick, 3000);
    return () => clearInterval(id);
  }, []);

  const call = async (path: string, body?: object) => {
    setErr(null);
    try { sessionStorage.setItem("demoToken", token); } catch {}
    try {
      await api(path, { method: "POST", body: JSON.stringify(body || {}), headers: { "X-Demo-Admin-Token": token } });
    } catch (e) { setErr(String(e)); }
  };

  return (
    <Panel
      title="5 · Same agents, real Gemini sandbox"
      subtitle="Gemini's sandbox has no weather markets yet, so the agents trade a live crypto/commodity contract. Real signed orders, real fills."
      mode="sandbox"
    >
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <input
          className="w-56 rounded-lg border border-slate-300 px-3 py-2 text-sm"
          type="password" placeholder="Admin token" value={token}
          onChange={(e) => setToken(e.target.value)}
        />
        <button className={btnPrimary} disabled={!token || live?.running} onClick={() => call("/live/start", { seconds: 180 })}>
          Start 3-min live run
        </button>
        <button className={btnGhost} disabled={!token || !live?.running} onClick={() => call("/live/stop")}>Stop</button>
        {live?.running && <span className="text-sm font-medium text-emerald-700">● running on {live.symbol}</span>}
      </div>
      {err && <p className="mb-2 text-sm text-rose-600">{err}</p>}
      <pre className="max-h-72 overflow-auto rounded-xl bg-slate-900 p-4 text-xs leading-relaxed text-slate-100">
        {live?.log?.length ? live.log.join("\n") : "No live run yet."}
      </pre>
    </Panel>
  );
}

// ---------- page ----------

export default function Home() {
  const [health, setHealth] = useState<Health | null>(null);
  const [profile, setProfile] = useState<Profile | null>(null);
  const [market, setMarket] = useState<MarketResp | null>(null);
  const [marketErr, setMarketErr] = useState<string | null>(null);
  const [profileId, setProfileId] = useState<string | null>(null);
  const [executed, setExecuted] = useState(false);
  const mode: Mode = health?.mode ?? "mock";

  const poll = useCallback(() => {
    api<MarketResp>("/market").then((m) => { setMarket(m); setMarketErr(null); })
      .catch((e) => setMarketErr(`Can't reach the backend (${e.message}).`));
  }, []);

  useEffect(() => {
    api<Health>("/health").then(setHealth).catch(() => {});
    poll();
    const id = setInterval(poll, 2500);
    return () => clearInterval(id);
  }, [poll]);

  useEffect(() => { setProfileId(null); setExecuted(false); }, [profile]);

  return (
    <main className="mx-auto max-w-6xl space-y-5 px-4 py-8">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-slate-900">Weather Hedge</h1>
          <p className="text-slate-600">
            AI agents that protect small businesses from bad weather on Gemini prediction markets.
          </p>
        </div>
        <div className="text-right text-xs text-slate-500">
          {health ? (
            <>
              <div>Market maker: {health.mm_running ? "running" : "stopped"}</div>
              <div>Gemini sandbox: {health.sandbox_ok ? "connected" : "unreachable"}</div>
            </>
          ) : "Connecting…"}
        </div>
      </header>

      <ProfilePanel profile={profile} setProfile={setProfile} mode={mode} />
      <MarketPanel market={market} error={marketErr} />
      <HedgePanel profile={profile} mode={mode} onHedged={(pid, ex) => { setProfileId(pid); setExecuted(ex); }} />
      <ScenarioPanel profileId={profileId} executed={executed} mode={mode} />
      <LivePanel />

      <footer className="pt-2 text-xs text-slate-400">
        SIMULATED panels: our agents trade real Gemini weather contract definitions on our own order book. LIVE SANDBOX:
        real orders on Gemini&apos;s sandbox exchange.
      </footer>
    </main>
  );
}
