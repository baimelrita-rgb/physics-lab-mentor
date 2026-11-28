import { useCallback, useEffect, useMemo, useState } from "react";
import { ApiError, authApi, teacherApi, type ContentDoc, type ContentField, type ContentItem, type Me } from "./api";
import { TeacherHeader } from "./Teacher";

type Values = Record<string, unknown>;
const STATUS: Record<string, [string, string]> = { approved: ["תוכן מאושר", "okc"], draft: ["טיוטה", "draft"] };

export function ContentTab() {
  const [list, setList] = useState<ContentItem[]>([]);
  const [cur, setCur] = useState<string | null>(new URLSearchParams(location.search).get("ex"));
  const loadList = useCallback(() => teacherApi.contentList().then((l) => { setList(l); setCur((c) => c ?? l[0]?.id ?? null); }), []);
  useEffect(() => { loadList(); }, [loadList]);
  return (
    <div className="t-page">
      <TeacherHeader tab="content" />
      <div className="t-wrap ct-layout">
        <nav className="panel t-section ct-list" aria-label="תרגילים">
          <div className="t-h">תרגילים</div>
          {list.map((e) => (
            <button key={e.id} className={`ct-item ${cur === e.id ? "cur" : ""}`} onClick={() => setCur(e.id)} aria-current={cur === e.id}>
              <b>{e.number} · {e.title}</b>
              <span className="ct-tags">
                <span className={`chip ${STATUS[e.status][1]} sm-chip`}>{STATUS[e.status][0]}</span>
                {e.errors > 0 && <span className="ct-err-n">{e.errors} לתיקון</span>}
                {e.edited && <span className="muted sm">נערך כאן</span>}
              </span>
            </button>
          ))}
          <a className="secondary auto link-btn ct-export" href="/api/teacher/content/export.yaml">ייצוא השינויים (YAML)</a>
          <p className="muted sm">השינויים נשמרים בשרת. כדי שייכנסו גם למאגר הקוד, מייצאים אותם ומעדכנים את תיקיית content.</p>
        </nav>
        {cur && <Editor key={cur} id={cur} onChanged={loadList} />}
      </div>
    </div>
  );
}

