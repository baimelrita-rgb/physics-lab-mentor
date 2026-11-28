import { useCallback, useEffect, useState } from "react";
import { ApiError, api, teacherApi, type Card, type Detail, type ExerciseItem, type Live } from "./api";
import { fmt } from "./Chart";

const FLAG_STYLE: Record<string, [string, string]> = {
  "תקוע": ["#FDECEC", "#A12B2B"], "רמז 3": ["#FFF1E0", "#9A4A06"], "הושלם": ["#E7F4E8", "#2E6B31"],
};
const ALERT_STYLE: Record<string, [string, string]> = {
  stuck: ["#FDECEC", "#A12B2B"], hint3: ["#FFF1E0", "#9A4A06"], misconception: ["#F3F5F8", "#3A4450"],
  offtopic: ["#F3F5F8", "#3A4450"],
};
const shade = (v: number | null): [string, string] =>
  v === 2 ? ["#DCEFDD", "#2E6B31"] : v === 1 ? ["#FFF1D6", "#8A5A00"] : v === 0 ? ["#F3F5F8", "#5A6573"] : ["#fff", "#9AA5B1"];
const mmss = (s: number) => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;

export function TeacherHome() {
  const [items, setItems] = useState<ExerciseItem[]>([]);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => { api.exercises().then(setItems); }, []);
  const start = async (id: string) => {
    try { const l = await teacherApi.createLesson(id); location.href = `/teacher/${l.lesson.id}`; }
    catch (e) { setError(e instanceof ApiError ? e.message : "שגיאה"); }
  };
  return (
    <div className="t-page">
      <TeacherHeader />
      <div className="t-wrap">
        <section className="panel t-section">
          <div className="t-h">פתיחת שיעור</div>
          <p className="muted">בחרו תרגיל. המערכת תיצור קוד שיעור, והעמדות יצטרפו איתו.</p>
          <div className="picker-list">
            {items.map((e) => (
              <button key={e.id} className="picker-item" disabled={!e.available} onClick={() => start(e.id)}>
                <b>{e.id} · {e.title}</b><span>{e.subtitle}</span>
                <span className={`chip ${e.status === "approved" ? "okc" : "draft"}`}>{e.status === "approved" ? "תוכן מאושר" : "תוכן טיוטה"}</span>
              </button>
            ))}
          </div>
          {error && <div className="note warn">{error}</div>}
        </section>
      </div>
    </div>
  );
}

function TeacherHeader() {
  const [llm, setLlm] = useState<boolean | null>(null);
  useEffect(() => { api.status().then((x) => setLlm(x.llm)).catch(() => setLlm(null)); }, []);
  return (
    <header className="t-header">
      <div className="t-header-in">
        <div className="t-brand">מנטור מעבדה · מורה</div>
        <nav className="t-tabs" aria-label="לשוניות">
          <a href="/teacher" className="cur">שיעור חי</a>
          {["הכנת שיעור", "תלמידים", "כיתה", "תוכן"].map((t) => <span key={t} title="בשלב הבא">{t}</span>)}
        </nav>
        {llm !== null && (
          <span className={`t-llm ${llm ? "on" : ""}`} title={llm ? "המנטור מנסח רמזים עם Claude" : "אין מפתח API: המנטור משתמש בטקסטים המאושרים בלבד"}>
            Claude: {llm ? "פעיל" : "כבוי (טקסטים מאושרים)"}
          </span>
        )}
      </div>
    </header>
  );
}

