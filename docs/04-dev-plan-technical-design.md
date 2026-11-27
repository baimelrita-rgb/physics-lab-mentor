# מנטור מעבדה – תכנית פיתוח ודיזיין טכני

2026-11-27 · @Rita baimel

## 1. היקף, הנחות ובסיס ההערכה

המסמך מתרגם את ה־PRD ואת מסמך הארכיטקטורה למודולים, לחוזים ולתכנית ביצוע. הוא נכתב לצוות שיבנה את המערכת.

### היקף

- **בתוך ההיקף (MVP):** עמדת המנוע, שלושת התרגילים הראשונים, מסכי תלמיד ומורה, מצב חירום (offline), ושערי בטיחות.

- **שלב 2:** עמדות מתח נמוך ופוטו־וולטאי, סטודיו תוכן וקונפיגורציה, ואנליטיקה לבית הספר.

- **מחוץ להיקף:** שליטה מרחוק בעמדה (העמדה לקריאה בלבד), אפליקציית הורים וממשק לשפה האנגלית.

### הנחות צוות

| תפקיד                | היקף משרה | אחריות                                 |
|----------------------|-----------|----------------------------------------|
| Tech Lead / ארכיטקט  | 1.0       | חוזים, סקירות, CEL, ביצועים            |
| Backend              | 2.0       | שירותי ענן, מנוע אבחון, טיוטור         |
| Edge / Embedded      | 1.0       | סוכן ה־UNO Q, MQTT, OTA, עבודה מול תלם |
| Frontend             | 1.5       | PWA לעמדה, מסך המורה, ספריית הרכיבים   |
| QA / אוטומציה        | 1.0       | Golden replay, סימולטור, HIL           |
| DevOps / SRE         | 0.5       | Terraform, Kubernetes, ניטור           |
| מעצב/ת UX            | 0.5       | מסכים, כרטיסי הגדרה, בדיקות שמישות     |
| מומחה/ית תוכן פדגוגי | 0.5       | תרגילים, תפיסות שגויות, סולמות רמזים   |
| מנהל/ת מוצר          | 0.5       | עדיפויות, קשר עם תלם ובתי הספר         |

סה״כ כ־8.5 משרות.

### בסיס ההערכה

- כל משך זמן במסמך הוא **הערכה** לצוות בגודל הזה, בספרינטים של שבועיים.

- ההערכות מניחות שמפת הרגיסטרים של תלם והמרות היחידות יגיעו עד סוף שלב 0. איחור בהן מזיז את כל הנתיב הקריטי (ראו פרק 11).

- הערכים במעטפת הבטיחות מוצעים בלבד, עד לאישור תלם.

## 2. מבנה הריפו וגבולות מודולים

מונוריפו אחד. בדיקת תלויות בין מודולים נאכפת ב־CI (import-linter).

    talem-mentor/
      apps/
        api/                 # FastAPI modular monolith (נקודת כניסה אחת)
        worker/              # צרכני Redis Streams: ingest, analytics
        station-pwa/         # React + Vite, kiosk
        teacher-web/         # React, מסך מורה
      modules/               # מודולי דומיין, Python
        identity/ registry/ content/ session/ ingest/
        timegate/ orchestrator/ setup/ diagnosis/
        tutor/ envelope/ generator/ analytics/ realtime/
      edge/
        agent/               # Python agent על UNO Q
        mcu/                 # קושחת STM32 (Arduino) לקריאת חיישנים
        image/               # בניית אימג׳ A/B
      packages/
        schemas/             # JSON Schema + Pydantic + TS מגונרטים
        rules/               # קבצי CEL + בדיקות
        ui-kit/              # ספריית רכיבים + Storybook
      content/               # תרגילים, תפיסות, רמזים (YAML)
      tools/
        simulator/           # סימולטור עמדה + תלמידים מדומים
        replay/              # הרצת הקלטות golden
      infra/
        terraform/ helm/ argocd/
      docs/adr/

### כללי גבול

