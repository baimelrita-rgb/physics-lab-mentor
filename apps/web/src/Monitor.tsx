import { useEffect, useState } from "react";
import { fmt } from "./Chart";

type Row = { key: string; name: string; unit: string; group: string; value: number | null; quality: string; last_value_t: number | null };
type Mon = {
  station: string; connected: boolean; samples: number; last_seq: number | null; gaps: number; duplicates: number;
  seconds_since_frame: number | null; agent: Record<string, unknown>; channels: Row[];
  envelope: { rule: string; title: string; level: string; t: number; channel: string; value: number; limit: number }[];
  rules: { id: string; title: string; status: string; state: string }[];
};

const QL: Record<string, [string, string]> = {
  ok: ["תקין", "q-ok"], stale: ["ישן", "q-stale"], missing: ["חסר", "q-missing"],
  out_of_range_sensor: ["מחוץ לתחום החיישן", "q-missing"], not_sent: ["לא נשלח", "muted"],
};
const RS: Record<string, [string, string]> = { ok: ["תקין", "#E7F4E8"], warn: ["התקרבות לסף", "#FFF1E0"], stop: ["חריגה", "#FDECEC"] };

export function MonitorList() {
  const [list, setList] = useState<{ station: string; connected: boolean; samples: number }[]>([]);
  useEffect(() => {
    const f = () => fetch("/api/teacher/stations").then((r) => r.json()).then(setList).catch(() => {});
    f(); const h = setInterval(f, 2000); return () => clearInterval(h);
  }, []);
  return (
    <div className="picker">
      <h1>ניטור עמדות</h1>
      <p className="muted">עמדות שהבקר שלהן שלח נתונים לשרת. העמדה לקריאה בלבד: אין מכאן שליטה במכשירים.</p>
      {!list.length && <div className="note warn">עדיין לא התחברה אף עמדה. בהדגמה: <code dir="ltr">python3 tools/simulator/station_agent.py</code></div>}
      <div className="picker-list">
        {list.map((s) => (
          <a key={s.station} className="picker-item" href={`/monitor/${s.station}`}>
            <b dir="ltr">{s.station}</b><span>{s.samples} שניות נתונים</span>
            <span className={`chip ${s.connected ? "okc" : "draft"}`}>{s.connected ? "מחוברת" : "מנותקת"}</span>
          </a>
        ))}
      </div>
    </div>
  );
}

export function Monitor({ id }: { id: string }) {
  const [m, setM] = useState<Mon | null>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    const f = () => fetch(`/api/teacher/stations/${id}/monitor`).then(async (r) => {
      if (!r.ok) { setErr("העמדה עוד לא שלחה נתונים."); return; }
      setM(await r.json()); setErr(null);
    }).catch(() => setErr("אין קשר לשרת."));
    f(); const h = setInterval(f, 1000); return () => clearInterval(h);
  }, [id]);
  if (!m) return <div className="loading">{err ?? "טוען…"}</div>;
  const groups = [...new Set(m.channels.map((c) => c.group))];
  return (
    <div className="t-page">
      <header className="t-header"><div className="t-header-in"><div className="t-brand">ניטור עמדה · <span dir="ltr">{m.station}</span></div>
        <span className={`t-llm ${m.connected ? "on" : ""}`}>{m.connected ? "מחוברת" : "מנותקת"}</span></div></header>
      <div className="t-wrap">
        <section className="panel t-lesson">
          <div><div className="muted sm">שניות נתונים</div><div className="t-ex">{m.samples}</div></div>
          <div><div className="muted sm">מסגרת אחרונה</div><div className="t-ex">{m.seconds_since_frame ?? "—"} s</div></div>
          <div><div className="muted sm">מספר רץ אחרון</div><div className="t-ex" dir="ltr">{m.last_seq ?? "—"}</div></div>
          <div><div className="muted sm">פערים · כפילויות</div><div className="t-ex">{m.gaps} · {m.duplicates}</div></div>
          <div className="muted sm">סוכן: {String(m.agent.agent_version ?? "—")} · שעון מסונכרן: {m.agent.clock_synced ? "כן" : "לא ידוע"} · בתור: {String(m.agent.offline_buffer ?? 0)}</div>
        </section>

        <section className="panel t-section">
          <div className="t-h">מעטפת בטיחות</div>
          <div className="mon-rules">
            {m.rules.map((r) => (
              <div key={r.id} className="mon-rule" style={{ background: RS[r.state][1] }}>
                <b>{r.id}</b> {r.title}
                <div className="sm">{RS[r.state][0]} · <span className={r.status === "approved" ? "q-ok" : "q-stale"}>{r.status === "approved" ? "מאושר" : "ערך מוצע, ממתין לתלם"}</span></div>
              </div>
            ))}
          </div>
        </section>

        <section className="panel t-section">
          <div className="t-h">ערוצים</div>
          <table className="mon-table">
            <thead><tr><th>ערוץ</th><th>ערך</th><th>איכות</th><th>מפתח</th></tr></thead>
            {groups.map((g) => (
              <tbody key={g}>
                <tr><td colSpan={4} className="mon-group">{g}</td></tr>
                {m.channels.filter((c) => c.group === g).map((c) => (
                  <tr key={c.key}>
                    <td>{c.name}</td>
                    <td dir="ltr" className="mon-val">{c.value === null ? "—" : `${fmt(c.value)} ${c.unit}`}</td>
                    <td className={QL[c.quality]?.[1]}>{QL[c.quality]?.[0] ?? c.quality}</td>
                    <td dir="ltr" className="muted sm">{c.key}</td>
                  </tr>
                ))}
              </tbody>
            ))}
          </table>
        </section>
      </div>
    </div>
  );
}
