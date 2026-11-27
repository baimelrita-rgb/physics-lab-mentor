# מנטור מעבדה לפיזיקה

מערכת הדרכה למעבדת פיזיקה: מנטור AI שמלווה תלמידים בעמדת ניסוי (עמדה 1: מנוע תלת־פאזי עם וסת תדר), ומסך מורה לשיעור חי.
המאגר מרכז את מסמכי האפיון והעיצוב שהופקו לפרויקט. עדיין אין בו קוד.

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

## הערות

- המסמכים יוצאו ל־Markdown ממסמכי Claude Docs. תרשימים מוטמעים לא עברו ומסומנים במקומם בהערה `[embedded content: …]` או `[תוכן מוטמע: …]`.
- בתכנית הפיתוח שני סעיפים עדיין בהכנה: תלויות ונתיב קריטי, וסיכונים / DoD / RACI.
- קובצי ה־CSV של ההקלטות הסינתטיות (Normal, Labeled_Errors) שמוזכרים במוח 3 אינם במאגר.
