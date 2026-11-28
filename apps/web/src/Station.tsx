import { useCallback, useEffect, useState } from "react";
import { api, ApiError, type View } from "./api";
import { Chart, fmt, qualityLabel } from "./Chart";

const COLORS = ["#15191E", "#1E4FA8", "#C2570C"];
const DIRS: [string, string][] = [["up", "עולה"], ["down", "יורד"], ["same", "לא משתנה"]];
const EXPECT: [string, string][] = [["up", "יעלה"], ["down", "ירד"], ["same", "לא ישתנה"], ["unsure", "לא בטוח"]];
const READING_STATES = ["HYPOTHESIZE", "EVIDENCE", "REASON", "RECHECK"];
const HINT_STATES = READING_STATES;

export function Station({ id }: { id: string }) {
  const [v, setV] = useState<View | null>(null);
  const [error, setError] = useState<string | null>(null);

  const act = useCallback(async (p: Promise<View>) => {
    try { setV(await p); setError(null); }
    catch (e) { setError(e instanceof ApiError ? e.message : "שגיאת תקשורת"); }
  }, []);

  useEffect(() => {
    let alive = true;
    const tick = async () => { try { const nv = await api.get(id); if (alive) setV(nv); } catch { /* keep last view */ } };
    tick();
    const h = setInterval(tick, 700);
    return () => { alive = false; clearInterval(h); };
  }, [id]);

  if (!v) return <div className="loading">טוען…</div>;
  const ex = v.exercise;

  return (
    <div className="station">
      <header className="topbar">
        <div className="tb-group">
          <div className="tb-title">עמדת מנוע תלת־פאזי</div>
          <div className="tb-sub">{v.label}</div>
        </div>
        <div className="tb-group">
          <span className="chip dark">{v.recording.alias}</span>
          <span className="chip amber">הקלטה · נתונים סינתטיים</span>
          {ex.status === "draft" && <span className="chip draft">תוכן טיוטה</span>}
        </div>
        <div className="tb-group tb-clock">
          <span>זמן הרצה</span>
          <span dir="ltr" className="tb-time">{Math.max(v.visible_t, 0)} s</span>
          {v.visible_t === ex.stop_s && ["OBSERVE", "HYPOTHESIZE", "EVIDENCE", "REASON"].includes(v.state) && (
            <span className="tb-stop">עצירה</span>
          )}
        </div>
      </header>

      <nav className="stepper" aria-label="שלבי התרגיל">
        {v.steps.map((label, i) => (
          <div key={label} className={`step ${i === v.step ? "cur" : i < v.step ? "done" : ""}`}>
            <span className="step-n">{i + 1}</span><span>{label}</span>
          </div>
        ))}
        <div className="step-ex">תרגיל: {ex.title}</div>
      </nav>

      {v.paused && <div className="paused">המורה השהה את העבודה. המתינו להוראות.</div>}

      <main className="work">
        {v.state === "THEORY" ? <Theory v={v} act={act} /> :
         v.state === "PREDICT" ? <Predict v={v} act={act} /> :
         <Investigate v={v} act={act} />}
        <Mentor v={v} act={act} error={error} />
      </main>

      <footer className="footbar">
        <span>הפעלה ועצירה בלחצנים הפיזיים בלבד · המסך לקריאה</span>
        <span>קו מקווקו = רגע נוכחי · אזור אפור = נתון חסר</span>
      </footer>
    </div>
  );
}

type P = { v: View; act: (p: Promise<View>) => void };

function Theory({ v, act }: P) {
  const ex = v.exercise;
  const hl = v.theory_answer && !v.theory_answer.correct ? ex.check.highlight_card : null;
  return (
    <section className="panel center theory">
      <div className="lead">{ex.title} · {ex.subtitle}</div>
      <div className="cards">
        {ex.cards.map((c) => (
          <article key={c.id} className={`kcard ${hl === c.id ? "hl" : ""}`}>
            <div className="kcard-id">{c.id}</div>
            <h3>{c.title}</h3>
            <p>{c.body}</p>
            {c.formula && <div className="formula" dir="ltr">{c.formula}</div>}
          </article>
        ))}
      </div>
      <div className="check">
        <div className="check-q">שאלת הבנה: {ex.check.question}</div>
        <div className="chips">
          {ex.check.choices.map((c, i) => (
            <button key={c} className={`chip-btn ${v.theory_answer?.choice === i ? "sel" : ""}`}
                    onClick={() => act(api.theory(v.id, i))}>{c}</button>
          ))}
        </div>
        {v.theory_answer && (
          <div className={`note ${v.theory_answer.correct ? "ok" : "warn"}`}>
            {v.theory_answer.correct ? "נכון." : "לא בדיוק. קראו שוב את הכרטיס המודגש ונסו שוב."}
          </div>
        )}
      </div>
    </section>
  );
}

