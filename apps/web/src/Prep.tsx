import { useEffect, useState } from "react";
import { ApiError, teacherApi, type LessonSettings, type Preview, type PrepStation, type TeacherExercise } from "./api";
import { TeacherHeader } from "./Teacher";

const STEPS = ["כיתה ועמדות", "תרגיל", "תצוגה מקדימה", "הגדרה ובטיחות", "עזרה וציון"];
const today = () => new Date().toISOString().slice(0, 10);

export function LessonPrep() {
  const [step, setStep] = useState(0);
  const [stations, setStations] = useState<PrepStation[]>([]);
  const [exercises, setExercises] = useState<TeacherExercise[]>([]);
  const [preview, setPreview] = useState<Preview | null>(null);
  const [showKey, setShowKey] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [s, setS] = useState<LessonSettings>({
    exercise_id: "", class_name: "", date: today(), stations: 4,
    hint_quota: 3, allow_ask: true, deduction: "none", planned: false, setup_ack: false,
  });
  const set = (p: Partial<LessonSettings>) => setS((x) => ({ ...x, ...p }));

  useEffect(() => {
    teacherApi.prepStations().then(setStations);
    teacherApi.exercises().then(setExercises);
  }, []);
  useEffect(() => {
    if (s.exercise_id) teacherApi.preview(s.exercise_id).then(setPreview);
  }, [s.exercise_id]);

  const canNext = [
    s.stations >= 1,
    !!s.exercise_id,
    !!preview,
    s.setup_ack,
    true,
  ][step];

  const finish = async (planned: boolean) => {
    try {
      const l = await teacherApi.createLesson({ ...s, planned });
      location.href = planned ? "/teacher" : `/teacher/${l.lesson.id}`;
    } catch (e) { setErr(e instanceof ApiError ? e.message : "שגיאה"); }
  };

  return (
    <div className="t-page">
      <TeacherHeader tab="prep" />
      <nav className="stepper" aria-label="שלבי ההכנה">
        {STEPS.map((t, i) => (
          <button key={t} className={`step ${i === step ? "cur" : i < step ? "done" : ""}`}
            disabled={i > step} onClick={() => setStep(i)}>
            <span className="step-n">{i < step ? "✓" : i + 1}</span>{t}
          </button>
        ))}
      </nav>
      <div className="t-wrap prep">
        {step === 0 && (
          <section className="panel t-section">
            <div className="t-h">כיתה ועמדות</div>
            <div className="prep-row">
              <label className="field-label">כיתה<input className="join-input" value={s.class_name} placeholder="למשל י׳2"
                onChange={(e) => set({ class_name: e.target.value })} /></label>
              <label className="field-label">מועד<input className="join-input" type="date" dir="ltr" value={s.date}
                onChange={(e) => set({ date: e.target.value })} /></label>
              <label className="field-label">מספר קבוצות<input className="join-input" type="number" min={1} max={40} dir="ltr"
                value={s.stations} onChange={(e) => set({ stations: Math.max(1, Math.min(40, Number(e.target.value) || 1)) })} /></label>
            </div>
            <div className="t-h sm2">עמדה</div>
            <div className="picker-list">
              {stations.map((st) => (
                <div key={st.id} className={`picker-item ${st.usable ? "" : "off"}`}>
                  <div>
                    <b>{st.name}</b>
                    {st.components.length > 0 && <div className="muted sm">{st.components.join(" · ")}</div>}
                    {st.reason && <div className="muted sm">{st.reason}</div>}
                  </div>
                  <span className={`chip ${st.usable ? "okc" : "draft"}`}>{st.status}</span>
                </div>
              ))}
            </div>
            <p className="muted sm">כל הקבוצות עובדות על אותה הקלטה, כל אחת במסך משלה. הקבוצות מצטרפות עם קוד השיעור.</p>
          </section>
        )}

        {step === 1 && (
          <section className="panel t-section">
            <div className="t-h">תרגיל</div>
            <div className="picker-list">
              {exercises.map((e) => (
                <button key={e.id} className={`picker-item ${s.exercise_id === e.id ? "sel" : ""}`} disabled={!e.available}
                  onClick={() => set({ exercise_id: e.id })} aria-pressed={s.exercise_id === e.id}>
                  <b>{e.number} · {e.title}</b><span>{e.subtitle}</span>
                  <span className={`chip ${e.status === "approved" ? "okc" : "draft"}`}>
                    {!e.available ? "אין הקלטה" : e.status === "approved" ? "תוכן מאושר" : "תוכן טיוטה"}</span>
                </button>
              ))}
            </div>
          </section>
        )}

        {step === 2 && preview && (
          <section className="panel t-section">
            <div className="t-h">{preview.number} · {preview.title}: מה התלמידים יראו</div>
            {preview.status !== "approved" && <div className="note warn">התוכן של התרגיל הזה עדיין טיוטה. כדאי לעבור עליו לפני השיעור.</div>}
            <dl className="prep-dl">
              <dt>כותרת אצל התלמיד</dt><dd>{preview.number} (בלי שם, כדי לא לחשוף את התשובה)</dd>
              <dt>מטרה</dt><dd>{preview.student.goal}</dd>
              <dt>כרטיסי רקע</dt><dd>{preview.student.cards.join(" · ")}</dd>
              <dt>שאלת הבנה</dt><dd>{preview.student.check}</dd>
              <dt>תחזית</dt><dd>{preview.student.predict}</dd>
              <dt>צפייה</dt><dd>{preview.student.observe} ההקלטה נעצרת בשנייה {preview.student.stop_s}.</dd>
              <dt>השערות לבחירה</dt><dd>{preview.student.hypotheses.join(" · ")}</dd>
              <dt>ערוצים</dt><dd>{preview.student.channels.join(" · ")}</dd>
              <dt>רמזים לפי הסדר</dt><dd><ol>{preview.student.hints.map((h) => <li key={h}>{h}</li>)}</ol></dd>
              {preview.student.recheck && <><dt>בדיקה חוזרת</dt><dd>{preview.student.recheck}</dd></>}
              <dt>שאלת יציאה</dt><dd>{preview.student.exit}</dd>
            </dl>
            <button className="secondary auto" onClick={() => setShowKey(!showKey)}>{showKey ? "הסתרת המפתח" : "הצגת המפתח (למורה בלבד)"}</button>
            {showKey && (
              <dl className="prep-dl key">
                <dt>תשובת שאלת ההבנה</dt><dd>{preview.key.check_answer}</dd>
                <dt>הסיבה</dt><dd>{preview.key.cause}</dd>
                <dt>ראיות נדרשות</dt><dd>{preview.key.evidence.join(" · ")}</dd>
                <dt>מסקנה</dt><dd>{preview.key.conclusion}</dd>
              </dl>
            )}
            <p className="muted sm">וריאציות לכל עמדה ייכנסו בשלב מאוחר יותר. עכשיו כל הקבוצות מקבלות את תרגיל הבסיס.</p>
          </section>
        )}

        {step === 3 && preview && (
          <section className="panel t-section">
            <div className="t-h">הגדרה ובטיחות</div>
            <div className="note">{preview.setup.note}</div>
            <div className="t-h sm2">מעטפת הבטיחות של העמדה</div>
            <ul className="prep-rules">
              {preview.setup.envelope.map((r) => (
                <li key={r.id}><b dir="ltr">{r.id}</b> {r.title}
                  <span className={r.status === "approved" ? "q-ok" : "q-stale"}> · {r.status === "approved" ? "מאושר" : "ערך מוצע, ממתין לתלם"}</span></li>
              ))}
            </ul>
            <label className="prep-check">
              <input type="checkbox" checked={s.setup_ack} onChange={(e) => set({ setup_ack: e.target.checked })} />
              עברתי על רשימת ההגדרה והבטיחות
            </label>
          </section>
        )}

        {step === 4 && (
          <section className="panel t-section">
            <div className="t-h">עזרה וציון</div>
            <div className="t-h sm2">עזרה לתלמיד</div>
            <div className="chips">
              <button className={`chip-btn ${s.allow_ask ? "sel" : ""}`} onClick={() => set({ allow_ask: true })}>כפתור רמז ושאלה פתוחה</button>
              <button className={`chip-btn ${!s.allow_ask ? "sel" : ""}`} onClick={() => set({ allow_ask: false })}>כפתור רמז בלבד</button>
            </div>
            <div className="t-h sm2">מכסת רמזים</div>
            <div className="chips">
              {[0, 1, 2, 3].map((n) => (
                <button key={n} className={`chip-btn ${s.hint_quota === n ? "sel" : ""}`} onClick={() => set({ hint_quota: n })}>
                  {n === 0 ? "בלי רמזים" : n}{n === 3 ? " (ברירת מחדל)" : ""}</button>
              ))}
            </div>
            <p className="muted sm">המורה יכול לתת רמז מהמסך שלו גם אחרי שהמכסה נגמרה.</p>
            <div className="t-h sm2">ניכוי</div>
            <div className="chips">
              <button className={`chip-btn ${s.deduction === "none" ? "sel" : ""}`} onClick={() => set({ deduction: "none" })}>ללא ניכוי</button>
              <button className={`chip-btn ${s.deduction === "per_hint" ? "sel" : ""}`} onClick={() => set({ deduction: "per_hint" })}>נקודה לכל רמז שהתלמיד ביקש</button>
            </div>
            <div className="prep-summary">
              <b>סיכום:</b> {s.class_name || "כיתה לא צוינה"} · {s.date} · {s.stations} קבוצות ·{" "}
              {exercises.find((e) => e.id === s.exercise_id)?.number} · {s.hint_quota} רמזים ·{" "}
              {s.allow_ask ? "עם שאלה פתוחה" : "רמז בלבד"} · {s.deduction === "none" ? "ללא ניכוי" : "ניכוי לכל רמז"}
            </div>
            <div className="prep-finish">
              <button className="primary" onClick={() => finish(false)}>פתיחת השיעור עכשיו</button>
              <button className="secondary auto" onClick={() => finish(true)}>שמירה לשיעור מתוכנן</button>
            </div>
            {err && <div className="note warn">{err}</div>}
          </section>
        )}

        {step < 4 && (
          <div className="prep-nav">
            {step > 0 && <button className="secondary auto" onClick={() => setStep(step - 1)}>הקודם</button>}
            <button className="primary" disabled={!canNext} onClick={() => setStep(step + 1)}>הבא</button>
          </div>
        )}
      </div>
    </div>
  );
}