- כל מודול מחשיף `api.py` (פונקציות ציבוריות) ו־`events.py` (אירועים שהוא מפרסם). מודול אחר לא מייבא את הפנימיות שלו.

- רק `session` כותב למצב הסשן. `orchestrator` מחליט, `session` מממש.

- `tutor` הוא המודול היחיד שקורא ל־LLM. אין לו גישה ל־answer_key.

- `envelope` ו־`setup` רצים אותם קבצי CEL גם בקצה (דרך `packages/rules`), כדי שמצב חירום יתנהג בדיוק כמו הענן.

- סכמות נכתבות פעם אחת ב־`packages/schemas`, ומהן מגונרטים טיפוסים לפייתון ול־TypeScript.

## 3. מודל נתונים

PostgreSQL 16 עם TimescaleDB ו־pgvector. כל טבלה של משתמש נושאת `tenant_id` תחת RLS. הסכמה `answer_key` נגישה רק לתפקיד `svc_diagnosis`.

``` sql
-- tenancy
CREATE TABLE tenancy.school (id uuid PK, tenant_id uuid NOT NULL, name text, retention_days int DEFAULT 365);
CREATE TABLE tenancy.person (id uuid PK, tenant_id uuid, role text CHECK (role IN ('student','teacher','admin','engineer')),
  display_name text, pseudonym text UNIQUE);

-- config: סוגי עמדות, רכיבים, ערוצים
CREATE TABLE config.station_type (id text PK, version int, slots jsonb);
CREATE TABLE config.station (id uuid PK, tenant_id uuid, type_id text, device_cert_fp text, lab_id uuid);
CREATE TABLE config.channel (station_id uuid, key text, unit text, kind text CHECK (kind IN ('measured','derived','simulated')),
  register int, scale numeric, verified_at timestamptz, PRIMARY KEY (station_id, key));

-- content (מגורסה, בלתי ניתנת לשינוי אחרי אישור)
CREATE TABLE content.exercise (id text, version int, status text, body jsonb, approved_by uuid, PRIMARY KEY (id, version));
CREATE TABLE content.setup_template (id text, version int, steps jsonb, PRIMARY KEY (id, version));
CREATE TABLE content.misconception (id text PK, exercise_id text, body jsonb, embedding vector(1024));

-- scenario + answer_key
CREATE TABLE scenario.instance (id uuid PK, station_session_id uuid, exercise_id text, params jsonb, seed bigint);
CREATE TABLE answer_key.fact (scenario_id uuid PK, cause text, evidence jsonb, checks jsonb);

-- obs: hypertable
CREATE TABLE obs.sample (ts timestamptz NOT NULL, station_id uuid, seq bigint, key text, value double precision,
  quality smallint, PRIMARY KEY (station_id, key, ts));
SELECT create_hypertable('obs.sample','ts', chunk_time_interval => interval '1 day');
-- דחיסה אחרי 7 ימים, מחיקה לפי retention_days. continuous aggregate של 1s.

-- session
CREATE TABLE session.station_session (id uuid PK, tenant_id uuid, station_id uuid, lesson_id uuid,
  state text, state_rev int, opened_at timestamptz, closed_at timestamptz);
CREATE TABLE session.member (station_session_id uuid, person_id uuid, joined_at timestamptz, PRIMARY KEY (station_session_id, person_id));
CREATE TABLE session.gate (id uuid PK, station_session_id uuid, kind text, opened_at timestamptz,
  decided_by uuid, decision text, decided_at timestamptz, note text);
CREATE TABLE session.setup_step (station_session_id uuid, step_id text, status text, verified_at timestamptz,
  evidence jsonb, PRIMARY KEY (station_session_id, step_id));

-- learning_log: רק הוספה (append-only)
CREATE TABLE learning_log.event (id bigserial PK, station_session_id uuid, person_id uuid, ts timestamptz,
  type text, payload jsonb);
```

**הערות:**

- `state_rev` משמש לנעילה אופטימית במעברי מצב.

