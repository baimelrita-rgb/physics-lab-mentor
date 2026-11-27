# מנטור מעבדה לפיזיקה

מערכת הדרכה למעבדת פיזיקה: מנטור AI שמלווה תלמידים בעמדת ניסוי (עמדה 1: מנוע תלת־פאזי עם וסת תדר), ומסך מורה לשיעור חי.
המאגר מרכז את מסמכי האפיון והעיצוב שהופקו לפרויקט. עדיין אין בו קוד.

## גרסה ראשונה (שלב 1)

מה עובד: מסך התלמיד לתרגיל EX-01 מקצה לקצה על ההקלטות הסינתטיות. השלבים: רקע ושאלת הבנה, תחזית, צפייה עד נקודת העצירה, השערה, איסוף ראיות מהגרף, נימוק עם אבחון, בדיקה חוזרת ושאלת יציאה. התרגילים EX-02 עד EX-04 נטענים, אבל התוכן שלהם עדיין טיוטה. עוד אין מסך מורה ואין LLM: הרמזים וההודעות הם טקסטים קבועים ומאושרים.

| תיקייה | תוכן |
|---|---|
| `apps/api/` | שרת Python (FastAPI): ייבוא נתונים, מכונת המצבים, שער הזמן, מנוע האבחון, API |
| `apps/web/` | מסך העמדה (React) |
| `content/` | תוכן התרגילים, קטלוג הערוצים, ומפתח התשובות (`answer_key.yaml`, לשרת בלבד) |

### הרצה מקומית

```bash
pip install fastapi uvicorn pyyaml pytest httpx
cd apps/web && npm install && npm run build && cd ../..
cd apps/api && python3 -m uvicorn lab.app:app --port 8000
```

אחר כך פותחים את http://localhost:8000 ובוחרים תרגיל. כדי שההקלטה תתנגן מהר יותר בהדגמה, מריצים את השרת עם `REPLAY_SPEED=4`. בדיקות: `cd apps/api && python3 -m pytest`.

## מסמכים

| מסמך | קובץ |
|---|---|
| PRD וארכיטקטורה (מסמך הבסיס) | [docs/01-prd/00-prd-and-architecture.md](docs/01-prd/00-prd-and-architecture.md) |
| מוח 1 · ידע וסילבוס | [docs/01-prd/01-brain1-knowledge-syllabus.md](docs/01-prd/01-brain1-knowledge-syllabus.md) |
| מוח 2 · פרופיל עמדה | [docs/01-prd/02-brain2-station-profile.md](docs/01-prd/02-brain2-station-profile.md) |
| מוח 3 · נתונים, תרחישים וספריות | [docs/01-prd/03-brain3-data-exercises.md](docs/01-prd/03-brain3-data-exercises.md) |
| לקחים ממערכות דומות | [docs/01-prd/04-lessons-from-similar-systems.md](docs/01-prd/04-lessons-from-similar-systems.md) |
| מסמך ארכיטקטורה טכנית | [docs/02-technical-architecture.md](docs/02-technical-architecture.md) |
| מסמך UI ו־UX | [docs/03-ui-ux.md](docs/03-ui-ux.md) |
| תכנית פיתוח ודיזיין טכני | [docs/04-dev-plan-technical-design.md](docs/04-dev-plan-technical-design.md) |

## עיצוב מסכים

תיקיית [design/](design/) מכילה את קובצי המקור של עיצוב המסכים:

- `Main.dc.html` · מסך תלמיד בעמדה (10 אינץ׳, 1280×800)
- `Teacher.dc.html` · מסך מורה, שיעור חי
- `canvas.json` · פריסת הקנבס

הקבצים בפורמט של כלי העיצוב (`x-dc`) ונטענים יחד עם סקריפט התמיכה שלו, ולכן אינם מוצגים כראוי כדף HTML רגיל.

## מסמכי מקור ונתונים

מסמכי המקור שעליהם נבנו מסמכי האפיון, בפורמט המקורי (Word), בתיקיית [source-docs/](source-docs/):

| קובץ | תוכן |
|---|---|
| `TLM_Motor_Mentor_Three_Brains_HE.docx` | מסמך העברה: עמדת המנוע ושלושת המוחות של המנטור |
| `TLM_Rita_01_Station.docx` | תיק עמדה: עמדת המרת אנרגיה |
| `TLM_Rita_02_Healthy.docx` | מאגר הנתונים: שלוש הרצות מדומות תקינות (120 רשומות) |
| `TLM_Rita_03_Errors.docx` | מפתח למורה: ארבע הרצות סינתטיות עם אירועים (160 דגימות) |
| `TLM_Rita_04_Lesson.docx` | מערך שיעור: המרת אנרגיה בעמדת מנוע תלת־פאזי עם וסת תדר |

נתונים סינתטיים בתיקיית [data/](data/):

- `TLM_Rita_Labeled_Errors.csv` · 160 דגימות בהרצות E01–E04, עם תיוג אירועים

## הערות

- המסמכים יוצאו ל־Markdown ממסמכי Claude Docs. תרשימים מוטמעים לא עברו ומסומנים במקומם בהערה `[embedded content: …]` או `[תוכן מוטמע: …]`.
- בתכנית הפיתוח שני סעיפים עדיין בהכנה: תלויות ונתיב קריטי, וסיכונים / DoD / RACI.
- קובץ ה־CSV של ההרצות התקינות (Normal, הרצות N01–N03) עדיין אינו במאגר.
