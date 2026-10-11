// AI-generated with Claude (Anthropic).
// Typed client for the backend. The frontend holds no secrets and calls only this API.
export const API_URL = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").replace(/\/$/, "");

export type Side = "heat_hurt" | "cold_hurt" | "needs_review";

export interface Business {
  domain: string;
  name: string | null;
  logo_url: string | null;
  address: string | null;
  side: Side;
  confidence: number;
  reason_codes: string[];
  business_type: string | null;
  baseline_temp_f: number | null;
  annual_revenue: number | null;
  dollars_per_degree: number | null;
  dollars_per_degree_source: "revenue" | "default" | null;
  gemini_city: string | null;
  distance_miles: number | null;
}

export interface Bucket {
  label: string;
  model_prob: number;
  market_price: number | null;
  temp_f: number;
}

export interface Dashboard {
  business: Business;
  hub: { gemini_city: string; code: string | null; station: string; distance_miles: number | null } | null;
  forecast: {
    date: string;
    mean_high_f: number;
    sd_f: number;
    source: "ensemble" | "climatology";
    members: number;
    buckets: Bucket[];
  } | null;
  recommendation: {
    date: string;
    your_daily_cost: number;
    standalone_daily_cost: number;
    pool_daily_cost: number;
    priced_by: "market maker" | "forecast";
    pool_standalone_cost: number;
    pool_savings_pct: number;
    pool_size: number;
    net_dollars_per_degree: number;
    contracts: { bucket: string; contracts: number; price: number; price_source: string; cost: number }[];
  } | null;
  pool: { domain: string; name: string; side: Side; dollars_per_degree: number }[];
  simulation: Simulation | null;
  temperature_history: { date: string; year: number; years_back: number; high_f: number }[];
  pnl_series: { date: string; high_f: number; normal_high_f: number; unhedged: number; hedged: number }[];
  summary: {
    days: number;
    from: string;
    to: string;
    worst_day: { date: string; high_f: number; normal_high_f: number; unhedged: number; hedged: number };
    bad_days: number;
    stdev_unhedged: number;
    stdev_hedged: number;
    daily_fee_pooled: number;
    daily_fee_alone: number;
    total_fee_pooled: number;
    total_fee_alone: number;
    total_losses_unhedged: number;
  } | null;
}

export interface SimStats { mean: number; worst: number; best: number; stdev: number; p5: number; p95: number }

export interface Simulation {
  days: number;
  forecast_mean_f: number;
  forecast_sd_f: number;
  share: number;
  premium: number;
  avg_cost: number;
  days_hedge_paid: number;
  unhedged: SimStats;
  hedged: SimStats;
  histogram: { from: number; to: number; hedged: number; unhedged: number }[];
}

export type Mode = "mock" | "sandbox";

export interface PoolMarket {
  mode: Mode;
  event: string;
  quotes: { symbol: string; bucket: string; lo: number | null; hi: number | null;
            fair_value: number | null; bid: number | null; ask: number | null; inventory: number }[];
  fills: { time: number; symbol: string; bucket: string; yes_buyer: string; yes_seller: string;
           yes_price: number; qty: number }[];
}

export interface ExecuteResult {
  mode: Mode;
  event: string;
  total_cost: number;
  orders: { bucket: string; qty: number; price?: number; filled?: number; cost?: number; status: string }[];
}

export interface LiveStatus {
  mode: Mode;
  running: boolean;
  symbol?: string | null;
  description?: string;
  error?: string | null;
  log: string[];
}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
    cache: "no-store",
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail ?? body);
    } catch {}
    throw new Error(detail);
  }
  return res.json();
}

export const getDashboard = (domain: string, days: number) =>
  api<Dashboard>(`/api/dashboard?domain=${encodeURIComponent(domain)}&days=${days}`);
export const getPoolMarket = (domain: string) =>
  api<PoolMarket>(`/api/pool/market?domain=${encodeURIComponent(domain)}`);
export const executePool = (domain: string) =>
  api<ExecuteResult>("/api/pool/execute", { method: "POST", body: JSON.stringify({ domain }) });
export const getLive = () => api<LiveStatus>("/live");
export const startLive = (token: string, seconds = 180) =>
  api<{ started: boolean }>("/live/start", {
    method: "POST", body: JSON.stringify({ seconds }), headers: { "X-Demo-Admin-Token": token },
  });

/** Gemini strike code -> readable range: LO68 -> "68°F or less", 69TO70 -> "69–70°F", HI77 -> "77°F+" */
export function strikeLabel(code: string): string {
  if (code.startsWith("LO")) return `${code.slice(2)}°F or less`;
  if (code.startsWith("HI")) return `${code.slice(2)}°F+`;
  const [a, b] = code.split("TO");
  return `${a}–${b}°F`;
}

/** Plan bucket label ("70°F to 71°F", "69°F or below", "72°F or above") -> inclusive bounds. */
export function labelBounds(label: string): { lo: number | null; hi: number | null } {
  const n = (label.match(/-?\d+/g) || []).map(Number);
  if (label.includes("below")) return { lo: null, hi: n[0] };
  if (label.includes("above")) return { lo: n[0], hi: null };
  return { lo: n[0], hi: n[1] };
}

export const getBusinesses = () => api<Business[]>("/api/businesses");
export const onboard = (body: { url: string; city?: string; annual_revenue?: number }) =>
  api<{ domain: string; profile: Business }>("/api/onboard", { method: "POST", body: JSON.stringify(body) });

// Formatting
export const usd = (n: number, digits = 0) =>
  (n < 0 ? "−$" : "$") +
  Math.abs(n).toLocaleString("en-US", { minimumFractionDigits: digits, maximumFractionDigits: digits });
export const usdSigned = (n: number) => (n > 0 ? "+" : "") + usd(n);
export const pct = (n: number) => `${Math.round(n * 100)}%`;
export const shortDate = (iso: string) =>
  new Date(iso + "T12:00:00").toLocaleDateString("en-US", { month: "short", day: "numeric" });
export const longDate = (iso: string) =>
  new Date(iso + "T12:00:00").toLocaleDateString("en-US", { weekday: "long", month: "long", day: "numeric" });

export const sideLabel: Record<Side, string> = {
  heat_hurt: "Hurt by heat",
  cold_hurt: "Hurt by cold",
  needs_review: "Needs review",
};
