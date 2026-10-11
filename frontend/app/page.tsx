// AI-generated with Claude (Anthropic).
"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { BRAND } from "@/lib/brand";
import { Business, getBusinesses, onboard } from "@/lib/api";
import { SideBadge, Wordmark } from "@/components/ui";

const STEPS = [
  "Reading your website",
  "Working out how weather affects your sales",
  "Finding your nearest weather market",
  "Pooling you with nearby businesses",
];

const HOW = [
  ["We read your website", "What you sell tells us whether hot or cold days cost you money."],
  ["We find your weather market", "Gemini lists a daily high-temperature market for 49 US cities. We match you to the closest."],
  ["We net you against your neighbors", "A ramen shop and an ice cream shop cancel each other out. Only the leftover gets hedged, so it costs less."],
];

export default function Onboard() {
  const router = useRouter();
  const [url, setUrl] = useState("");
  const [city, setCity] = useState("");
  const [revenue, setRevenue] = useState("");
  const [busy, setBusy] = useState(false);
  const [step, setStep] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [demos, setDemos] = useState<Business[]>([]);
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    getBusinesses().then(setDemos).catch(() => setDemos([]));
    return () => { if (timer.current) clearInterval(timer.current); };
  }, []);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    const rev = revenue.replace(/[$,\s]/g, "");
    const host = url.trim().replace(/^https?:\/\//i, "").split("/")[0];
    if (!/^[^\s.]+(\.[^\s.]+)+$/.test(host)) {
      setError("Enter your full website address, like yourshop.com.");
      return;
    }
    if (rev && !(Number(rev) > 0)) {
      setError("Annual revenue should be a number, like 1,500,000.");
      return;
    }
    setBusy(true);
    setStep(0);
    // Steps advance on a timer; the last one holds until the server answers.
    timer.current = setInterval(() => setStep((s) => Math.min(s + 1, STEPS.length - 1)), 2500);
    try {
      const res = await onboard({
        url: url.trim(),
        city: city.trim() || undefined,
        annual_revenue: rev ? Number(rev) : undefined,
      });
      router.push(`/dashboard/${encodeURIComponent(res.domain)}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
      setBusy(false);
    } finally {
      if (timer.current) clearInterval(timer.current);
    }
  }

  return (
    <div className="min-h-screen">
      <header className="mx-auto flex max-w-6xl items-center justify-between px-6 py-6 sm:px-10">
        <Wordmark />
        <span className="text-[13px] text-muted">Built on Gemini prediction markets</span>
      </header>

      <main className="mx-auto grid max-w-6xl gap-12 px-6 pb-20 pt-6 sm:px-10 lg:grid-cols-[1.05fr_1fr] lg:gap-16 lg:pt-14">
        <div className="max-w-xl">
          <h1 className="text-[44px] font-semibold leading-[1.05] tracking-[-0.03em] text-ink sm:text-[56px]">
            Welcome to {BRAND}.
          </h1>
          <p className="mt-5 text-lg leading-relaxed text-ink-2">
            Hot weeks and cold snaps move your sales. {BRAND} pools you with nearby businesses
            that weather affects the opposite way, then hedges what&apos;s left on Gemini&apos;s
            weather markets.
          </p>

          <ol className="mt-12 space-y-7">
            {HOW.map(([title, body], i) => (
              <li key={title} className="flex gap-4">
                <span className="mt-0.5 flex size-7 shrink-0 items-center justify-center rounded-full bg-brand-wash text-[13px] font-semibold text-brand">
                  {i + 1}
                </span>
                <div>
                  <p className="font-medium text-ink">{title}</p>
                  <p className="mt-1 text-[15px] leading-relaxed text-ink-2">{body}</p>
                </div>
              </li>
            ))}
          </ol>
        </div>

        <div>
          <div className="rounded-2xl border border-line bg-card p-7 shadow-[0_1px_2px_rgba(0,0,0,0.04),0_8px_24px_-12px_rgba(0,0,0,0.08)] sm:p-9">
            <h2 className="text-xl font-semibold tracking-tight">Tell us about your business</h2>
            <p className="mt-1.5 text-[15px] text-ink-2">Takes about a minute the first time we see a website.</p>

            {busy ? (
              <ol className="mt-8 space-y-4" aria-live="polite">
                {STEPS.map((s, i) => (
                  <li key={s} className="flex items-center gap-3 text-[15px]">
                    {i < step ? (
                      <span className="flex size-5 items-center justify-center rounded-full bg-brand text-white">
                        <svg width="10" height="10" viewBox="0 0 10 10" aria-hidden><path d="M2 5.2 4 7l4-4.5" stroke="currentColor" strokeWidth="1.6" fill="none" strokeLinecap="round" strokeLinejoin="round" /></svg>
                      </span>
                    ) : i === step ? (
                      <span className="size-5 animate-spin rounded-full border-2 border-brand-wash border-t-brand" />
                    ) : (
                      <span className="size-5 rounded-full border-2 border-line" />
                    )}
                    <span className={i <= step ? "text-ink" : "text-muted"}>{s}</span>
                  </li>
                ))}
              </ol>
            ) : (
              <form onSubmit={submit} className="mt-7 space-y-5">
                <Field label="Business website" htmlFor="url">
                  <input id="url" required value={url} onChange={(e) => setUrl(e.target.value)}
                         placeholder="yourshop.com" autoComplete="url" inputMode="url"
                         className={inputCls} />
                </Field>
                <Field label="City" htmlFor="city" optional hint="Needed if you have more than one location.">
                  <input id="city" value={city} onChange={(e) => setCity(e.target.value)}
                         placeholder="Los Angeles, CA" className={inputCls} />
                </Field>
                <Field label="Annual revenue" htmlFor="rev" optional hint="Sizes your exposure. Leave blank to use a typical shop.">
                  <div className="relative">
                    <span className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-muted">$</span>
                    <input id="rev" value={revenue} onChange={(e) => setRevenue(e.target.value)}
                           placeholder="1,500,000" inputMode="numeric" className={`${inputCls} pl-7`} />
                  </div>
                </Field>
                {error && <p role="alert" className="rounded-lg bg-[#fbeaea] px-3.5 py-2.5 text-sm text-bad">{error}</p>}
                <button type="submit"
                        className="w-full rounded-xl bg-brand px-4 py-3.5 text-[15px] font-medium text-white transition-colors hover:bg-brand-ink focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand">
                  See my weather exposure
                </button>
              </form>
            )}
          </div>

          {demos.length > 0 && !busy && (
            <div className="mt-8">
              <p className="text-[13px] font-medium text-ink-2">Or open a business we&apos;ve already analyzed</p>
              <ul className="mt-3 divide-y divide-line overflow-hidden rounded-xl border border-line bg-card">
                {demos.map((b) => (
                  <li key={`${b.domain}-${b.address}`}>
                    <button onClick={() => router.push(`/dashboard/${encodeURIComponent(b.domain)}`)}
                            className="flex w-full items-center gap-3 px-4 py-3 text-left transition-colors hover:bg-wash">
                      {b.logo_url
                        ? <img src={b.logo_url} alt="" className="size-8 rounded-md border border-line object-contain bg-white" />
                        : <span className="size-8 rounded-md bg-wash" />}
                      <span className="min-w-0 flex-1">
                        <span className="block truncate text-[15px] font-medium">{b.name || b.domain}</span>
                        <span className="block truncate text-[13px] text-muted">{b.domain} · {b.gemini_city ?? "No market"}</span>
                      </span>
                      <SideBadge side={b.side} />
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}

const inputCls =
  "w-full rounded-xl border border-line-strong/70 bg-white px-3.5 py-3 text-[15px] text-ink placeholder:text-muted/80 outline-none transition-shadow focus:border-brand focus:ring-4 focus:ring-brand/10";

function Field({ label, htmlFor, optional, hint, children }: {
  label: string; htmlFor: string; optional?: boolean; hint?: string; children: React.ReactNode;
}) {
  return (
    <div>
      <label htmlFor={htmlFor} className="flex items-baseline justify-between text-sm font-medium text-ink">
        {label}
        {optional && <span className="text-[13px] font-normal text-muted">Optional</span>}
      </label>
      <div className="mt-1.5">{children}</div>
      {hint && <p className="mt-1.5 text-[13px] text-muted">{hint}</p>}
    </div>
  );
}
