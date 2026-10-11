// AI-generated with Claude (Anthropic).
import Link from "next/link";
import { BRAND } from "@/lib/brand";
import { Side, sideLabel } from "@/lib/api";

export function Wordmark({ href = "/" }: { href?: string }) {
  return (
    <Link href={href} className="group inline-flex items-baseline gap-2 text-ink">
      <span className="display text-[28px] leading-none">{BRAND}</span>
      <svg width="26" height="8" viewBox="0 0 26 8" aria-hidden className="translate-y-[-2px]">
        <path d="M1 4c4-4 8-4 12 0s8 4 12 0" stroke="currentColor" strokeWidth="1.5" fill="none" strokeLinecap="round" />
      </svg>
    </Link>
  );
}

/** A ruled section: numbered label column on the left, content on the right. */
export function Section({
  n, title, note, children, aside, dim,
}: {
  n: string; title: React.ReactNode; note?: React.ReactNode; children: React.ReactNode;
  aside?: React.ReactNode; dim?: boolean;
}) {
  return (
    <section className={`grid gap-x-14 gap-y-6 border-t border-ink pb-16 pt-5 lg:grid-cols-[250px_1fr] ${dim ? "opacity-60 transition-opacity" : "transition-opacity"}`}>
      <header>
        <p className="tabular text-[13px] text-muted">{n}</p>
        <h2 className="display mt-2 text-[30px] leading-[1.08] text-ink">{title}</h2>
        {note && <p className="mt-3 text-[14px] leading-relaxed text-ink-2">{note}</p>}
        {aside && <div className="mt-5">{aside}</div>}
      </header>
      <div className="min-w-0">{children}</div>
    </section>
  );
}

/** A quiet container for grouped content inside a section. */
export function Card({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return <div className={`rounded-[3px] border border-line bg-card ${className}`}>{children}</div>;
}

export function Stat({
  label, value, note, tone = "ink",
}: { label: string; value: React.ReactNode; note?: React.ReactNode; tone?: "ink" | "heat" | "cold" }) {
  const color = tone === "heat" ? "text-heat" : tone === "cold" ? "text-cold" : "text-ink";
  return (
    <div className="min-w-0">
      <p className="text-[13px] text-ink-2">{label}</p>
      <p className={`display tabular mt-1 text-[44px] leading-none ${color}`}>{value}</p>
      {note && <p className="mt-2.5 text-[13px] leading-snug text-muted">{note}</p>}
    </div>
  );
}

export function SideBadge({ side }: { side: Side }) {
  const color = side === "heat_hurt" ? "text-heat" : side === "cold_hurt" ? "text-cold" : "text-muted";
  const mark = side === "heat_hurt" ? "bg-heat" : side === "cold_hurt" ? "bg-cold" : "bg-muted";
  return (
    <span className={`inline-flex items-center gap-1.5 whitespace-nowrap text-[13px] font-medium ${color}`}>
      <span className={`size-2 ${mark}`} />
      {sideLabel[side]}
    </span>
  );
}

export function Segmented<T extends string | number>({
  options, value, onChange, label,
}: { options: { value: T; label: string }[]; value: T; onChange: (v: T) => void; label: string }) {
  return (
    <div role="radiogroup" aria-label={label} className="inline-flex gap-4 text-[13px]">
      {options.map((o) => (
        <button
          key={o.value}
          role="radio"
          aria-checked={o.value === value}
          onClick={() => onChange(o.value)}
          className={`border-b pb-0.5 transition-colors ${
            o.value === value ? "border-ink font-medium text-ink" : "border-transparent text-muted hover:text-ink"
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

export function Swatch({ color, label }: { color: string; label: string }) {
  return (
    <span className="inline-flex items-center gap-2 text-[13px] text-ink-2">
      <span className="size-2.5" style={{ background: color }} />
      {label}
    </span>
  );
}

export function Button({ children, onClick, disabled, variant = "solid", type = "button", className = "" }: {
  children: React.ReactNode; onClick?: () => void; disabled?: boolean; variant?: "solid" | "outline";
  type?: "button" | "submit"; className?: string;
}) {
  const base = "inline-flex items-center justify-center gap-2 rounded-[3px] px-4 py-2.5 text-[14px] font-medium transition-colors disabled:opacity-40 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink";
  const look = variant === "solid"
    ? "bg-ink text-page hover:bg-black"
    : "border border-ink text-ink hover:bg-ink hover:text-page";
  return <button type={type} onClick={onClick} disabled={disabled} className={`${base} ${look} ${className}`}>{children}</button>;
}
