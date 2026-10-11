// AI-generated with Claude (Anthropic).
import Link from "next/link";
import { BRAND } from "@/lib/brand";
import { SOURCES } from "@/lib/sources";
import { Wordmark } from "@/components/ui";

const STEPS = [
  ["Tell us about your business", "Your name, location and website. What you sell tells us whether hot or cold days cost you money."],
  ["We find your weather market", "Gemini runs a daily high-temperature market for 49 US cities. We match you to the station closest to you."],
  ["We pool you with your opposite", "Businesses hurt by heat and businesses hurt by cold cancel each other out. The pool only hedges what's left."],
];

export default function Landing() {
  return (
    <div className="min-h-screen">
      <nav className="mx-auto flex max-w-[1180px] items-center justify-between px-6 pb-4 pt-8 sm:px-10">
        <Wordmark />
        <div className="flex items-center gap-6 text-[14px]">
          <a href="#how" className="hidden text-ink-2 hover:text-ink sm:inline">How it works</a>
          <a href="#method" className="hidden text-ink-2 hover:text-ink sm:inline">Methodology</a>
          <Link href="/start" className="rounded-md bg-ink px-4 py-2 font-medium text-white hover:bg-black">Get started</Link>
        </div>
      </nav>
      <div className="mx-auto max-w-[1180px] px-6 sm:px-10"><div className="border-t border-line" /></div>

      <main className="mx-auto max-w-[1180px] px-6 sm:px-10">
        {/* Hero */}
        <section className="grid gap-12 pb-20 pt-16 lg:grid-cols-[1.15fr_1fr] lg:items-end lg:pt-24">
          <div>
            <h1 className="serif text-[56px] leading-[1.0] text-ink sm:text-[80px]">
              Weather shouldn&apos;t decide your month.
            </h1>
            <p className="mt-7 max-w-[34rem] text-[19px] leading-[1.55] text-ink-2">
              A heat wave can wipe out a week of ramen sales. A cold snap does the same to an ice cream shop.
              {" "}{BRAND} pools businesses like these so one&apos;s bad day is covered by the other&apos;s good day,
              and hedges what&apos;s left on Gemini&apos;s weather markets.
            </p>
            <div className="mt-9 flex flex-wrap items-center gap-4">
              <Link href="/start" className="rounded-md bg-ink px-5 py-3 text-[15px] font-medium text-white hover:bg-black">
                See what the weather costs you →
              </Link>
              <Link href="/dashboard/dkramen.com" className="text-[15px] text-ink-2 underline-offset-4 hover:text-ink hover:underline">
                Or open a sample business
              </Link>
            </div>
          </div>

          {/* The idea in one picture */}
          <div className="rounded-xl border border-line bg-card p-7 shadow-sm">
            <p className="text-[13px] text-muted">Example: tomorrow comes in 5°F hotter than forecast</p>
            <ul className="mt-5 space-y-4">
              <Row label="Ramen shop" sub="loses $62 per °F of heat" value={-310} />
              <Row label="Ice cream shop" sub="gains $50 per °F of heat" value={250} />
            </ul>
            <div className="mt-5 border-t border-line pt-5">
              <Row label="The pool, together" sub={`Only this gets hedged on Gemini`} value={-60} strong />
            </div>
          </div>
        </section>

        {/* How it works */}
        <section id="how" className="scroll-mt-8 border-t border-line-strong py-16">
          <div className="grid gap-x-14 gap-y-8 lg:grid-cols-[250px_1fr]">
            <div>
              <p className="tabular text-[13px] text-muted">01</p>
              <h2 className="display mt-2 text-[22px]">How it works</h2>
            </div>
            <ol className="grid gap-8 sm:grid-cols-3 sm:gap-6">
              {STEPS.map(([title, body], i) => (
                <li key={title} className="border-t border-line pt-4">
                  <p className="tabular text-[13px] text-muted">Step {i + 1}</p>
                  <p className="mt-2 font-medium text-ink">{title}</p>
                  <p className="mt-1.5 text-[14px] leading-relaxed text-ink-2">{body}</p>
                </li>
              ))}
            </ol>
          </div>
        </section>

        {/* Why it costs less */}
        <section className="border-t border-line-strong py-16">
          <div className="grid gap-x-14 gap-y-8 lg:grid-cols-[250px_1fr]">
            <div>
              <p className="tabular text-[13px] text-muted">02</p>
              <h2 className="display mt-2 text-[22px]">Why pooling costs less</h2>
            </div>
            <div className="grid gap-8 text-[15px] leading-relaxed text-ink-2 sm:grid-cols-2">
              <p>
                Protection is priced by how much risk you need covered. Hedging alone, a ramen shop and an ice cream
                shop each buy contracts for their own bad weather, and pay for both. In a pool, most of that risk
                cancels before anything is bought, so the pool buys far fewer contracts.
              </p>
              <p>
                The trade-off is fair and simple: on your good days, part of your windfall goes to members having a bad
                one, and theirs comes to you. You give up some big days in exchange for no wiped-out weeks.
              </p>
            </div>
          </div>
        </section>

        {/* Gemini */}
        <section className="border-t border-line-strong py-16">
          <div className="grid gap-x-14 gap-y-8 lg:grid-cols-[250px_1fr]">
            <div>
              <p className="tabular text-[13px] text-muted">03</p>
              <h2 className="display mt-2 text-[22px]">Built on Gemini</h2>
            </div>
            <div className="grid gap-8 text-[15px] leading-relaxed text-ink-2 sm:grid-cols-3">
              <p><span className="font-medium text-ink">Real contracts.</span> Gemini lists daily high-temperature markets for 49 US cities, each settled on the National Weather Service report.</p>
              <p><span className="font-medium text-ink">Real forecasts.</span> We price every temperature range from 82 runs of two weather models, GFS and ECMWF.</p>
              <p><span className="font-medium text-ink">AI agents.</span> A market-maker agent quotes every range; the pool&apos;s agent buys the ranges that protect it.</p>
            </div>
          </div>
        </section>

        {/* Methodology */}
        <section id="method" className="scroll-mt-8 border-t border-line-strong py-16">
          <div className="grid gap-x-14 gap-y-8 lg:grid-cols-[250px_1fr]">
            <div>
              <p className="tabular text-[13px] text-muted">04</p>
              <h2 className="display mt-2 text-[22px]">Methodology</h2>
              <p className="mt-3 text-[14px] leading-relaxed text-ink-2">
                Our pricing follows standard weather-derivative and insurance methods. Where our numbers are
                assumptions, we say so.
              </p>
            </div>
            <div>
              <ul className="divide-y divide-line border-y border-line">
                {SOURCES.methods.map((m) => (
                  <li key={m.title} className="grid gap-2 py-5 sm:grid-cols-[220px_1fr] sm:gap-8">
                    <p className="font-medium text-ink">{m.title}</p>
                    <div className="text-[14px] leading-relaxed text-ink-2">
                      <p>{m.body}</p>
                      {m.cites.length > 0 && (
                        <p className="mt-2 text-[13px] text-muted">
                          {m.cites.map((c, i) => (
                            <span key={c.url}>
                              {i > 0 && "; "}
                              <a href={c.url} target="_blank" rel="noreferrer" className="underline underline-offset-2 hover:text-ink">{c.label}</a>
                            </span>
                          ))}
                        </p>
                      )}
                    </div>
                  </li>
                ))}
              </ul>
              {SOURCES.caveat && <p className="mt-5 text-[13px] leading-relaxed text-muted">{SOURCES.caveat}</p>}
            </div>
          </div>
        </section>

        {/* Closing CTA */}
        <section className="border-t border-line-strong py-20 text-center">
          <h2 className="serif text-[44px] leading-tight text-ink">What does the weather cost you?</h2>
          <p className="mt-3 text-[16px] text-ink-2">Takes about a minute. You&apos;ll see your exposure, your pool and your price.</p>
          <Link href="/start" className="mt-8 inline-block rounded-md bg-ink px-5 py-3 text-[15px] font-medium text-white hover:bg-black">
            Get started →
          </Link>
        </section>
      </main>

      <footer className="border-t border-line">
        <div className="mx-auto flex max-w-[1180px] flex-wrap justify-between gap-4 px-6 py-8 text-[13px] text-muted sm:px-10">
          <span>{BRAND}. Weather hedging for small businesses.</span>
          <span>Contracts and prices from Gemini prediction markets. Trading shown is on a simulated exchange.</span>
        </div>
      </footer>
    </div>
  );
}

function Row({ label, sub, value, strong }: { label: string; sub: string; value: number; strong?: boolean }) {
  const max = 310;
  const w = (Math.abs(value) / max) * 50;
  return (
    <li className="list-none">
      <div className="flex items-baseline justify-between">
        <div>
          <p className={`text-[15px] ${strong ? "font-semibold text-ink" : "font-medium text-ink"}`}>{label}</p>
          <p className="text-[13px] text-muted">{sub}</p>
        </div>
        <p className={`display tabular text-[24px] ${value < 0 ? "text-ink" : "text-ink-2"}`}>
          {value < 0 ? "−" : "+"}${Math.abs(value)}
        </p>
      </div>
      <div className="relative mt-2 h-2.5 bg-wash">
        <span className="absolute inset-y-0 left-1/2 w-px bg-line-strong" />
        <span className="absolute inset-y-0" style={{ background: strong ? "#171717" : value < 0 ? "#d9541e" : "#2463b8",
              width: `${w}%`, left: value < 0 ? `${50 - w}%` : "50%" }} />
      </div>
    </li>
  );
}
