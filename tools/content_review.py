"""Write docs/05-content-review.md: the exercise content as the student sees it, for teacher review.

Run from the repository root after editing content/exercises.yaml:
    python3 tools/content_review.py
"""
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
ex_all = yaml.safe_load((ROOT / "content" / "exercises.yaml").read_text(encoding="utf-8"))
chan = {c["key"]: c["name"] for g in yaml.safe_load((ROOT / "content" / "channels.yaml").read_text(encoding="utf-8"))["groups"]
        for c in g["channels"]}
hyp = ex_all["hypotheses"]

lines = [
    "# סקירת תוכן התרגילים",
    "",
    "הקובץ נוצר אוטומטית מתוך `content/exercises.yaml` ומציג את מה שהתלמיד רואה בכל תרגיל.",
    "לתיקון: כתבו את השינוי במילים, או ערכו את `content/exercises.yaml` והריצו `python3 tools/content_review.py`.",
    "",
    "**מקרא סטטוס:** ✅ מאושר (מתסריט השיעור) · ✏️ טיוטה, ממתין לאישור מורה.",
    "",
]
for eid, e in ex_all["exercises"].items():
    status = "✅ מאושר" if e["status"] == "approved" else "✏️ טיוטה"
    lines += [
        f"## {eid} · {e['title']}: {e['subtitle']} ({status})",
        "",
        "| חלק | מה התלמיד רואה |",
        "|---|---|",
        f"| מטרה | {e['goal']} |",
        f"| הקלטה ונקודת עצירה | הקלטה {e['recording']}, עצירה בשנייה {e['stop_s']} |",
        f"| כרטיסי ידע | {', '.join(e['cards'])} |",
        f"| שאלת הבנה | {e['check']['question']} |",
        f"| תשובות לבחירה | {' / '.join(e['check']['choices'])} |",
        f"| הנחיית תחזית | {e['predict']['prompt']} |",
        f"| ערוצים בתחזית | {', '.join(chan[c] for c in e['predict']['channels'])} |",
        f"| הנחיית צפייה | {e['observe_prompt']} |",
        f"| ערוצים פתוחים בהתחלה | {', '.join(chan[c] for c in e['initial_channels'])} |",
        f"| ערוצים שאפשר לפתוח | {', '.join(chan[c] for c in e['openable_channels'])} |",
        f"| השערות לבחירה | {' / '.join(hyp[h] for h in e['hypothesis_options'])} |",
        f"| רמז 1 | {e['hints'][0]} |",
        f"| רמז 2 | {e['hints'][1]} |",
        f"| רמז 3 | {e['hints'][2]} |",
        f"| הנחיית בדיקה חוזרת | {e['recheck_prompt']} |",
        f"| שאלת יציאה | {e['exit_question']} |",
        "",
    ]
(ROOT / "docs" / "05-content-review.md").write_text("\n".join(lines), encoding="utf-8")
print("wrote docs/05-content-review.md")
