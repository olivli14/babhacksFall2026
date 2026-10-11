// AI-generated with Claude (Anthropic).
"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { BRAND } from "@/lib/brand";
import { Business, getBusinesses, onboard } from "@/lib/api";
import { Button, SideBadge, Wordmark } from "@/components/ui";

const STEPS = [
  "Reading your website",
  "Working out how weather affects your sales",
  "Finding your nearest weather market",
  "Pooling you with nearby businesses",
];

const HOW = [
  ["We read your website", "What you sell tells us whether hot or cold days cost you money."],
  ["We find your weather market", "Gemini runs a daily high-temperature market for 49 US cities. We match you to the closest one."],
  ["We pair you with your opposite", "A ramen shop and an ice cream shop cancel each other out. Only what's left gets hedged, so it costs less."],
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
      <header className="mx-auto flex max-w-[1180px] items-end justify-between px-6 pb-4 pt-8 sm:px-10">
        <Wordmark />
        <p className="hidden text-[13px] text-muted sm:block">Weather hedging for small businesses, on Gemini prediction markets</p>
      </header>
      <div className="mx-auto max-w-[1180px] px-6 sm:px-10"><div className="border-t border-line" /></div>

      <main className="mx-auto grid max-w-[1180px] gap-14 px-6 pb-24 pt-12 sm:px-10 lg:grid-cols-[1fr_430px] lg:gap-20 lg:pt-16">
        <div>
          <h1 className="serif text-[60px] leading-[0.98] text-ink sm:text-[76px]">
            Welcome to <em className="italic">{BRAND}</em>.
          </h1>
          <p className="mt-7 max-w-[34rem] text-[19px] leading-[1.55] text-ink-2">
            A heat wave can wipe out a week of ramen sales. A cold snap does the same to an ice cream shop.
            {" "}{BRAND} puts businesses like these in the same pool, so one&apos;s bad day is the other&apos;s good day,
            and hedges what&apos;s left on Gemini&apos;s weather markets.
          </p>

          <ol className="mt-16 grid gap-8 sm:grid-cols-3 sm:gap-6">
            {HOW.map(([title, body], i) => (
              <li key={title} className="border-t border-line-strong pt-4">
                <p className="tabular text-[13px] text-muted">0{i + 1}</p>
                <p className="mt-2 font-medium text-ink">{title}</p>
                <p className="mt-1.5 text-[14px] leading-relaxed text-ink-2">{body}</p>
              </li>
            ))}
          </ol>
        </div>

        <div>
          <div className="rounded-xl border border-line bg-card p-7 shadow-sm sm:p-8">
            <h2 className="display text-[22px]">Get started</h2>
            <p className="mt-2 text-[14px] text-ink-2">Takes about a minute the first time we see a website.</p>

            {busy ? (
              <ol className="mt-8 space-y-4" aria-live="polite">
                {STEPS.map((s, i) => (
                  <li key={s} className="flex items-center gap-3 text-[15px]">
                    {i < step ? (
                      <span className="flex size-5 items-center justify-center bg-ink text-page">
                        <svg width="10" height="10" viewBox="0 0 10 10" aria-hidden><path d="M2 5.2 4 7l4-4.5" stroke="currentColor" strokeWidth="1.6" fill="none" strokeLinecap="round" strokeLinejoin="round" /></svg>
                      </span>
                    ) : i === step ? (
                      <span className="size-5 animate-spin rounded-full border-2 border-line border-t-ink" />
                    ) : (
                      <span className="size-5 border border-line-strong" />
                    )}
                    <span className={i <= step ? "text-ink" : "text-muted"}>{s}</span>
                  </li>
                ))}
              </ol>
            ) : (
              <form onSubmit={submit} className="mt-7 space-y-5">
                <Field label="Business website" htmlFor="url">
                  <input id="url" required value={url} onChange={(e) => setUrl(e.target.value)}
                         placeholder="yourshop.com" autoComplete="url" inputMode="url" className={inputCls} />
                </Field>
                <Field label="City" htmlFor="city" optional hint="Needed if you have more than one location.">
                  <input id="city" value={city} onChange={(e) => setCity(e.target.value)}
                         placeholder="Los Angeles, CA" className={inputCls} />
                </Field>
                <Field label="Annual revenue" htmlFor="rev" optional hint="Sizes your exposure. Leave blank to use a typical shop.">
                  <div className="relative">
                    <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted">$</span>
                    <input id="rev" value={revenue} onChange={(e) => setRevenue(e.target.value)}
                           placeholder="1,500,000" inputMode="numeric" className={`${inputCls} pl-6`} />
                  </div>
                </Field>
                {error && <p role="alert" className="border-l-2 border-bad pl-3 text-[14px] text-bad">{error}</p>}
                <Button type="submit" className="w-full py-3.5 text-[15px]">See what the weather costs you →</Button>
              </form>
            )}
          </div>

          {demos.length > 0 && !busy && (
            <div className="mt-10">
              <p className="text-[13px] text-muted">Or open one we&apos;ve already analyzed</p>
              <ul className="mt-3 border-t border-line">
                {demos.map((b) => (
                  <li key={`${b.domain}-${b.address}`} className="border-b border-line">
                    <button onClick={() => router.push(`/dashboard/${encodeURIComponent(b.domain)}`)}
                            className="group flex w-full items-center gap-3 py-3 text-left">
                      {b.logo_url
                        ? <img src={b.logo_url} alt="" className="size-8 rounded border border-line bg-white object-contain" />
                        : <span className="size-8 bg-wash" />}
                      <span className="min-w-0 flex-1">
                        <span className="block truncate text-[15px] font-medium group-hover:underline">{b.name || b.domain}</span>
                        <span className="block truncate text-[13px] text-muted">{b.gemini_city ?? "No market"}</span>
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
  "w-full rounded-md border border-line-strong bg-white px-3 py-2.5 text-[15px] text-ink placeholder:text-muted/70 outline-none transition-colors focus:border-ink focus:ring-2 focus:ring-ink/10";

function Field({ label, htmlFor, optional, hint, children }: {
  label: string; htmlFor: string; optional?: boolean; hint?: string; children: React.ReactNode;
}) {
  return (
    <div>
      <label htmlFor={htmlFor} className="flex items-baseline justify-between text-[14px] font-medium text-ink">
        {label}
        {optional && <span className="text-[13px] font-normal text-muted">Optional</span>}
      </label>
      <div className="mt-1.5">{children}</div>
      {hint && <p className="mt-1.5 text-[13px] text-muted">{hint}</p>}
    </div>
  );
}
