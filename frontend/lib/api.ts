export const API_URL = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").replace(/\/$/, "");

export type Mode = "mock" | "sandbox";

export interface Profile {
  business_type: string;
  location: string;
  baseline_revenue: number;
  weather_variable: "temperature_high";
  bad_direction: "below" | "above";
  threshold_f: number;
  loss_per_degree: number;
  premium_budget: number;
}

export interface Quote {
  fair_value: number;
  bid: number;
  ask: number;
  size: number;
  inventory_yes: number;
  inventory_no: number;
}

export interface ContractRow {
  symbol: string;
  bucket: string;
  lo: number | null;
  hi: number | null;
  fair_value: number;
  book: { bids: [number, number][]; asks: [number, number][] };
  mm_quotes: Quote | null;
}

export interface MarketResp {
  mode: Mode;
  event: string;
  event_title: string;
  contracts: ContractRow[];
}

export interface Leg {
  symbol: string;
  bucket: string;
  prob: number;
  loss_if_hit: number;
  ask: number;
  qty: number;
  cost: number;
}

export interface Recommendation {
  event: string;
  event_title: string;
  location: string;
  date: string;
  prob_bad_weather: number;
  expected_lost_revenue: number;
  premium: number;
  max_payout: number;
  coverage: number;
  legs: Leg[];
  explanation: string;
}

export interface Scenario {
  temp_f: number;
  revenue: number;
  hedge_payout: number;
  premium: number;
  hedge_pnl: number;
  net: number;
  net_unhedged: number;
}

export interface Health {
  mode: Mode;
  mm_running: boolean;
  mm_event: string | null;
  sandbox_ok: boolean;
  live_running: boolean;
}

export interface LiveStatus {
  mode: Mode;
  running: boolean;
  symbol?: string | null;
  description?: string;
  error?: string | null;
  mm_quote?: Quote | null;
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
    throw new Error(`${res.status}: ${detail}`);
  }
  return res.json();
}

export function bucketLabel(b: string): string {
  if (b.startsWith("LO")) return `≤ ${b.slice(2)}°F`;
  if (b.startsWith("HI")) return `≥ ${b.slice(2)}°F`;
  const [a, z] = b.split("TO");
  return `${a}–${z}°F`;
}

export const usd = (n: number) =>
  (n < 0 ? "−$" : "$") + Math.abs(n).toLocaleString(undefined, { maximumFractionDigits: 0 });
export const pct = (n: number) => `${Math.round(n * 100)}%`;
