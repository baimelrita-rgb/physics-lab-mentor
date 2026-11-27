import { StrictMode, useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import { api, type ExerciseItem } from "./api";
import { Station } from "./Station";
import "./styles.css";

// Routes: "/" = exercise picker (for the demo), "/station/<session id>" = student screen.
function App() {
  const m = location.pathname.match(/^\/station\/(\w+)/);
  if (m) return <Station id={m[1]} />;
  return <Picker />;
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
      <h1>מנטור מעבדה · עמדה 1</h1>
      <p className="muted">בחרו תרגיל כדי לפתוח סשן עמדה. גרסת הדגמה על נתונים סינתטיים.</p>
      <div className="picker-list">
        {items.map((e) => (
          <button key={e.id} className="picker-item" disabled={!e.available} onClick={() => start(e.id)}>
            <b>{e.id} · {e.title}</b>
            <span>{e.subtitle}</span>
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
