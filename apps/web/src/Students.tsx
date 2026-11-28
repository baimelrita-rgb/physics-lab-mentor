import { useCallback, useEffect, useState } from "react";
import { ApiError, teacherApi, type StudentDetail, type StudentsOverview } from "./api";
import { TeacherHeader } from "./Teacher";

function heat(v: number | null): [string, string] {
  if (v === null) return ["#FFFFFF", "#9AA5B1"];
  if (v >= 1.75) return ["#CFE8D1", "#1F4D22"];
  if (v >= 1.25) return ["#E5F2E0", "#2E6B31"];
  if (v >= 0.75) return ["#FFF1D6", "#8A5A00"];
  return ["#FBE3E3", "#8A1F1F"];
}
const ddmm = (d: string) => d.slice(5).split("-").reverse().join(".");

function Trend({ values }: { values: (number | null)[] }) {
  if (!values.length) return <span className="muted sm">—</span>;
  return (
    <span className="st-trend" dir="ltr" title={values.map((v) => (v === null ? "—" : `${Math.round(v * 100)}%`)).join(" → ")}>
      {values.map((v, i) => <i key={i} style={{ height: `${Math.max(8, (v ?? 0) * 100)}%`, background: heat(v === null ? null : v * 2)[1] }} />)}
    </span>
  );
}

