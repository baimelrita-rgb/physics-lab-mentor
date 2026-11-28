import { useState } from "react";
import { fmt } from "./Chart";
import type { Preview, SetupComponent } from "./api";

/* ---------- Step 3: what the students will go through ---------- */

type Stage = { key: string; n: number; title: string; short: string; body: React.ReactNode };

export function ExerciseFlow({ p, showKey }: { p: Preview; showKey: boolean }) {
  const st = p.student;
  const stages: Stage[] = [
    { key: "theory", n: 1, title: "רקע", short: `${st.cards.length} כרטיסים + שאלת הבנה`,
      body: <><Chips items={st.cards} /><Q label="שאלת הבנה" text={st.check} answer={showKey ? p.key.check_answer : undefined} /></> },
    { key: "predict", n: 2, title: "תחזית", short: "כיוון שינוי לכל ערוץ", body: <Q text={st.predict} /> },
    { key: "observe", n: 3, title: "צפייה", short: `עצירה בשנייה ${st.stop_s}`, body: <Q text={st.observe} /> },
    { key: "hyp", n: 4, title: "השערה", short: `${st.hypotheses.length} אפשרויות`,
      body: <Chips items={st.hypotheses} mark={showKey ? p.key.cause : undefined} /> },
    { key: "evidence", n: 5, title: "ראיות", short: `${st.channels.length} ערוצים לפתיחה`,
      body: <><Chips items={st.channels} />{showKey && <div className="pv-keyline">ראיות נדרשות: {p.key.evidence.join(" · ")}</div>}</> },
    { key: "reason", n: 6, title: "נימוק", short: `${st.hints.length} רמזים בסולם`, body: <HintLadder hints={st.hints} /> },
    ...(st.recheck ? [{ key: "recheck", n: 7, title: "בדיקה חוזרת", short: "חלון אחרי העצירה", body: <Q text={st.recheck} /> }] : []),
    { key: "exit", n: st.recheck ? 8 : 7, title: "שאלת יציאה", short: "שאלה פתוחה", body: <Q text={st.exit} /> },
  ];
  const [cur, setCur] = useState("theory");
  const stage = stages.find((s) => s.key === cur) ?? stages[0];
  return (
    <div className="pv">
      <ol className="pv-flow" aria-label="שלבי התרגיל אצל התלמיד">
        {stages.map((s) => (
          <li key={s.key}>
            <button className={`pv-stage ${s.key === cur ? "cur" : ""}`} onClick={() => setCur(s.key)} aria-pressed={s.key === cur}>
              <span className="pv-n">{s.n}</span>
              <span className="pv-t">{s.title}</span>
              <span className="pv-s">{s.short}</span>
            </button>
          </li>
        ))}
      </ol>
      <div className="pv-detail">
        <div className="pv-dh">{stage.n} · {stage.title}</div>
        {stage.body}
      </div>
      <Timeline p={p} showKey={showKey} />
    </div>
  );
}

function Q({ label, text, answer }: { label?: string; text: string; answer?: string }) {
  return (
    <div className="pv-q">
      {label && <div className="muted sm">{label}</div>}
      <div>{text}</div>
      {answer && <div className="pv-keyline">תשובה: {answer}</div>}
    </div>
  );
}

function Chips({ items, mark }: { items: string[]; mark?: string }) {
  return <div className="pv-chips">{items.map((x) => <span key={x} className={`pv-chip ${mark === x ? "key" : ""}`}>{x}</span>)}</div>;
}

function HintLadder({ hints }: { hints: string[] }) {
  return (
    <ol className="pv-ladder">
      {hints.map((h, i) => <li key={h}><span className="pv-rung">רמז {i + 1}</span><span>{h}</span></li>)}
    </ol>
  );
}

const WIN: Record<string, [string, string]> = { before: ["לפני", "w-before"], after: ["אחרי", "w-after"], recheck: ["בדיקה חוזרת", "w-recheck"] };

export function Timeline({ p, showKey }: { p: Preview; showKey: boolean }) {
  const { duration, stop_s, windows, runs } = p.timeline;
  if (!duration) return null;
  const pct = (t: number) => `${(t / duration) * 100}%`;
  const ticks = Array.from({ length: Math.floor(duration / 10) + 1 }, (_, i) => i * 10);
  return (
    <div className="tl">
      <div className="tl-h"><b>ההקלטה</b> <span className="muted sm">{duration} שניות{runs > 1 ? ` · ${runs} הרצות` : ""}</span></div>
      <div className="tl-bar" dir="ltr">
        <div className="tl-seen" style={{ width: pct(stop_s) }} />
        {Object.entries(windows).filter(([k]) => WIN[k]).map(([k, [a, b]]) => (
          <div key={k} className={`tl-win ${WIN[k][1]}`} style={{ left: pct(a), width: pct(b - a + 1) }} title={`${WIN[k][0]}: ${a}–${b} s`} />
        ))}
        {runs > 1 && Array.from({ length: runs - 1 }, (_, i) => <div key={i} className="tl-run" style={{ left: pct(((i + 1) * duration) / runs) }} />)}
        {showKey && p.setup.scenario.map((e, i) => (
          <div key={i} className={`tl-ev ${e.how}`} style={{ left: pct(e.t[0]), width: `max(4px, ${pct(e.t[1] - e.t[0] + 1)})` }} title={e.action} />
        ))}
        <div className="tl-stop" style={{ left: pct(stop_s) }}><span>עצירה בשנייה {stop_s}</span></div>
      </div>
      <div className="tl-ticks" dir="ltr">{ticks.map((t) => <span key={t} style={{ left: pct(t) }}>{t}</span>)}</div>
      <div className="tl-legend">
        {Object.keys(windows).filter((k) => WIN[k]).map((k) => <span key={k}><i className={WIN[k][1]} />{WIN[k][0]}</span>)}
        <span><i className="tl-seen-i" />מה שהתלמיד רואה לפני העצירה</span>
        {showKey && <span><i className="ev-i" />שינוי בעמדה (מפתח)</span>}
      </div>
    </div>
  );
}