export function TeacherLive({ lessonId }: { lessonId: string }) {
  const [live, setLive] = useState<Live | null>(null);
  const [open, setOpen] = useState<string | null>(null);
  const refresh = useCallback(async () => { try { setLive(await teacherApi.live(lessonId)); } catch { /* keep */ } }, [lessonId]);
  useEffect(() => { refresh(); const h = setInterval(refresh, 1000); return () => clearInterval(h); }, [refresh]);
  if (!live) return <div className="loading">טוען…</div>;
  const L = live.lesson;
  const joinUrl = `${location.origin}/join?code=${L.code}`;

  return (
    <div className="t-page">
      <TeacherHeader />
      <div className="t-wrap">
        {L.status === "draft" && <div className="note warn">תוכן התרגיל הזה עדיין טיוטה וממתין לאישור.</div>}

        <section className="panel t-lesson" aria-label="תרגיל פעיל">
          <div>
            <div className="muted sm">תרגיל פעיל</div>
            <div className="t-ex">{L.exercise_id} · {L.title}: {L.subtitle}</div>
          </div>
          <div className="t-code">
            <div className="muted sm">קוד שיעור</div>
            <div className="t-code-n" dir="ltr">{L.code}</div>
          </div>
          <div className="muted sm">עצירה בשנייה {L.stop_s} · {mmss(L.elapsed)} מתחילת השיעור · הצטרפות: <span dir="ltr">{joinUrl}</span></div>
          <div className="t-actions">
            <button className="secondary auto" onClick={async () => setLive(await teacherApi.lessonAction(lessonId, "pause"))}>השהה את כולם</button>
            <button className="primary" onClick={async () => setLive(await teacherApi.lessonAction(lessonId, "resume"))}>המשך לכולם</button>
          </div>
        </section>

        <div className="t-row">
          <section className="t-cards-wrap" aria-label="עמדות ותלמידים">
            <div className="t-h">עמדות ותלמידים</div>
            {!live.cards.length && <div className="panel t-empty">עדיין אין עמדות. בעמדה פותחים את מסך ההצטרפות ומקלידים את הקוד <b dir="ltr">{L.code}</b>.</div>}
            <div className="t-cards">
              {live.cards.map((c) => <StationCard key={c.id} c={c} onOpen={() => setOpen(c.id)} refresh={refresh} />)}
            </div>
          </section>
          <aside className="panel t-alerts" aria-label="התראות">
            <div className="t-h">התראות</div>
            {!live.alerts.length && <div className="muted">אין התראות.</div>}
            {live.alerts.map((a, i) => (
              <div key={i} className="t-alert" style={{ background: ALERT_STYLE[a.kind]?.[0] }}>
                <div className="t-alert-k" style={{ color: ALERT_STYLE[a.kind]?.[1] }}>{a.title}</div>
                <div>{a.text}</div>
                <div className="t-suggest">הצעה: {a.suggest}</div>
              </div>
            ))}
          </aside>
        </div>

        <div className="t-row">
          <section className="panel t-section grow" aria-label="מחוון כיתתי">
            <div className="t-h">מחוון כיתתי · {L.exercise_id} <span className="muted sm">(ציון מוצע, לאישור המורה)</span></div>
            <table className="t-rubric">
              <thead><tr><th>עמדה</th>{live.rubric_aspects.map((a) => <th key={a}>{a}</th>)}<th>סה״כ</th></tr></thead>
              <tbody>
                {live.cards.map((c) => (
                  <tr key={c.id}>
                    <td className="b">{c.label}</td>
                    {c.rubric.map((v, i) => <td key={i} style={{ background: shade(v)[0], color: shade(v)[1] }}>{v ?? "—"}</td>)}
                    <td className="b">{c.total}/8</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div className="muted sm">0 = טרם הודגם · 1 = עם רמז · 2 = עצמאי · — = עוד לא ניתן לשפוט</div>
          </section>
          <section className="panel t-section side" aria-label="תפיסות שגויות">
            <div className="t-h">תפיסות שגויות בשיעור</div>
            {!live.misconceptions.length && <div className="muted">עדיין לא זוהו.</div>}
            {live.misconceptions.map((m) => {
              const max = Math.max(...live.misconceptions.map((x) => x.count));
              return (
                <div key={m.id} className="t-mis">
                  <div className="t-mis-row"><span>{m.id} · {m.label}</span><b>{m.count}</b></div>
                  <div className="t-bar"><div style={{ width: `${(m.count / max) * 100}%` }} /></div>
                </div>
              );
            })}
          </section>
        </div>
      </div>
      {open && <DetailDrawer sid={open} onClose={() => setOpen(null)} refresh={refresh} />}
    </div>
  );
}

function StationCard({ c, onOpen, refresh }: { c: Card; onOpen: () => void; refresh: () => void }) {
  const [err, setErr] = useState<string | null>(null);
  const run = async (p: Promise<unknown>) => { try { await p; setErr(null); refresh(); } catch (e) { setErr(e instanceof ApiError ? e.message : "שגיאה"); } };
  const border = c.urgency === 0 ? "#D46A6A" : c.urgency === 1 ? "#E39A4E" : "#D8DEE5";
  return (
    <article className="t-card" style={{ borderColor: border, borderWidth: c.urgency < 2 ? 2 : 1 }}>
      <div className="t-card-top"><b>{c.label}</b><span className="muted sm">{c.paused ? "מושהה" : `שלב ${c.step + 1} מתוך 6`}</span></div>
      <div className="t-card-stage"><span className="t-stage">{c.stage}</span><span className="muted sm">{mmss(c.seconds_in_state)} בשלב</span></div>
      <div className="sm">השערה אחרונה: <b>{c.hypothesis_label ?? "—"}</b></div>
      <div className="t-card-top sm muted">
        <span>רמזים: {c.hints_used} מתוך {c.quota}</span>
        {c.flag && <span className="t-flag" style={{ background: FLAG_STYLE[c.flag][0], color: FLAG_STYLE[c.flag][1] }}>{c.flag}</span>}
      </div>
      <div className="t-card-actions">
        <button onClick={onOpen}>פתח יומן</button>
        <button onClick={() => run(teacherApi.action(c.id, "hint"))} disabled={c.hints_used >= c.quota}>תן רמז</button>
        <button onClick={() => run(teacherApi.action(c.id, c.paused ? "resume" : "pause"))}>{c.paused ? "המשך" : "השהה"}</button>
      </div>
      {err && <div className="note warn sm">{err === "no hints in THEORY" || err.startsWith("no hints in") ? "רמז זמין רק משלב ההשערה." : err}</div>}
    </article>
  );
}

const INTENT: Record<string, string> = {
  hypothesis: "השערה", question: "שאלה", answer_request: "בקשת תשובה", off_topic: "מחוץ לתחום", other: "אחר", unclear: "לא ברור",
};

const EVENT_LABEL: Record<string, string> = {
  "session.opened": "הצטרפות", "state.changed": "מעבר שלב", "theory.answered": "שאלת הבנה",
  "prediction.submitted": "תחזית", "hypothesis.chosen": "השערה", "channel.opened": "פתיחת ערוץ",
  "channel.closed": "סגירת ערוץ", "reading.saved": "קריאה נשמרה", "hint.given": "רמז",
  "reason.evaluated": "נימוק", "exit.answered": "שאלת יציאה", "teacher.paused": "השהיה",
  "teacher.resumed": "המשך", "teacher.message": "הודעת מורה", "student.asked": "שאלה למנטור",
};

function DetailDrawer({ sid, onClose, refresh }: { sid: string; onClose: () => void; refresh: () => void }) {
  const [d, setD] = useState<Detail | null>(null);
  const [msg, setMsg] = useState("");
  useEffect(() => { let a = true; const f = () => teacherApi.detail(sid).then((x) => a && setD(x)); f(); const h = setInterval(f, 1500); return () => { a = false; clearInterval(h); }; }, [sid]);
  if (!d) return null;
  return (
    <div className="t-drawer-bg" onClick={onClose}>
      <aside className="t-drawer" onClick={(e) => e.stopPropagation()} aria-label="פירוט עמדה">
        <div className="t-card-top"><div className="t-h">{d.label} · {d.stage}</div><button className="x big" onClick={onClose} aria-label="סגור">×</button></div>
        <div className="box"><div className="muted sm">מסקנה מצופה (למורה בלבד)</div><div>{d.expected.cause_label}. {d.expected.conclusion}</div></div>

        <div className="t-h sm2">ציון מוצע</div>
        <table className="t-rubric"><tbody>
          {d.rubric_aspects.map((a, i) => <tr key={a}><td>{a}</td><td style={{ background: shade(d.rubric[i])[0], color: shade(d.rubric[i])[1] }}>{d.rubric[i] ?? "—"}</td></tr>)}
        </tbody></table>

        <div className="t-h sm2">עבודת התלמידים</div>
        <div className="sm">תחזית: {d.prediction ? Object.entries(d.prediction.directions).map(([k, v]) => `${k} ${v === "up" ? "↑" : v === "down" ? "↓" : "="}`).join(" · ") + (d.prediction.text ? ` · ״${d.prediction.text}״` : "") : "—"}</div>
        <div className="sm">השערה: {d.hypothesis_label ?? "—"}</div>
        <div className="sm">קריאות: {d.readings.length ? d.readings.map((r) => `${r.name} ${r.value === null ? "חסר" : fmt(r.value)} ש׳${r.t}`).join(" · ") : "—"}</div>
        {d.attempts.map((a, i) => (
          <div key={i} className={`note ${a.passed ? "ok" : "warn"} sm`}>נימוק {i + 1}: ״{a.text || "—"}״ · {a.outcome}{a.misconception ? ` (${a.misconception})` : ""}{a.missing.length ? ` · חסר: ${a.missing.join(", ")}` : ""}</div>
        ))}
        {d.exit_answer && <div className="sm">שאלת יציאה: ״{d.exit_answer}״</div>}
        {d.hints.length > 0 && <div className="sm">רמזים: {d.hints.map((h) => `${h.level}${h.by === "teacher" ? " (מהמורה)" : ""}: ״${h.text}״`).join(" · ")}</div>}
        {d.asks.length > 0 && (
          <>
            <div className="t-h sm2">שאלות למנטור</div>
            {d.asks.map((q, i) => (
              <div key={i} className="box sm">
                <div><b>ש:</b> {q.q} <span className="muted">({INTENT[q.intent] ?? q.intent})</span></div>
                <div><b>ת:</b> {q.a} <span className="muted">{q.source === "llm" ? "· נוסח ע״י Claude" : "· טקסט מאושר"}</span></div>
              </div>
            ))}
          </>
        )}

        <div className="t-h sm2">הודעה לעמדה</div>
        <div className="t-msg">
          <input value={msg} maxLength={200} onChange={(e) => setMsg(e.target.value)} placeholder="למשל: בדקו את תדר היציאה" />
          <button className="primary" disabled={!msg.trim()} onClick={async () => { setD(await teacherApi.action(sid, "message", msg)); setMsg(""); refresh(); }}>שלח</button>
        </div>

        <div className="t-h sm2">ציר זמן</div>
        <ol className="t-timeline">
          {d.timeline.map((e, i) => (
            <li key={i}><span className="muted" dir="ltr">{mmss(e.t)}</span> {EVENT_LABEL[e.type] ?? e.type}{describe(e)}</li>
          ))}
        </ol>
      </aside>
    </div>
  );
}

function describe(e: Record<string, unknown>): string {
  if (e.type === "state.changed") return ` → ${e.to}`;
  if (e.type === "channel.opened") return `: ${e.channel} (ציפייה: ${e.expectation ?? "—"})`;
  if (e.type === "reading.saved") return `: ${e.name} ${e.value ?? "חסר"} ש׳${e.t}`;
  if (e.type === "hint.given") return ` ${e.level}${e.by === "teacher" ? " (מהמורה)" : ""}`;
  if (e.type === "hypothesis.chosen") return `: ${e.code}`;
  if (e.type === "reason.evaluated") return `: ${e.outcome}`;
  if (e.type === "teacher.message") return `: ״${e.text}״`;
  return "";
}