- `learning_log.event` נכתבת רק בהוספה. תפקיד השירות ללא UPDATE וללא DELETE, ומחיקה רק דרך משימת retention.

- שמות תלמידים לא נשלחים ל־LLM. רק `pseudonym`.

## 4. סכמת התקשורת וסוכן הקצה

### נושאי MQTT

| נושא                         | כיוון     | QoS         | תדירות                                |
|------------------------------|-----------|-------------|---------------------------------------|
| `tlm/{tenant}/{station}/obs` | קצה → ענן | 1           | 5 Hz עם אצוות של שנייה                |
| `.../status`                 | קצה → ענן | 1, retained | כל 10 ש׳ + LWT                        |
| `.../events`                 | קצה → ענן | 1           | לפי אירוע (חריגה, הגדרה אומתה מקומית) |
| `.../profile`                | ענן → קצה | 1, retained | כשמשתנה תרגיל או כללים                |
| `.../session`                | ענן → קצה | 1, retained | כשמשתנה מצב הסשן                      |

הנושא `profile` מעביר תוכן וכללים בלבד, לא פקודות. הסוכן מאמת חתימה (Ed25519) לפני טעינה. ה־ACL של הברוקר מגביל כל תעודת מכשיר לנושאים של העמדה שלו.

### מסגרת obs.v1

``` json
{
  "schema": "obs.v1",
  "station": "st_7f3a",
  "seq": 184223,
  "t0": "2026-11-27T09:14:02.000Z",
  "dt_ms": 200,
  "ch": {
    "output_frequency": {"v": [49.8, 49.9, 50.0, 50.0, 50.1], "q": [0,0,0,0,0]},
    "case_temp":        {"v": [41.2, 41.2, 41.3, 41.3, 41.3], "q": [0,0,0,0,0]}
  }
}
```

- `q`:  0 = ok,  1 = stale,  2 = missing,  3 = out_of_range_sensor.

- קליטה אידמפוטנטית לפי `(station, seq)`. פער בֿ`seq` מסומן ומושלם מהבאפר בחיבור מחדש.

- הסכמה קפואה לגרסה. שינוי שובר = obs.v2 במקביל.

### סוכן הקצה (Python על UNO Q)

| רכיב       | תפקיד                                                                          |
|------------|--------------------------------------------------------------------------------|
| `reader`   | קריאת ערוצים מה־MCU דרך RPC פנימי (בלי פקודות כתיבה), המרת יחידות לפי מפת תלם  |
| `buffer`   | SQLite עם 24 שעות, WAL, שליחה חוזרת בסדר seq                                   |
| `uplink`   | לקוח MQTT 5 עם mTLS, backoff מעריכי                                            |
| `local_ws` | שרת WebSocket מקומי ל־PWA, קריאות חיות ב־5 Hz                                  |
| `rules`    | מנוע CEL מקומי (cel-python) למעטפה ולאימות הגדרה במצב חירום                    |
| `ota`      | עדכון A/B עם חתימה, החלפה רק כשאין סשן פעיל, חזרה אוטומטית אם healthcheck נכשל |
| `watchdog` | systemd + health endpoint, אתחול מחדש של רכיבים קרוסים                         |

**קבלה לסוכן:** ניתוק רשת של 60 דקות ללא אובדן מסגרות. צריכת זיכרון יציבה לאורך 72 שעות. אפס קריאות של כתיבה ל־MCU (נבדק בסריקת קוד ובבדיקת HIL).

## 5. מכונת מצבים, כללי CEL, אימות הגדרה ושער זמן

### מכונת מצבים

`JOINED → THEORY → SETUP → PREDICT → OBSERVE → HYPOTHESIZE → EVIDENCE → REASON → RECHECK → EXIT → RESET → CLOSED`