/* ---------- Step 4: station setup ---------- */

export function StationSetup({ p }: { p: Preview }) {
  const s = p.setup;
  const path = s.components.filter((c) => c.id !== "CTL-01");
  const ctl = s.components.find((c) => c.id === "CTL-01");
  return (
    <div className="ss">
      <div className="ss-h"><b>מצב התחלה</b> <span className="chip okc sm-chip">{s.point}</span></div>
      <div className="ss-path">
        {path.map((c, i) => (
          <div key={c.id} className="ss-cell">
            <ComponentBox c={c} />
            {i < path.length - 1 && <span className="ss-arrow" aria-hidden>←</span>}
          </div>
        ))}
      </div>
      {ctl && <div className="ss-ctl"><ComponentBox c={ctl} wide /></div>}

      <div className="ss-h"><b>קריאות צפויות לפני תחילת התרגיל</b></div>
      <div className="ss-expect">
        {s.expect.map((e) => (
          <div key={e.channel} className="ss-gauge"><span className="muted sm">{e.name}</span><b dir="ltr">{fmt(e.value)} <small>{e.unit}</small></b></div>
        ))}
      </div>
    </div>
  );
}

function ComponentBox({ c, wide }: { c: SetupComponent; wide?: boolean }) {
  return (
    <div className={`ss-box ${c.needed ? "" : "off"} ${wide ? "wide" : ""}`}>
      <div className="ss-name">{c.name}</div>
      <div className="ss-model" dir="auto">{c.model}</div>
      {c.settings.length > 0 && (
        <ul className="ss-set">
          {c.settings.map((x) => (
            <li key={x.param} title={x.note ?? ""}>
              <span className="muted">{x.param}</span>
              <b dir="auto">{typeof x.value === "number" ? `${fmt(x.value)} ${x.unit ?? ""}` : x.value}</b>
              {x.status === "proposed" && <span className="ss-prop" title="ערך מוצע, לאמת בעמדה">?</span>}
            </li>
          ))}
        </ul>
      )}
      {!c.needed && <div className="muted sm">לא נדרש בתרגיל הזה</div>}
    </div>
  );
}

export function Scenario({ p }: { p: Preview }) {
  const s = p.setup;
  return (
    <div className="sc">
      <div className={`sc-live ${s.live.ok ? "ok" : "no"}`}>
        <b>{s.live.ok ? "אפשר לשחזר בעמדה חיה" : "לא לשחזר בעמדה חיה"}</b> · {s.live.note}
      </div>
      <ol className="sc-list">
        {s.scenario.map((e, i) => (
          <li key={i}>
            <span className="sc-t" dir="ltr">{e.t[0] === e.t[1] ? `${e.t[0]} s` : `${e.t[0]}–${e.t[1]} s`}</span>
            <span className="sc-comp">{e.component_name}</span>
            <span className={`sc-how ${e.how}`}>{e.how === "physical" ? "בעמדה" : "בתוכנה"}</span>
            <span className="sc-act">{e.action}{e.note && <span className="muted"> · {e.note}</span>}</span>
          </li>
        ))}
      </ol>
    </div>
  );
}

export function EnvelopeCheck({ p }: { p: Preview }) {
  const L: Record<string, [string, string]> = { ok: ["בתוך המעטפת", "ok"], warn: ["מתקרב לסף", "warn"], stop: ["חריגה", "stop"] };
  return (
    <div className="env">
      {p.setup.envelope.map((r) => (
        <div key={r.id} className={`env-tile ${L[r.level][1]}`}>
          <div className="sm"><b dir="ltr">{r.id}</b> {r.title}</div>
          <div className="env-state">{L[r.level][0]}{r.value !== null && <span className="env-num">שיא <bdi dir="ltr">{fmt(r.value)}</bdi> מול סף <bdi dir="ltr">{fmt(r.limit ?? 0)}</bdi></span>}</div>
          <div className="muted sm">{r.status === "approved" ? "סף מאושר" : "סף מוצע, ממתין לתלם"}</div>
        </div>
      ))}
    </div>
  );
}