function Editor({ id, onChanged }: { id: string; onChanged: () => void }) {
  const [doc, setDoc] = useState<ContentDoc | null>(null);
  const [vals, setVals] = useState<Values>({});
  const [serverErrors, setServerErrors] = useState<{ path: string; message: string }[]>([]);
  const [msg, setMsg] = useState<string | null>(null);
  const [showHistory, setShowHistory] = useState(false);
  const [me, setMe] = useState<Me | null>(null);
  useEffect(() => { authApi.me().then(setMe).catch(() => setMe(null)); }, []);

  const apply = (d: ContentDoc) => {
    setDoc(d);
    setVals(Object.fromEntries(d.fields.map((f) => [f.path, f.value])));
    setServerErrors(d.errors);
  };
  useEffect(() => { teacherApi.content(id).then(apply); }, [id]);

  const dirty = useMemo(() => doc ? doc.fields.filter((f) => JSON.stringify(vals[f.path]) !== JSON.stringify(f.value)).map((f) => f.path) : [], [doc, vals]);
  const leakTerms = ((vals["leak_terms"] as string[]) ?? []).filter((t) => t.trim());
  // Instant check while typing (the server checks again on save).
  const liveLeak = (f: ContentField): string | null => {
    if (f.audience !== "student") return null;
    const v = vals[f.path];
    const texts = Array.isArray(v) ? (v as string[]) : [String(v ?? "")];
    const hit = leakTerms.find((t) => texts.some((x) => x.includes(t)));
    return hit ? `חושף את התשובה: ״${hit}״` : null;
  };

  if (!doc) return <section className="panel t-section">טוען…</section>;
  const set = (path: string, v: unknown) => { setVals((x) => ({ ...x, [path]: v })); setMsg(null); };
  // A field being edited shows the live checks; the server's errors return on the next save.
  const errorsFor = (path: string) => {
    if (!dirty.includes(path)) return serverErrors.filter((e) => e.path === path);
    const out: { path: string; message: string }[] = [];
    const v = vals[path];
    if (path === "hints") (v as string[]).forEach((h, i) => { if (h.trim() && !h.trim().endsWith("?")) out.push({ path, message: `רמז ${i + 1} צריך להיות שאלה (להסתיים בסימן שאלה).` }); });
    if ((Array.isArray(v) ? (v as string[]) : [String(v ?? "")]).some((x) => !x.trim())) out.push({ path, message: "שדה ריק." });
    return out;
  };

  const save = async () => {
    try {
      const r = await teacherApi.contentSave(id, Object.fromEntries(dirty.map((p) => [p, vals[p]])));
      if (!r.saved) { setServerErrors(r.errors); setMsg("לא נשמר. יש שדות לתיקון."); return; }
      apply(r.exercise); setMsg(r.changed.length ? "נשמר. התרגיל חזר לטיוטה עד שיאושר שוב." : "אין שינוי לשמור."); onChanged();
    } catch (e) { setMsg(e instanceof ApiError ? e.message : "שגיאה"); }
  };
  const action = async (a: "approve" | "revert") => {
    if (a === "revert" && !confirm("לחזור לנוסח שבמאגר? השינויים שנעשו כאן יימחקו (ההיסטוריה נשמרת).")) return;
    try { apply(await teacherApi.contentAction(id, a)); setMsg(a === "approve" ? "התוכן אושר." : "חזר לנוסח שבמאגר."); onChanged(); }
    catch (e) { setMsg(e instanceof ApiError ? e.message : "שגיאה"); }
  };

  const student = doc.fields.filter((f) => f.audience === "student");
  const teacherOnly = doc.fields.filter((f) => f.audience === "teacher");
  const edited = doc.fields.some((f) => f.changed);
  const approver = me?.can_approve !== false;          // the tenant's content approver (MVP package 4)
  const canApprove = approver && !dirty.length && !serverErrors.length && doc.status !== "approved";

  const fieldBox = (f: ContentField) => {
    const errs = errorsFor(f.path);
    const live = liveLeak(f);
    const isDirty = dirty.includes(f.path);
    return (
      <div key={f.path} className={`ct-field ${errs.length || live ? "bad" : ""}`}>
        <label className="ct-label">
          {f.label}
          {isDirty && <span className="ct-dirty">לא נשמר</span>}
          {!isDirty && f.changed && <span className="muted sm">שונה מהמאגר</span>}
        </label>
        <FieldInput f={f} value={vals[f.path]} onChange={(v) => set(f.path, v)} vals={vals} setOther={set} />
        {live && <div className="ct-msg">{live}</div>}
        {errs.map((e, i) => <div key={i} className="ct-msg">{e.message}</div>)}
      </div>
    );
  };

  return (
    <div className="ct-main">
      <section className="panel t-section">
        <div className="ct-head">
          <div>
            <div className="t-h">תרגיל {doc.number} · {String(vals["title"] ?? "")}</div>
            <div className="muted sm">
              <span className={`chip ${STATUS[doc.status][1]} sm-chip`}>{STATUS[doc.status][0]}</span>
              {doc.approved_by && <> אושר בידי {doc.approved_by} ב־<bdi dir="ltr">{doc.approved_at?.replace("T", " ").slice(0, 16)}</bdi></>}
              {doc.status === "approved" && !doc.approved_by && " (מאושר במאגר)"}
            </div>
          </div>
          <div className="ct-actions">
            <a className="secondary auto link-btn" href="/teacher/prep">תצוגה מקדימה באשף</a>
            {edited && approver && <button className="secondary auto" onClick={() => action("revert")}>חזרה לנוסח המאגר</button>}
            {approver ? <button className="primary" disabled={!canApprove} onClick={() => action("approve")}
              title={dirty.length ? "קודם שומרים" : serverErrors.length ? "יש שדות לתיקון" : ""}>אישור התוכן</button>
              : <span className="muted sm">את השינויים מאשר/ת אחראי/ת התוכן של בית הספר.</span>}
          </div>
        </div>
        {serverErrors.length > 0 && (
          <div className="note warn sm">{serverErrors.length} דברים לתקן לפני אישור. השדות מסומנים באדום.</div>
        )}
      </section>

      <section className="panel t-section">
        <div className="t-h">מה התלמידים רואים</div>
        <p className="muted sm">אסור שיופיעו כאן מילים מרשימת ״מילים שאסור לראות״. הבדיקה רצה בזמן הקלדה ושוב בשמירה.</p>
        {student.map(fieldBox)}
      </section>

      <section className="panel t-section">
        <div className="t-h">למורה בלבד</div>
        {teacherOnly.filter((f) => f.path !== "check_answer").map(fieldBox)}
      </section>

      <section className="panel t-section">
        <div className="t-h">קבוע מהנתונים <span className="muted sm">(לא נערך כאן)</span></div>
        <div className="ct-fixed">
          <span><span className="muted">הקלטה</span> <b dir="ltr">{doc.fixed.recording}</b></span>
          <span><span className="muted">עצירה</span> <b>שנייה {doc.fixed.stop_s}</b></span>
          <span><span className="muted">הסיבה</span> <b>{doc.fixed.cause}</b></span>
          <span><span className="muted">ראיות נדרשות</span> <b>{doc.fixed.evidence.join(" · ")}</b></span>
        </div>
        <p className="muted sm">הסיבה, הראיות והחלונות קשורים למנוע האבחון ולהקלטה, ולכן משתנים רק בקבצים במאגר.</p>
      </section>

      <section className="panel t-section">
        <button className="more-btn" onClick={() => setShowHistory(!showHistory)}>{showHistory ? "הסתרת ההיסטוריה" : `היסטוריית שינויים (${doc.history.length})`}</button>
        {showHistory && (
          <ol className="ct-history">
            {doc.history.map((h, i) => (
              <li key={i}>
                <bdi dir="ltr" className="muted sm">{h.at.replace("T", " ").slice(0, 16)}</bdi> · <b>{h.by}</b> ·{" "}
                {h.field === "revert" ? "חזרה לנוסח המאגר" : h.field === "status" ? "אישור התוכן"
                  : <>שינוי ב{doc.fields.find((f) => f.path === h.field)?.label ?? h.field}</>}
              </li>
            ))}
            {!doc.history.length && <li className="muted sm">אין עדיין שינויים.</li>}
          </ol>
        )}
      </section>

      {(dirty.length > 0 || msg) && (
        <div className="ct-savebar">
          {msg && <span>{msg}</span>}
          {dirty.length > 0 && <>
            <span>{dirty.length} שדות שונו</span>
            <button className="secondary auto" onClick={() => apply(doc)}>ביטול</button>
            <button className="primary" onClick={save}>שמירה</button>
          </>}
        </div>
      )}
    </div>
  );
}

