import type { ReactNode } from "react";

export function Panel({ title, children, aside }: { title: string; children: ReactNode; aside?: ReactNode }) {
  return (
    <section className="rounded-lg border border-line bg-panel">
      <header className="flex items-center justify-between border-b border-line px-4 py-2.5">
        <h2 className="text-xs font-semibold uppercase tracking-wider text-muted">{title}</h2>
        {aside}
      </header>
      <div className="p-4">{children}</div>
    </section>
  );
}

type Tone = "good" | "warn" | "bad" | "muted";
const TONES: Record<Tone, string> = {
  good: "border-good/40 text-good",
  warn: "border-warn/40 text-warn",
  bad: "border-bad/40 text-bad",
  muted: "border-line text-muted",
};

export function Badge({ tone, children }: { tone: Tone; children: ReactNode }) {
  return (
    <span className={`inline-block rounded border px-2 py-0.5 text-xs font-medium ${TONES[tone]}`}>{children}</span>
  );
}

export function Stat({ label, value, note }: { label: string; value: ReactNode; note?: ReactNode }) {
  return (
    <div>
      <div className="text-xs text-muted">{label}</div>
      <div className="num mt-1 text-xl">{value}</div>
      {note && <div className="mt-1 text-xs text-muted">{note}</div>}
    </div>
  );
}

export function Row({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex items-baseline justify-between gap-4 py-1.5 text-sm">
      <span className="text-muted">{label}</span>
      <span className="text-right">{children}</span>
    </div>
  );
}