function Predict({ v, act }: P) {
  const [dirs, setDirs] = useState<Record<string, string>>(v.prediction?.directions ?? {});
  const [text, setText] = useState(v.prediction?.text ?? "");
  const submit = async () => {
    await act(api.predict(v.id, dirs, text));
    await act(api.advance(v.id));
  };
  return (
    <section className="panel center predict">
      <div className="lead">תחזית</div>
      <p className="prompt">{v.mentor}</p>
      {v.exercise.predict_channels.map((c) => (
        <div key={c.key} className="pred-row">
          <span className="pred-name">{c.name}</span>
          <div className="chips">
            {DIRS.map(([k, label]) => (
              <button key={k} className={`chip-btn ${dirs[c.key] === k ? "sel" : ""}`}
                      onClick={() => setDirs({ ...dirs, [c.key]: k })}>{label}</button>
            ))}
          </div>
        </div>
      ))}
      <label className="field-label" htmlFor="ptext">למה? (לא חובה, עד 300 תווים)</label>
      <textarea id="ptext" rows={3} maxLength={300} value={text} onChange={(e) => setText(e.target.value)} />
      <button className="primary big" disabled={!Object.keys(dirs).length && !text.trim()} onClick={submit}>
        שמרו תחזית והתחילו את ההקלטה
      </button>
    </section>
  );
}