export function Students() {
  const [classes, setClasses] = useState<{ name: string; lessons: number }[]>([]);
  const [name, setName] = useState<string | null>(new URLSearchParams(location.search).get("class"));
  const [ov, setOv] = useState<StudentsOverview | null>(null);
  const [open, setOpen] = useState<string | null>(null);
  const [names, setNames] = useState("");
  const [newClass, setNewClass] = useState("");
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    teacherApi.classes().then((c) => { setClasses(c); setName((n) => n ?? c[0]?.name ?? null); });
  }, []);
  const load = useCallback(() => { if (name) teacherApi.students(name).then(setOv); }, [name]);
  useEffect(() => { setOv(null); setOpen(null); load(); }, [load]);

  const add = async () => {
    const list = names.split(/\n|,/).map((x) => x.trim()).filter(Boolean);
    if (!name || !list.length) return;
    try { await teacherApi.rosterAdd(name, list); setNames(""); load(); }
    catch (e) { setErr(e instanceof ApiError ? e.message : "שגיאה"); }
  };
  const createClass = () => {
    const n = newClass.trim();
    if (!n) return;
    if (!classes.some((c) => c.name === n)) setClasses([...classes, { name: n, lessons: 0 }]);
    setName(n); setNewClass("");
  };

  const active = ov?.students.filter((s) => s.active) ?? [];
  const inactive = ov?.students.filter((s) => !s.active) ?? [];

  return (
    <div className="t-page">
      <TeacherHeader tab="students" />
      <div className="t-wrap">
        <section className="panel t-section cv-top">
          <div className="cv-pick">
            <span className="muted sm">כיתה</span>
            <div className="chips">
              {classes.map((c) => (
                <button key={c.name} className={`chip-btn ${c.name === name ? "sel" : ""}`} onClick={() => setName(c.name)}>{c.name}</button>
              ))}
            </div>
          </div>
          <form className="cv-pick" onSubmit={(e) => { e.preventDefault(); createClass(); }}>
            <span className="muted sm">כיתה חדשה</span>
            <div className="st-inline">
              <input className="join-input" value={newClass} maxLength={40} placeholder="למשל י׳3" onChange={(e) => setNewClass(e.target.value)} />
              <button className="secondary auto" type="submit" disabled={!newClass.trim()}>הוספה</button>
            </div>
          </form>
        </section>

        {name && (
          <div className="st-layout">
            <section className="panel t-section">
              <div className="t-h">תלמידי {name}</div>
              {ov && !ov.students.length && <p className="muted">עדיין אין תלמידים ברשימה. הוסיפו שמות בטופס שבצד.</p>}
              {ov && ov.unassigned_sessions > 0 && (
                <div className="note sm">{ov.unassigned_sessions} מתוך {ov.sessions} עמדות בכיתה הזו לא שויכו לתלמידים (הצטרפו לפני שהייתה רשימה). אפשר לשייך מתוך יומן העמדה בשיעור.</div>
              )}
              {ov && ov.students.length > 0 && (
                <div className="cv-scroll">
                  <table className="st-table">
                    <thead>
                      <tr><th>תלמיד</th><th>שיעורים</th>{ov.aspects.map((a) => <th key={a} className="st-asp">{a}</th>)}<th>מגמה</th><th>תפיסות שגויות</th><th>אחרון</th></tr>
                    </thead>
                    <tbody>
                      {[...active, ...inactive].map((s) => (
                        <tr key={s.id} className={`${s.active ? "" : "inactive"} ${open === s.id ? "cur" : ""}`} onClick={() => setOpen(s.id)}
                          tabIndex={0} onKeyDown={(e) => e.key === "Enter" && setOpen(s.id)}>
                          <th>{s.name}{!s.active && <span className="muted sm"> (לא פעיל)</span>}</th>
                          <td className="cv-plain">{s.lessons}</td>
                          {s.aspects.map((v, i) => { const [bg, fg] = heat(v); return <td key={i} className="st-cell" style={{ background: bg, color: fg }}>{v === null ? "—" : v.toFixed(1)}</td>; })}
                          <td><Trend values={s.trend} /></td>
                          <td className="st-mis">{s.misconceptions.map((m) => <span key={m.id} className="st-mchip" title={m.label}>{m.label}</span>)}</td>
                          <td className="muted sm" dir="ltr">{s.last ? ddmm(s.last) : "—"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
              <p className="muted sm">ציון של תלמיד הוא הציון של הקבוצה שלו בכל שיעור. לחצו על שורה לפירוט.</p>
            </section>

            <aside className="panel t-section st-side">
              <div className="t-h">הוספת תלמידים</div>
              <p className="muted sm">שם בכל שורה. מספיק שם פרטי ואות ראשונה של שם המשפחה. השמות מוצגים לתלמידים בכיתה במסך ההצטרפות.</p>
              <textarea className="st-names" rows={6} value={names} onChange={(e) => setNames(e.target.value)} placeholder={"נועה כ.\nעומר ל."} />
              <button className="primary" onClick={add} disabled={!names.trim()}>הוספה לרשימה</button>
              {err && <div className="note warn sm">{err}</div>}
            </aside>
          </div>
        )}
      </div>
      {open && name && <StudentDrawer id={open} className={name} onClose={() => setOpen(null)} onChanged={load} />}
    </div>
  );
}

function StudentDrawer({ id, className, onClose, onChanged }: { id: string; className: string; onClose: () => void; onChanged: () => void }) {
  const [d, setD] = useState<StudentDetail | null>(null);
  const [edit, setEdit] = useState<string | null>(null);
  const load = useCallback(() => teacherApi.student(id, className).then(setD), [id, className]);
  useEffect(() => { load(); }, [load]);
  if (!d) return null;
  const save = async (patch: { name?: string; active?: boolean }) => { await teacherApi.rosterEdit(id, className, patch); setEdit(null); load(); onChanged(); };
  return (
    <div className="t-drawer-bg" onClick={onClose}>
      <aside className="t-drawer" onClick={(e) => e.stopPropagation()} aria-label="פירוט תלמיד">
        <div className="t-card-top">
          {edit === null
            ? <div className="t-h">{d.student.name}</div>
            : <input className="join-input" value={edit} maxLength={40} onChange={(e) => setEdit(e.target.value)} />}
          <button className="x big" onClick={onClose} aria-label="סגור">×</button>
        </div>
        <div className="st-actions">
          {edit === null
            ? <button className="secondary auto sm-btn" onClick={() => setEdit(d.student.name)}>שינוי שם</button>
            : <button className="primary sm-btn" onClick={() => save({ name: edit })} disabled={!edit.trim()}>שמירה</button>}
          <button className="secondary auto sm-btn" onClick={() => save({ active: !d.student.active })}>
            {d.student.active ? "סימון כלא פעיל (עזב את הכיתה)" : "החזרה לרשימה"}</button>
        </div>

        <div className="t-h sm2">ממוצע מחוון</div>
        <div className="st-avg">
          {d.aspects.map((a, i) => { const v = d.averages[i]; const [bg, fg] = heat(v); return (
            <div key={a} style={{ background: bg, color: fg }}><span className="sm">{a}</span><b>{v === null ? "—" : v.toFixed(1)}</b></div>); })}
        </div>

        <div className="t-h sm2">שליטה בכרטיסי ידע</div>
        <div className="st-mastery">
          {d.mastery.map((m) => (
            <div key={m.id} className={m.value === null ? "nodata" : ""}>
              <span className="sm">{m.title}</span>
              {m.value === null ? <span className="muted sm">אין נתונים</span> : (
                <><div className="cv-mtrack"><div style={{ width: `${m.value * 100}%` }} /></div><b className="sm">{Math.round(m.value * 100)}%</b></>
              )}
            </div>
          ))}
        </div>

        <div className="t-h sm2">שיעורים ({d.sessions.length})</div>
        {!d.sessions.length && <p className="muted sm">עדיין לא השתתף בשיעור.</p>}
        <ol className="st-timeline">
          {[...d.sessions].reverse().map((s) => (
            <li key={s.session}>
              <div className="t-card-top">
                <b dir="ltr">{ddmm(s.date)}</b>
                <span className="sm">תרגיל {s.number} · {s.title}</span>
                <a className="sm" href={`/teacher/${s.lesson}`}>לשיעור</a>
              </div>
              <div className="muted sm">{s.group}{s.partners.length ? ` · עם ${s.partners.join(", ")}` : ""} · {s.finished ? "סיים" : `הגיע עד ${s.stage}`} · {s.hints} רמזים</div>
              <div className="st-scores">
                {s.scores.map((v, i) => { const [bg, fg] = heat(v); return <span key={i} title={d.aspects[i]} style={{ background: bg, color: fg }}>{v ?? "—"}</span>; })}
                <b className="sm">{s.total}/8{s.confirmed ? " · אושר" : " · מוצע"}</b>
              </div>
              {s.misconceptions.length > 0 && <div className="st-mis">{s.misconceptions.map((m) => <span key={m.id} className="st-mchip">{m.label}</span>)}</div>}
              {s.teacher_note && <div className="sm">הערת מורה: {s.teacher_note}</div>}
            </li>
          ))}
        </ol>
      </aside>
    </div>
  );
}
