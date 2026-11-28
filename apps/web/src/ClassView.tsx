import { useEffect, useState } from "react";
import { teacherApi, type ClassData } from "./api";
import { TeacherHeader } from "./Teacher";

const PERIODS: [number | null, string][] = [[7, "שבוע"], [30, "חודש"], [90, "3 חודשים"], [null, "הכול"]];
const mmss = (s: number) => `${Math.floor(s / 60)}:${String(Math.round(s) % 60).padStart(2, "0")}`;

// Score 0..2 -> background/text. Same scale as the rubric on the live screen.
function heat(v: number | null): [string, string] {
  if (v === null) return ["#FFFFFF", "#9AA5B1"];
  if (v >= 1.75) return ["#CFE8D1", "#1F4D22"];
  if (v >= 1.25) return ["#E5F2E0", "#2E6B31"];
  if (v >= 0.75) return ["#FFF1D6", "#8A5A00"];
  return ["#FBE3E3", "#8A1F1F"];
}
const pct = (v: number | null) => (v === null ? "—" : `${Math.round(v * 100)}%`);

export function ClassView() {
  const [classes, setClasses] = useState<{ name: string; lessons: number }[]>([]);
  const [name, setName] = useState<string | null>(null);
  const [days, setDays] = useState<number | null>(30);
  const [d, setD] = useState<ClassData | null>(null);

  useEffect(() => {
    teacherApi.classes().then((c) => { setClasses(c); if (c.length) setName(c[0].name); });
  }, []);
  useEffect(() => {
    if (name) teacherApi.classView(name, days).then(setD);
  }, [name, days]);

  return (
    <div className="t-page">
      <TeacherHeader tab="class" />
      <div className="t-wrap">
        <section className="panel t-section cv-top">
          <div className="cv-pick">
            <span className="muted sm">כיתה</span>
            <div className="chips">
              {classes.map((c) => (
                <button key={c.name} className={`chip-btn ${c.name === name ? "sel" : ""}`} onClick={() => setName(c.name)}>
                  {c.name} <span className="cv-count">{c.lessons}</span></button>
              ))}
            </div>
          </div>
          <div className="cv-pick">
            <span className="muted sm">תקופה</span>
            <div className="chips">
              {PERIODS.map(([v, l]) => (
                <button key={l} className={`chip-btn sm ${days === v ? "sel" : ""}`} onClick={() => setDays(v)}>{l}</button>
              ))}
            </div>
          </div>
          {!classes.length && (
            <div className="note">עדיין אין שיעורים שהתקיימו. אפשר ליצור כיתה לדוגמה: <code dir="ltr">python3 tools/seed_demo_class.py</code></div>
          )}
        </section>

        {d && !d.lessons.length && <section className="panel t-section"><p className="muted">אין שיעורים בתקופה הזו.</p></section>}

        {d && d.lessons.length > 0 && (
          <>
            <section className="panel t-section">
              <div className="cv-lessons">
                {d.lessons.map((l) => (
                  <a key={l.id} className="cv-lesson" href={`/teacher/${l.id}`}>
                    <b dir="ltr">{l.date.slice(5).split("-").reverse().join(".")}</b>
                    <span>תרגיל {l.number}</span><span className="muted sm">{l.groups} קבוצות</span>
                  </a>
                ))}
              </div>
            </section>

            <div className="cv-grid">
              <section className="panel t-section">
                <div className="t-h">מפת מחוון לפי קבוצה</div>
                <p className="muted sm">ממוצע 0 עד 2 בכל היבט, בכל השיעורים שנבחרו. ציון שהמורה אישרה גובר על המוצע. היבט שקבוצה לא הגיעה אליו עד סוף השיעור נספר כ־0.</p>
                <div className="cv-scroll">
                  <table className="cv-heat">
                    <thead><tr><th>קבוצה</th>{d.aspects.map((a) => <th key={a}>{a}</th>)}<th>סיימו</th><th>רמזים</th></tr></thead>
                    <tbody>
                      {d.heatmap.map((h) => (
                        <tr key={h.label}>
                          <th>{h.label}</th>
                          {h.aspects.map((v, i) => {
                            const [bg, fg] = heat(v);
                            return <td key={i} style={{ background: bg, color: fg }} title={`${h.label} · ${d.aspects[i]}`}>{v === null ? "—" : v.toFixed(1)}</td>;
                          })}
                          <td className="cv-plain">{h.finished}/{h.sessions}</td>
                          <td className="cv-plain">{h.hints ?? "—"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <div className="cv-legend">
                  {[[2, "שולט"], [1.5, "כמעט"], [1, "חלקי"], [0, "חסר"]].map(([v, l]) => (
                    <span key={l as string}><i style={{ background: heat(v as number)[0] }} />{l}</span>
                  ))}
                </div>
              </section>

              <section className="panel t-section">
                <div className="t-h">תפיסות שגויות נפוצות</div>
                {!d.misconceptions.length && <p className="muted">לא זוהו תפיסות שגויות בתקופה הזו.</p>}
                {d.misconceptions.map((m) => (
                  <div key={m.id} className="cv-mis">
                    <div className="cv-mis-h">
                      <b>{m.label}</b>
                      {m.direction && <span className={`cv-trend ${m.direction}`}>{m.direction === "down" ? "↘ יורדת" : m.direction === "up" ? "↗ עולה" : "→ יציבה"}</span>}
                    </div>
                    <div className="muted sm">{m.groups} קבוצות: {m.group_names.join(", ")}</div>
                    <div className="cv-spark" aria-label="שיעור הקבוצות בכל שיעור">
                      {m.trend.map((t) => (
                        <div key={t.lesson} className="cv-spark-col" title={`${t.date}: ${pct(t.share)}`}>
                          <div className="cv-spark-bar" style={{ height: `${Math.max(4, (t.share ?? 0) * 100)}%` }} />
                          <span dir="ltr">{t.date.slice(5).split("-").reverse().join(".")}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </section>
            </div>

            <div className="cv-grid">
              <section className="panel t-section">
                <div className="t-h">איפה נתקעים</div>
                <p className="muted sm">זמן חציוני בכל שלב. אדום: כמה פעמים קבוצה עברה את סף ה״תקוע״ ({mmss(d.threshold_s)} דק׳).</p>
                <div className="cv-stages">
                  {(() => {
                    const max = Math.max(1, ...d.stages.map((s) => s.median_s ?? 0));
                    return d.stages.filter((s) => s.sessions).map((s) => (
                      <div key={s.state} className="cv-stage">
                        <span className="cv-stage-l">{s.label}</span>
                        <div className="cv-stage-track">
                          <div className={`cv-stage-bar ${s.stuck ? "hot" : ""}`} style={{ width: `${((s.median_s ?? 0) / max) * 100}%` }} />
                        </div>
                        <span className="cv-stage-v" dir="ltr">{mmss(s.median_s ?? 0)}</span>
                        <span className="cv-badges">
                          {s.stuck > 0 && <span className="cv-badge stuck">{s.stuck} תקוע</span>}
                          {s.hints > 0 && <span className="cv-badge">{s.hints} רמזים</span>}
                        </span>
                      </div>
                    ));
                  })()}
                </div>
              </section>

              <section className="panel t-section">
                <div className="t-h">שליטה בכרטיסי ידע</div>
                <p className="muted sm">מהמחוון של תרגילים שמלמדים את הכרטיס. ״אין נתונים״: עוד לא נעשה תרגיל שמלמד אותו.</p>
                <div className="cv-scroll">
                  <table className="cv-mastery">
                    <thead><tr><th>כרטיס</th><th>כיתה</th>{d.heatmap.map((h) => <th key={h.label}>{h.label.replace("קבוצה ", "")}</th>)}</tr></thead>
                    <tbody>
                      {d.mastery.map((m) => (
                        <tr key={m.id} className={m.class === null ? "nodata" : ""}>
                          <th>{m.title}</th>
                          <td className="cv-mbar">
                            {m.class === null ? <span className="muted sm">אין נתונים</span> : (
                              <><div className="cv-mtrack"><div style={{ width: pct(m.class) }} /></div><span>{pct(m.class)}</span></>
                            )}
                          </td>
                          {d.heatmap.map((h) => {
                            const v = m.groups[h.label];
                            const [bg, fg] = heat(v === null || v === undefined ? null : v * 2);
                            return <td key={h.label} style={{ background: bg, color: fg }}>{v == null ? "" : pct(v)}</td>;
                          })}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </section>
            </div>
            <p className="muted sm">הקבוצות מזוהות לפי השם שהקלידו בהצטרפות. מעקב אחרי תלמיד יחיד ייכנס עם רשימת תלמידי הכיתה.</p>
          </>
        )}
      </div>
    </div>
  );
}