function Investigate({ v, act }: P) {
  const ex = v.exercise;
  const [asking, setAsking] = useState<string | null>(null);
  const keys = Object.keys(v.series).slice(-3);
  const canRead = READING_STATES.includes(v.state) && !v.paused;
  const windows = v.state === "RECHECK" || v.state === "EXIT" || v.state === "CLOSED"
    ? { before: ex.windows.before, after: ex.windows.recheck }
    : { before: ex.windows.before, after: ex.windows.after };

  return (
    <>
      <section className="panel channels" aria-label="ערוצי מדידה">
        <div className="panel-title">ערוצי מדידה</div>
        {v.groups.map((g) => (
          <div key={g.id} className="ch-group">
            <div className="ch-group-title">{g.title}</div>
            {g.channels.map((c) => (
              <div key={c.key}>
                <button className={`ch ${c.open ? "open" : ""}`}
                        onClick={() => c.open ? act(api.close(v.id, c.key)) : setAsking(asking === c.key ? null : c.key)}>
                  <span>{c.name}</span><span className={`dot ${c.open ? "on" : ""}`} />
                </button>
                {asking === c.key && (
                  <div className="expect">
                    <div>מה אתם מצפים לראות?</div>
                    <div className="chips">
                      {EXPECT.map(([k, label]) => (
                        <button key={k} className="chip-btn sm" onClick={() => { setAsking(null); act(api.open(v.id, c.key, k)); }}>{label}</button>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        ))}
      </section>

      <section className="graphs">
        <div className="panel graph-panel">
          <div className="legend">
            <span><i className="sw before" />חלון לפני · {windows.before[0]}–{windows.before[1]} s</span>
            <span><i className="sw after" />חלון אחרי · {windows.after[0]}–{windows.after[1]} s</span>
            <span className="legend-hint">{canRead ? "לחצו על נקודה בגרף כדי לשמור קריאה" : "ציר זמן משותף · שניות מתחילת ההרצה"}</span>
          </div>
          {keys.map((k, i) => (
            <Chart key={k} name={v.series[k].name} unit={v.series[k].unit} points={v.series[k].points}
                   duration={ex.duration} visibleT={v.visible_t} windows={windows} color={COLORS[i % 3]}
                   clickable={canRead} onPick={(t) => act(api.reading(v.id, k, t))}
                   runs={v.recording.runs.length > 1 ? v.recording.runs : []} />
          ))}
          <div className="xaxis" dir="ltr">
            {Array.from({ length: Math.floor((ex.duration - 1) / (ex.duration > 50 ? 10 : 5)) + 1 }, (_, i) => i * (ex.duration > 50 ? 10 : 5)).map((t) => (
              <span key={t} style={{ left: `${((8 + (t / ex.duration) * 664) / 680) * 100}%` }}>{t}</span>
            ))}
            <span style={{ left: "98.8%" }}>{ex.duration} s</span>
          </div>
        </div>
        <Tray v={v} act={act} />
      </section>
    </>
  );
}

function Tray({ v, act }: P) {
  if (!READING_STATES.includes(v.state) && !v.readings.length) return null;
  return (
    <div className="panel tray">
      <div className="tray-title">קריאות שאספתם</div>
      {!v.readings.length && <span className="muted">עדיין אין קריאות.</span>}
      {v.readings.map((r) => (
        <span key={r.id} className={`reading q-${r.quality}`}>
          {r.name} · <span dir="ltr">{r.value === null ? "חסר" : `${fmt(r.value)} ${r.unit}`}</span> · ש׳ {r.t}
          {r.quality !== "ok" && <> · {qualityLabel(r.quality, r.age_s)}</>}
          {READING_STATES.includes(v.state) && v.state !== "REASON" && (
            <button className="x" aria-label="הסר קריאה" onClick={() => act(api.removeReading(v.id, r.id))}>×</button>
          )}
        </span>
      ))}
    </div>
  );
}

function Mentor({ v, act, error }: P & { error: string | null }) {
  const ex = v.exercise;
  const [cited, setCited] = useState<string[]>([]);
  const [text, setText] = useState("");
  const hyp = ex.hypotheses.find((h) => h.code === v.hypothesis);
  const hintsLeft = v.hints.quota - v.hints.used;

  return (
    <aside className="panel mentor" aria-label="מנטור">
      <div className="mentor-head">
        <div className="mentor-title">מנטור</div>
        <span className="muted sm">המורה רואה את השיחה</span>
      </div>

      {hyp && v.state !== "HYPOTHESIZE" && (
        <div className="box">
          <div className="muted sm">ההשערה שלכם</div>
          <div>{hyp.label}</div>
        </div>
      )}

      {v.note_from_teacher && (
        <div className="note teacher"><div className="muted sm">הודעה מהמורה</div>{v.note_from_teacher}</div>
      )}

      {v.feedback && ["EVIDENCE", "RECHECK"].includes(v.state) && (
        <div className={`note ${v.feedback.passed ? "ok" : "warn"}`}>{v.feedback.message}</div>
      )}

      <div className="mentor-card">
        <p>{v.mentor}</p>
        {v.state === "THEORY" && <button className="primary" onClick={() => act(api.advance(v.id))}>התחילו</button>}
        {v.state === "OBSERVE" && (v.visible_t >= ex.stop_s
          ? <button className="primary" onClick={() => act(api.advance(v.id))}>ראיתי, בואו נסביר</button>
          : <div className="muted">ההקלטה מתנגנת… שנייה {Math.max(v.visible_t, 0)} מתוך {ex.stop_s}</div>)}
      </div>

      {(v.state === "HYPOTHESIZE" || v.state === "REASON") && (
        <div className="stack">
          <div className="muted sm">{v.state === "HYPOTHESIZE" ? "בחרו השערה" : "ההשערה בנימוק"}</div>
          <div className="chips">
            {ex.hypotheses.map((h) => (
              <button key={h.code} className={`chip-btn ${v.hypothesis === h.code ? "sel" : ""}`}
                      onClick={() => act(api.hypothesis(v.id, h.code))}>{h.label}</button>
            ))}
          </div>
          {v.state === "HYPOTHESIZE" && (
            <button className="primary" disabled={!v.hypothesis} onClick={() => act(api.advance(v.id))}>המשיכו לבדיקת ראיות</button>
          )}
        </div>
      )}

      {v.hints.given.length > 0 && (
        <div className="stack">
          {v.hints.given.map((h, i) => (
            <div key={i} className="hint"><span className="badge">רמז {i + 1} מתוך {v.hints.quota}{v.hints.sources[i] === "teacher" ? " · מהמורה" : ""}</span><p>{h}</p></div>
          ))}
        </div>
      )}

      {v.state === "REASON" && (
        <div className="stack">
          <div className="muted sm">צטטו קריאות (לפחות שתיים)</div>
          <div className="cite-list">
            {v.readings.map((r) => (
              <label key={r.id} className="cite">
                <input type="checkbox" checked={cited.includes(r.id)}
                       onChange={(e) => setCited(e.target.checked ? [...cited, r.id] : cited.filter((c) => c !== r.id))} />
                {r.name} · <span dir="ltr">{r.value === null ? "חסר" : `${fmt(r.value)} ${r.unit}`}</span> · ש׳ {r.t}
              </label>
            ))}
          </div>
          <label className="field-label" htmlFor="reason">נימוק (עד 300 תווים)</label>
          <textarea id="reason" rows={3} maxLength={300} placeholder="מה ראיתם, ומתי?" value={text} onChange={(e) => setText(e.target.value)} />
          <button className="primary big" onClick={() => act(api.reason(v.id, text, cited))}>שלחו נימוק</button>
        </div>
      )}

      {v.can_ask && <AskBox v={v} act={act} />}

      {v.state === "EXIT" && <ExitForm v={v} act={act} />}

      {v.state === "CLOSED" && (
        <div className="stack">
          <div className="note ok">התרגיל הושלם.</div>
          <div className="muted sm">נאספו {v.readings.length} קריאות · נעשה שימוש ב־{v.hints.used} רמזים</div>
        </div>
      )}

      <div className="mentor-foot">
        {v.state === "EVIDENCE" && (
          <button className="primary big" onClick={() => act(api.advance(v.id))}>עברו לנימוק</button>
        )}
        {v.state === "RECHECK" && (
          <button className="primary big" onClick={() => act(api.advance(v.id))}>בדקתי, המשך</button>
        )}
        {HINT_STATES.includes(v.state) && (
          <button className="secondary" disabled={hintsLeft <= 0} onClick={() => act(api.hint(v.id))}>
            רמז · {hintsLeft > 0 ? `נותרו ${hintsLeft}` : "אין רמזים נוספים"}
          </button>
        )}
        {error && <div className="note warn">{translate(error)}</div>}
      </div>
    </aside>
  );
}

function AskBox({ v, act }: P) {
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState(false);
  const send = async (text: string) => {
    if (!text.trim()) return;
    setBusy(true); await act(api.ask(v.id, text)); setBusy(false); setQ("");
  };
  return (
    <div className="stack ask">
      {v.mentor_reply && (
        <div className="reply">
          <p>{v.mentor_reply.text}</p>
          {v.mentor_reply.chips.length > 0 && (
            <div className="chips">
              {v.mentor_reply.chips.map((c) => <button key={c} className="chip-btn sm" disabled={busy} onClick={() => send(c)}>{c}</button>)}
            </div>
          )}
        </div>
      )}
      <div className="ask-row">
        <input aria-label="שאלה למנטור" maxLength={300} placeholder="שאלה למנטור (עד 300 תווים)" value={q}
               onChange={(e) => setQ(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter") send(q); }} />
        <button className="secondary auto" disabled={busy || !q.trim()} onClick={() => send(q)}>{busy ? "…" : "שאל"}</button>
      </div>
    </div>
  );
}

function ExitForm({ v, act }: P) {
  const [text, setText] = useState("");
  return (
    <div className="stack">
      <label className="field-label" htmlFor="exit">תשובה (עד 300 תווים)</label>
      <textarea id="exit" rows={4} maxLength={300} value={text} onChange={(e) => setText(e.target.value)} />
      <button className="primary big" disabled={!text.trim()} onClick={() => act(api.exit(v.id, text))}>שלחו וסיימו</button>
    </div>
  );
}

const ERRORS: Record<string, string> = {
  "save at least 2 readings": "שמרו לפחות שתי קריאות לפני שממשיכים.",
  "cite at least 2 readings": "סמנו לפחות שתי קריאות לנימוק.",
  "save a reading after the stop point": "שמרו לפחות קריאה אחת אחרי רגע העצירה.",
  "choose a hypothesis first": "בחרו השערה קודם.",
  "no hints left": "נוצלו כל הרמזים.",
  "channel is not open": "פתחו את הערוץ קודם.",
  "that second is not visible yet": "השנייה הזו עוד לא הוצגה.",
  "paused by teacher": "המורה השהה את העבודה.",
  "empty question": "כתבו שאלה קודם.",
};
function translate(e: string) { return ERRORS[e] ?? e; }
