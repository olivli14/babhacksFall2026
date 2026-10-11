// AI-generated with Claude (Anthropic).
import Link from "next/link";
import { BRAND } from "@/lib/brand";
import { Side, sideLabel } from "@/lib/api";

export function Wordmark({ href = "/" }: { href?: string }) {
  return (
    <Link href={href} className="inline-flex items-center gap-2.5 text-ink">
      <svg width="22" height="22" viewBox="0 0 22 22" aria-hidden>
        <rect width="22" height="22" rx="6" fill="var(--color-brand)" />
        <path d="M5 13.5c2-3 4-3 6 0s4 3 6 0" stroke="white" strokeWidth="2" fill="none" strokeLinecap="round" />
      </svg>
      <span className="text-[17px] font-semibold tracking-tight">{BRAND}</span>
    </Link>
  );
}

export function Card({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return (
    <section className={`rounded-2xl border border-line bg-card ${className}`}>{children}</section>
  );
}

export function SectionHead({
  eyebrow, title, sub, right,
}: { eyebrow?: string; title: string; sub?: React.ReactNode; right?: React.ReactNode }) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-4 px-6 pt-6 pb-4 sm:px-8 sm:pt-7">
      <div className="max-w-2xl">
        {eyebrow && <p className="mb-1.5 text-xs font-medium uppercase tracking-[0.08em] text-muted">{eyebrow}</p>}
        <h2 className="text-lg font-semibold tracking-tight text-ink">{title}</h2>
        {sub && <p className="mt-1 text-sm leading-relaxed text-ink-2">{sub}</p>}
      </div>
      {right}
    </div>
  );
}

export function Stat({
  label, value, note, tone = "ink",
}: { label: string; value: React.ReactNode; note?: React.ReactNode; tone?: "ink" | "brand" }) {
  return (
    <div className="min-w-0">
      <p className="text-[13px] text-ink-2">{label}</p>
      <p className={`mt-1.5 text-[28px] font-semibold leading-none tracking-tight ${tone === "brand" ? "text-brand" : "text-ink"}`}>
        {value}
      </p>
      {note && <p className="mt-2 text-[13px] leading-snug text-muted">{note}</p>}
    </div>
  );
}

export function SideBadge({ side }: { side: Side }) {
  const style =
    side === "heat_hurt" ? "bg-heat-wash text-[#9a3a12]" :
    side === "cold_hurt" ? "bg-cold-wash text-[#1c5cab]" : "bg-wash text-ink-2";
  const dot = side === "heat_hurt" ? "bg-heat" : side === "cold_hurt" ? "bg-cold" : "bg-muted";
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium ${style}`}>
      <span className={`size-1.5 rounded-full ${dot}`} />
      {sideLabel[side]}
    </span>
  );
}

export function Segmented<T extends string | number>({
  options, value, onChange, label,
}: { options: { value: T; label: string }[]; value: T; onChange: (v: T) => void; label: string }) {
  return (
    <div role="radiogroup" aria-label={label} className="inline-flex rounded-lg bg-wash p-0.5">
      {options.map((o) => (
        <button
          key={o.value}
          role="radio"
          aria-checked={o.value === value}
          onClick={() => onChange(o.value)}
          className={`rounded-md px-3 py-1.5 text-[13px] font-medium transition-colors ${
            o.value === value ? "bg-card text-ink shadow-[0_1px_2px_rgba(0,0,0,0.08)]" : "text-ink-2 hover:text-ink"
          }`}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

export function LegendItem({ color, label, dashed }: { color: string; label: string; dashed?: boolean }) {
  return (
    <span className="inline-flex items-center gap-2 text-[13px] text-ink-2">
      <svg width="18" height="8" aria-hidden>
        <line x1="1" y1="4" x2="17" y2="4" stroke={color} strokeWidth="2" strokeLinecap="round"
              strokeDasharray={dashed ? "3 3" : undefined} />
      </svg>
      {label}
    </span>
  );
}
