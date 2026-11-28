import { useRef } from "react";
import type { Point } from "./api";

// Minimum vertical span per unit, so sensor noise does not look like a change.
const MIN_SPAN: Record<string, number> = {
  Hz: 10, rpm: 100, A: 0.5, "N·m": 1, V: 20, W: 100, "°C": 5, "mm/s": 1,
};
const W = 680, H = 110, X0 = 8, X1 = 672, Y0 = 8, Y1 = 102;

type Props = {
  name: string; unit: string; points: Point[]; duration: number; visibleT: number;
  windows: { before: [number, number]; after: [number, number] };
  color: string; clickable: boolean; onPick: (t: number) => void;
  runs?: { from: number; label: string }[];
};

export function Chart({ name, unit, points, duration, visibleT, windows, color, clickable, onPick, runs = [] }: Props) {
  const ref = useRef<SVGSVGElement>(null);
  const vals = points.map((p) => p.value).filter((v): v is number => v !== null);
  let lo = Math.min(...vals), hi = Math.max(...vals);
  if (!vals.length) { lo = 0; hi = 1; }
  const span = Math.max(hi - lo, MIN_SPAN[unit] ?? 1);
  const mid = (hi + lo) / 2;
  lo = mid - span * 0.6; hi = mid + span * 0.6;
  const x = (t: number) => X0 + (t / duration) * (X1 - X0);
  const y = (v: number) => Y1 - ((v - lo) / (hi - lo)) * (Y1 - Y0);

  // Split into segments: a gap stays a gap; stale points are drawn dashed.
  const segs: { pts: string; stale: boolean }[] = [];
  let cur: string[] = [], curStale = false;
  const flush = () => { if (cur.length) segs.push({ pts: cur.join(" "), stale: curStale }); cur = []; };
  points.forEach((p, i) => {
    if (p.value === null) { flush(); return; }
    const stale = p.quality === "stale";
    if (cur.length && stale !== curStale) {
      const prev = points[i - 1];
      flush();
      if (prev?.value != null) cur.push(`${x(prev.t)},${y(prev.value)}`);
    }
    curStale = stale;
    cur.push(`${x(p.t)},${y(p.value)}`);
  });
  flush();

  const last = [...points].reverse().find((p) => p.t === visibleT);
  const nowText = last ? (last.value === null ? "חסר" : `${fmt(last.value)} ${unit}`) : "—";
  const nowQuality = last?.quality ?? "ok";
  const gaps = points.filter((p) => p.value === null);

  function pick(e: React.MouseEvent) {
    if (!clickable || !ref.current) return;
    const r = ref.current.getBoundingClientRect();
    const px = ((e.clientX - r.left) / r.width) * W;
    const t = Math.round(((px - X0) / (X1 - X0)) * duration);
    if (t >= 0 && t <= visibleT) onPick(t);
  }

  return (
    <div className="strip">
      <div className="strip-head">
        <div className="strip-name">{name}</div>
        <div className="strip-now" dir="ltr">
          {nowText}{" "}
          <span className={`q q-${nowQuality}`}>{qualityLabel(nowQuality, last?.age_s ?? 0)}</span>
        </div>
      </div>
      <div className="strip-body">
        <span className="ylab top" dir="ltr">{fmt(hi)}</span>
        <span className="ylab bottom" dir="ltr">{fmt(lo)}</span>
        {runs.map((r) => (
          <span key={r.label} className="runlab" style={{ left: `${((X0 + (r.from / duration) * (X1 - X0)) / W) * 100 + 1}%` }}>{r.label}</span>
        ))}
        <svg ref={ref} style={{ direction: "ltr" }} viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none"
             className={clickable ? "clickable" : ""} onClick={pick} role="img" aria-label={`${name} לאורך זמן`}>
          <rect x={x(windows.before[0])} y={Y0 - 4} width={x(windows.before[1]) - x(windows.before[0])} height={Y1 - Y0 + 8} fill="var(--win-before)" />
          <rect x={x(windows.after[0])} y={Y0 - 4} width={x(windows.after[1]) - x(windows.after[0])} height={Y1 - Y0 + 8} fill="var(--win-after)" />
          {gaps.map((g) => (
            <rect key={g.t} x={x(g.t) - 4} y={Y0} width={8} height={Y1 - Y0} fill="var(--gap)" />
          ))}
          <line x1={X0} y1={Y1} x2={X1} y2={Y1} stroke="var(--axis)" strokeWidth={1} />
          {runs.slice(1).map((r) => (
            <line key={r.from} x1={x(r.from - 0.5)} y1={Y0 - 4} x2={x(r.from - 0.5)} y2={Y1} stroke="var(--muted)" strokeWidth={2} vectorEffect="non-scaling-stroke" />
          ))}
          {segs.map((s, i) => (
            <polyline key={i} points={s.pts} fill="none" stroke={s.stale ? "var(--muted)" : color}
                      strokeWidth={2.5} strokeDasharray={s.stale ? "6 5" : undefined} vectorEffect="non-scaling-stroke" />
          ))}
          {visibleT >= 0 && (
            <line x1={x(visibleT)} y1={2} x2={x(visibleT)} y2={Y1} stroke="var(--text)" strokeWidth={1.5}
                  strokeDasharray="4 3" vectorEffect="non-scaling-stroke" />
          )}
        </svg>
      </div>
    </div>
  );
}

export function fmt(v: number): string {
  const a = Math.abs(v);
  const d = a >= 100 ? 0 : a >= 10 ? 1 : a >= 1 ? 2 : 3;
  return v.toLocaleString("en-US", { maximumFractionDigits: d, minimumFractionDigits: d === 0 ? 0 : 1 });
}

export function qualityLabel(q: string, age: number): string {
  if (q === "missing") return "חסר";
  if (q === "stale") return `ישן · ${age} s`;
  return "ok";
}