| מעבר                  | תנאי (guard)                                          |
|-----------------------|-------------------------------------------------------|
| THEORY → SETUP        | תרגיל הבסיס עבר, או שהמורה שחרר                       |
| SETUP → PREDICT       | כל צעדי ההגדרה במצב `verified` וכל שערי הבטיחות אושרו |
| PREDICT → OBSERVE     | כל חבר קבוצה נתן תחזית                                |
| OBSERVE → HYPOTHESIZE | עבר זמן התצפית המינימלי (timegate)                    |
| EVIDENCE → REASON     | נשמרו לפחות N קריאות עם ערוצים שונים                  |
| RECHECK → EXIT        | הבדיקה החוזרת עברה, או מכסת ניסיונות נגמרה            |
| EXIT → RESET          | תשובת יציאה נשמרה                                     |
| RESET → CLOSED        | צעדי האיפוס אומתו (מצב בסיס)                          |
| \* → PAUSED           | המורה השהה, או עצירת בטיחות. חזרה למצב הקודם בלבד     |

מימוש: טבלת מעברים הצהרתית בפייתון. כל מעבר נכתב בטרנזקציה עם `state_rev`, רושם אירוע ב־outbox, ומפרסם ל־`session` ב־MQTT ול־WS.

### פורמט כלל CEL

``` yaml
id: ENV-MOT-FREQ-HI
version: 3
scope: envelope          # envelope | setup | diagnosis
station_type: motor_vfd
severity: safety_gate    # info | warn | stop | safety_gate
when: obs.output_frequency.p95_2s > params.freq_max
params: { freq_max: 50 } # מוצע, ממתין לאישור תלם
requires_quality: ok
message_key: envelope.freq_high
tests:
  - given: { output_frequency: [51,51,51] }  expect: fire
  - given: { output_frequency: [49,50,49] }  expect: quiet
```

הקבצים עוברים קומפילציה והרצת `tests` ב־CI. בענן משתמשים ב־cel-python, ובקצה באותה ספרייה ובאותה גרסת חבילה.

### אלגוריתם אימות הגדרה

    for step in template.steps (in order):
        show card(step); status = waiting
        if step.requires_deenergized and not deenergized(obs): status = blocked_power
        loop on each obs frame:
            if quality(step.channels) != ok: status = no_data; continue
            if eval(step.check, window=step.hold_s) is true for hold_s:
                status = verified; record evidence; break
            if eval(step.wrong_hint_rules) matches: show targeted hint
        if step.gate: open gate(kind=step.gate); wait for teacher decision

- `hold_s` (ברירת מחדל 2 ש׳) מונע אימות של ערך מקרי.

- צעד שכבר אומת חוזר למצב `waiting` אם התנאי שלו נשבר לפני המעבר ל־ PREDICT.

- צעד שלא ניתן לאמת מנתונים (למשל חיווט Δ/Y) מסומן `teacher_confirm` ועובר דרך שער.

### שער זמן (timegate)

מודול המחשב לכל מצב `min_dwell` (מהתוכן) ו־`max_dwell` (להתראת מורה). השעון הוא של הענן, והקצה משתמש בערכים האחרונים שקיבל במצב חירום.

## 6. מנוע אבחון, טיוטור ומאמת פלט

### מנוע אבחון (דטרמיניסטי)

קלט: תשובת התלמיד, הקריאות שציטט, המצב הנוכחי וה־answer_key. פלט: קוד אבחון מתוך רשימה סגורה.

1.  **סיווג התשובה:** ה־LLM מסווג שאלת תלמיד או הסבר חופשי לתוך `claim_type` ו־`misconception_id?` בפלט JSON מוגבל. עם ביטחון מתחת לסף, התוצאה היא `unclear`.

2.  **בדיקת ראיות:** הקריאות שצוטטו נבדקות מול `answer_key.fact.evidence` בכללי CEL.

3.  **החלטה:** טבלת החלטה (סוג טענה × תקינות ראיות × מצב) קובעת `move`: `probe`, `contrast`, `hint_level_n`, `confirm`, `redirect`, `safety`.

ה־LLM אף פעם לא קובע אם התלמיד צודק. זה תפקיד של שלב 2.