function FieldInput({ f, value, onChange, vals, setOther }: {
  f: ContentField; value: unknown; onChange: (v: unknown) => void; vals: Values; setOther: (p: string, v: unknown) => void;
}) {
  if (f.kind === "text") {
    const v = String(value ?? "");
    return <textarea className="ct-input" rows={v.length > 90 ? 3 : 1} value={v} onChange={(e) => onChange(e.target.value)} />;
  }
  const items = (value as string[]) ?? [];
  if (f.path === "leak_terms") return <TermsInput items={items} onChange={onChange} />;
  if (f.path === "check.choices") {
    const ans = Number(vals["check_answer"] ?? 0);
    return (
      <div className="ct-choices">
        {items.map((c, i) => (
          <div key={i} className="ct-choice">
            <label className="ct-radio" title="התשובה הנכונה (למורה בלבד)">
              <input type="radio" name="check_answer" checked={ans === i} onChange={() => setOther("check_answer", i)} /> נכונה
            </label>
            <input className="ct-input" value={c} onChange={(e) => onChange(items.map((x, j) => (j === i ? e.target.value : x)))} />
            {items.length > 2 && <button className="x" aria-label="הסרה" onClick={() => {
              onChange(items.filter((_, j) => j !== i));
              if (ans >= i && ans > 0) setOther("check_answer", ans === i ? 0 : ans - 1);
            }}>×</button>}
          </div>
        ))}
        {items.length < 4 && <button className="more-btn" onClick={() => onChange([...items, ""])}>+ תשובה</button>}
      </div>
    );
  }
  // hints: fixed ladder of three
  return (
    <ol className="ct-hints">
      {items.map((h, i) => (
        <li key={i}><span className="pv-rung">רמז {i + 1}</span>
          <textarea className="ct-input" rows={1} value={h} onChange={(e) => onChange(items.map((x, j) => (j === i ? e.target.value : x)))} />
        </li>
      ))}
    </ol>
  );
}

function TermsInput({ items, onChange }: { items: string[]; onChange: (v: string[]) => void }) {
  const [t, setT] = useState("");
  const add = () => { const v = t.trim(); if (v && !items.includes(v)) onChange([...items, v]); setT(""); };
  return (
    <div className="ct-terms">
      <div className="pv-chips">
        {items.map((x) => (
          <span key={x} className="pv-chip ct-term">{x}<button className="x" aria-label={`הסרת ${x}`} onClick={() => onChange(items.filter((y) => y !== x))}>×</button></span>
        ))}
      </div>
      <form className="st-inline" onSubmit={(e) => { e.preventDefault(); add(); }}>
        <input className="ct-input" value={t} placeholder="מילה או צירוף" onChange={(e) => setT(e.target.value)} />
        <button className="secondary auto" type="submit" disabled={!t.trim()}>הוספה</button>
      </form>
    </div>
  );
}
