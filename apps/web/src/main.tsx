import { StrictMode, useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import { api, ApiError, type ExerciseItem } from "./api";
import { Station } from "./Station";
import { Monitor, MonitorList } from "./Monitor";
import { TeacherHome, TeacherLive, TeacherLogin } from "./Teacher";
import { LessonPrep } from "./Prep";
import { ClassView } from "./ClassView";
import { Students } from "./Students";
import "./styles.css";

// Routes:
//   /                   home (choose teacher or station)
//   /teacher            open a lesson        /teacher/<lesson id>  live lesson
//   /join               station join screen (S0)
//   /station/<id>       student screen       /demo  exercise picker without a lesson
function App() {
  const path = location.pathname;
  let m;
  if ((m = path.match(/^\/station\/(\w+)/))) return <Station id={m[1]} />;
  if (path.startsWith("/teacher/login")) return <TeacherLogin />;
  if (path.startsWith("/teacher/prep")) return <LessonPrep />;
  if (path.startsWith("/teacher/class")) return <ClassView />;
  if (path.startsWith("/teacher/students")) return <Students />;
  if ((m = path.match(/^\/teacher\/(\w+)/))) return <TeacherLive lessonId={m[1]} />;
  if (path.startsWith("/teacher")) return <TeacherHome />;
  if ((m = path.match(/^\/monitor\/([\w-]+)/))) return <Monitor id={m[1]} />;
  if (path.startsWith("/monitor")) return <MonitorList />;
  if (path.startsWith("/join")) return <Join />;
  if (path.startsWith("/demo")) return <Picker />;
  return <Home />;
}

function Home() {
  return (
    <div className="picker">
      <h1>מנטור מעבדה · עמדה 1</h1>
      <p className="muted">גרסת הדגמה על נתונים סינתטיים.</p>
      <div className="picker-list">
        <a className="picker-item" href="/teacher"><b>מסך מורה</b><span>פתיחת שיעור ומעקב חי אחרי העמדות</span></a>
        <a className="picker-item" href="/join"><b>הצטרפות לעמדה</b><span>הקלדת קוד השיעור שהמורה פתח</span></a>
        <a className="picker-item" href="/demo"><b>תרגול בלי שיעור</b><span>פתיחת תרגיל ישירות, בלי מסך מורה</span></a>
        <a className="picker-item" href="/monitor"><b>ניטור עמדות</b><span>ערכים חיים מהבקר בעמדה ומצב מעטפת הבטיחות</span></a>
      </div>
    </div>
  );
}

function Join() {
  const params = new URLSearchParams(location.search);
  const [code, setCode] = useState(params.get("code") ?? "");
  const [label, setLabel] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [roster, setRoster] = useState<{ id: string; name: string; taken: boolean }[]>([]);
  const [members, setMembers] = useState<string[]>([]);
  useEffect(() => {
    setRoster([]); setMembers([]);
    if (code.length === 6) api.joinInfo(code).then((x) => setRoster(x.roster)).catch(() => setRoster([]));
  }, [code]);
  const toggle = (id: string) => setMembers((m) => (m.includes(id) ? m.filter((x) => x !== id) : [...m, id]));
  const go = async () => {
    try { const s = await api.join(code, label, members); location.href = `/station/${s.id}`; }
    catch (e) { setError(e instanceof ApiError && e.message === "lesson code not found" ? "הקוד לא נמצא. בדקו מול המורה." : "שגיאה בהצטרפות"); }
  };
  return (
    <div className="station">
      <header className="topbar"><div className="tb-title">עמדת מנוע תלת־פאזי</div><div className="tb-sub">עמדה 1</div></header>
      <div className="join">
        <div className="panel join-box">
          <div className="lead">הצטרפות לשיעור</div>
          <label className="field-label" htmlFor="code">קוד שיעור (6 ספרות)</label>
          <input id="code" className="join-code" dir="ltr" inputMode="numeric" maxLength={6} value={code}
                 onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))} />
          <label className="field-label" htmlFor="label">שם הקבוצה</label>
          <input id="label" className="join-input" maxLength={30} value={label} placeholder="למשל: קבוצה 3" onChange={(e) => setLabel(e.target.value)} />
          {roster.length > 0 && (
            <fieldset className="join-members">
              <legend className="field-label">מי בקבוצה? סמנו את השמות שלכם</legend>
              <div className="chips">
                {roster.map((r) => (
                  <button key={r.id} type="button" className={`chip-btn sm ${members.includes(r.id) ? "sel" : ""} ${r.taken && !members.includes(r.id) ? "taken" : ""}`}
                    aria-pressed={members.includes(r.id)} onClick={() => toggle(r.id)}>{r.name}</button>
                ))}
              </div>
              <div className="muted sm">שם מעומעם כבר סומן בקבוצה אחרת. אפשר לסמן אותו אם זו טעות.</div>
            </fieldset>
          )}
          <button className="primary big" disabled={code.length !== 6 || !label.trim() || (roster.length > 0 && !members.length)} onClick={go}>הצטרפו</button>
          {error && <div className="note warn">{error}</div>}
        </div>
      </div>
    </div>
  );
}

function Picker() {
  const [items, setItems] = useState<ExerciseItem[]>([]);
  useEffect(() => { api.exercises().then(setItems); }, []);
  const start = async (id: string) => {
    const s = await api.create(id);
    location.href = `/station/${s.id}`;
  };
  return (
    <div className="picker">
      <h1>תרגול בלי שיעור</h1>
      <p className="muted">בחרו תרגיל כדי לפתוח סשן עמדה.</p>
      <div className="picker-list">
        {items.map((e) => (
          <button key={e.id} className="picker-item" disabled={!e.available} onClick={() => start(e.id)}>
            <b>{e.number}</b>
            <span className={`chip ${e.status === "approved" ? "okc" : "draft"}`}>
              {e.status === "approved" ? "תוכן מאושר" : "תוכן טיוטה"}
            </span>
            {!e.available && <span className="muted">חסרה הקלטה</span>}
          </button>
        ))}
      </div>
    </div>
  );
}

createRoot(document.getElementById("root")!).render(<StrictMode><App /></StrictMode>);