### טיוטור (ניסוח)

קלט ל־LLM מורכב רק מהפריטים הבאים:

``` json
{
  "move": "contrast",
  "state": "EVIDENCE",
  "exercise_id": "MOT-02",
  "allowed_facts": ["בקריאה ששמרתם תדר היציאה הוא 50 Hz"],
  "forbidden": ["cause", "answer_key.*"],
  "student_text": "המנוע מתחמם כי התדר גבוה",
  "style": {"max_sentences": 2, "end_with_question": true, "lang": "he"}
}
```

פלט מחייב (JSON Schema): `{"text": string, "refs": [reading_id], "chips": [string]}`.

### מאמת פלט (validator)

כל פלט עובר את הבדיקות הבאות לפני שהוא מוצג:

| בדיקה            | שיטה                                                               |
|------------------|--------------------------------------------------------------------|
| סכמה             | אימות JSON Schema                                                  |
| אורך וסיום בשאלה | ספירת משפטים, בדיקת תו סיום                                        |
| אין חשיפת תשובה  | התאמת מונחים מול `answer_key.cause` ושמותיה הנרדפים + דמיון וקטורי |
| מספרים קיימים    | כל מספר בטקסט חייב להופיע ב־`allowed_facts`                        |
| בטיחות           | אין הוראה לפעולה פיזית שלא מכרטיס הגדרה מאושר                      |

כשלון: ניסיון חוזר אחד עם הערת תיקון, ואז מעבר לתבנית סטטית מאושרת לאותו `move`. כל כשלון נרשם לניתוח.

### ספק LLM

שכבת adapter עם timeout של 1.8 ש׳, circuit breaker, וקאש לפי `(move, exercise, state, hash(facts))`. הפרומפטים מגורסים בריפו ועוברים את סט האדברסריאל ב־CI.

## 7. חוזי API

REST תחת `/v1`, מוגדר ב־OpenAPI שנוצר מהקוד ונבדק ב־CI מול סנפשוט. אימות ב־OIDC (מורים) ובטוקן סשן קצר מועד לעמדה (תלמידים).

| Endpoint                          | מי         | מה                                                            |
|-----------------------------------|------------|---------------------------------------------------------------|
| `POST /v1/lessons`                | מורה       | פתיחת שיעור, שיבוץ תרגילים לעמדות                             |
| `POST /v1/stations/{id}/sessions` | עמדה       | פתיחת סשן עמדה                                                |
| `POST /v1/sessions/{id}/members`  | תלמיד      | הצטרפות במספר תלמיד                                           |
| `GET /v1/sessions/{id}`           | עמדה, מורה | מצב, צעדי הגדרה, שערים פתוחים                                 |
| `POST /v1/sessions/{id}/turns`    | תלמיד      | תחזית, השערה, שאלה. מחזיר כרטיס מנטור. דורש `Idempotency-Key` |
| `POST /v1/sessions/{id}/readings` | תלמיד      | שמירת קריאה (מפנה לֿseq ולחלון זמן)                            |
| `POST /v1/sessions/{id}/hints`    | תלמיד      | בקשת רמז, כפוף למכסה                                          |
| `POST /v1/gates/{id}/decision`    | מורה       | אישור או דחייה עם הערה                                        |
| `POST /v1/sessions/{id}/pause`    | מורה       | השהיה / המשך                                                  |
| `GET /v1/lessons/{id}/report`     | מורה       | סיכום שיעור                                                   |
| `PUT /v1/content/exercises/{id}`  | כותב תוכן  | טיוטה חדשה (שלב 2)                                            |

### WebSocket

- **מקומי (קצה → PWA):** `ws://localhost:8765/live` עם מסגרות obs.v1 ואירועי אימות מקומיים.

- **ענן (שרת → מורה ועמדה):** `wss://.../v1/rt` עם ערוצים `lesson:{id}` ו־`session:{id}`.

``` json
{"type": "session.state", "session": "ss_1", "state": "SETUP", "rev": 14}
{"type": "gate.opened", "gate": "g_9", "kind": "repower", "session": "ss_1"}
{"type": "envelope.alert", "session": "ss_1", "rule": "ENV-MOT-TEMP-HI", "severity": "stop"}
```

לקוח שמתחבר מחדש שולח `since_rev` ומקבל את כל האירועים שחסרו לו.

**שגיאות:** RFC 9457 (`application/problem+json`) עם `code` קבוע, למשל `STATE_GUARD_FAILED` או `GATE_ALREADY_DECIDED`.

## 8. אבני דרך, אפיקים וספרינטים

כל המשכים הם הערכה, בהנחת הצוות מפרק 1. סה״כ עד פיילוט בבית ספר: כ־24 שבועות.

| שלב             | משך (הערכה)  | אפיקים                                                                                       | קריטריון יציאה                                            |
|-----------------|--------------|----------------------------------------------------------------------------------------------|-----------------------------------------------------------|
| 0\. תשתיות      | 4 שבועות     | מונוריפו ו־CI, סביבת dev בענן, סכמות, סוכן קצה שקורא ערוץ אחד, סימולטור עמדה                 | מסגרת obs.v1 מהעמדה מגיעה ל־Timescale ומוצגת ב־PWA        |
| 1\. ליבת המנטור | 8 שבועות     | מכונת מצבים, הגדרה מוכוונת, מעטפה, אבחון, טיוטור + מאמת, מסך מורה, שערי בטיחות, תרגיל MOT-01 | תרגיל מלא עובר מקצה לקצה על הסימולטור. golden replay ירוק |
| 2\. עמדה אמיתית | 6 שבועות     | מפת רגיסטרים מלאה, מצב חירום, OTA, MOT-02/03, HIL, קשיחות, אבטחת מידע                        | סבב שמישות 2 עבר, 0 אירועי בטיחות, סקירת אבטחה עברה       |
| 3\. פיילוט      | 6 שבועות     | קליטה של בית ספר אחד, ניטור SLO, תיקונים, דוח פדגוגי                                         | מדדי הצלחה של ה־PRD נמדדו על שיעורים אמיתיים              |
| 4\. הרחבה       | אחרי הפיילוט | עמדות מתח נמוך ופוטו־וולטאי, סטודיו, סקייל ל־300 עמדות                                       | יוגדר בסוף שלב 3                                          |

### פירוק ספרינטים (שלבים 0–1, ספרינט = שבועיים)

| ספרינט | מטרה          | תוצרים עיקריים                                                                    |
|--------|---------------|-----------------------------------------------------------------------------------|
| S1     | שלד עובד      | ריפו, CI, Terraform dev, ברוקר MQTT עם mTLS, `packages/schemas`                   |
| S2     | נתונים זורמים | סוכן קצה (reader, buffer, uplink), ingest, hypertable, סימולטור, PWA עם LiveGauge |
| S3     | סשן והגדרה    | מכונת מצבים, הצטרפות, מנוע CEL, מאמת הגדרה, SetupCard                             |
| S4     | בטיחות        | מעטפה, שערים, StopOverlay, מסך מורה (StationTile, GateBar), realtime              |
| S5     | המנטור        | אבחון, טיוטור, מאמת, רמזים, ReadingTray, תוכן MOT-01                              |
| S6     | מקצה לקצה     | timegate, דוח שיעור, golden replay, סט אדברסריאלי ראשון, עומס ראשוני              |

הערה: S1–S2 הם שלב 0, ו־S3–S6 הם שלב 1.

## 9. אסטרטגיית בדיקות

| שכבה           | מה נבדק                                                 | כלי                             | סף / תנאי מעבר                          |
|----------------|---------------------------------------------------------|---------------------------------|-----------------------------------------|
| יחידה          | מודולים, מכונת מצבים, המרות                             | pytest, Vitest                  | כיסוי 80% במודולי הליבה, 100% מעברי מצב |
| כללי CEL       | כל כלל עם מקרה fire ומקרה quiet                         | מריץ tests מתוך קבצי YAML       | 100% מהכללים, רץ גם בסביבת הקצה         |
| חוזים          | OpenAPI, obs.v1, אירועי WS                              | schemathesis, snapshot          | אין שינוי שובר ללא גרסה                 |
| Golden replay  | הקלטות סשן אמיתיות מורצות מחדש דרך המערכת               | `tools/replay`                  | אותם מעברי מצב, אותם קודי אבחון         |
| אדברסריאלי     | ניסיונות לחלץ תשובה, prompt injection, שאלות מחוץ לתחום | סט של 300+ פרומפטים בעברית      | 0 חשיפות תשובה. חוסם מיזוג              |
| תלמידים מדומים | פרסונות (מנחש, תקוע, מתחקמן) מול המנטור                 | LLM כתלמיד + בודק אנושי על מדגם | עמידה בהנחיות הסגנון ב־95%              |
| עומס           | 300 עמדות מדומות, שיעורים מקבילים                       | k6 + סימולטור MQTT              | תור מנטור p95 מתחת ל־3 ש׳, 9k ערכים/ש׳  |
| HIL            | סוכן על UNO Q אמיתי מול עמדת תלם                        | עמדת בדיקה ייעודית              | המרות נכונות, ניתוק 60 דק׳ ללא אובדן    |
| בטיחות         | כל כלל עצירה ושער, בענן ובמצב חירום                     | הזרקת ערכים בסימולטור + HIL     | 100%, אישור חתום על ידי תלם             |
| E2E UI         | תסריטי תלמיד ומורה                                      | Playwright                      | תסריטי הליבה ירוקים לפני כל שחרור       |
| כאוס           | נפילת LLM, ברוקר, DB                                    | תרגילי game day ב־staging       | מעבר למצב מופחת ללא אובדן מצב סשן       |

## 10. CI/CD וסביבות

### צנרת

1.  **PR:** lint, typecheck, import-linter, בדיקות יחידה, בדיקות CEL, בדיקת חוזים, סריקת סודות ותלויות (Trivy, gitleaks). עד 10 דקות.

2.  **Merge ל־main:** בניית אימג׳ים חתומים (cosign), golden replay, סט אדברסריאלי, Playwright. פריסה אוטומטית ל־dev.

3.  **קידום ל־staging:** תגית גרסה, Argo CD, בדיקת עומס לילית, HIL מול עמדת הבדיקה.

4.  **קידום ל־prod:** אישור ידני, פריסה מחוץ לשעות הלימודים, חזרה לאחור בלחיצה אחת.

### קצה

- אימג׳ חתום נבנה ב־CI ונפרס בטבעות: 1 עמדה (קנרית), 10%, ואז כולם.

- החלפה רק כשאין סשן פעיל, ועצירה אוטומטית של הפריסה אם יותר מ־2% מהעמדות חוזרות לאחור.

- קבצי תוכן וכללים מתעדכנים דרך `profile`, לא דרך OTA.

### סביבות

| סביבה   | נתונים                   | עמדות                             | LLM                              |
|---------|--------------------------|-----------------------------------|----------------------------------|
| local   | סינתטיים                 | סימולטור (docker compose)         | מוק או מפתח פיתוח                |
| dev     | סינתטיים                 | סימולטור                          | אמיתי, מכסה נמוכה                |
| staging | סינתטיים + הקלטות מותמות | עמדת בדיקה אמיתית + סימולטור עומס | אמיתי                            |
| prod    | אמיתיים, אזור ישראל      | עמדות בתי ספר                     | אמיתי, ללא שמירת נתונים אצל הספק |

נתוני prod לא עוברים לסביבות נמוכות. הקלטות golden עוברות התממה (pseudonym בלבד, הסרת טקסט חופשי מזהה).

*\[בהכנה: Dependencies & critical path\]*

*\[בהכנה: Risks, DoD, RACI\]*
