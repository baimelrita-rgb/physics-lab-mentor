export type Point = { t: number; value: number | null; quality: string; age_s: number };
export type Reading = {
  id: string; channel: string; t: number; value: number | null; unit: string;
  quality: string; age_s: number; name: string;
};
export type View = {
  id: string; state: string; state_rev: number; paused: boolean; step: number; steps: string[];
  exercise: {
    id: string; number: string; goal: string; status: string; stop_s: number;
    duration: number; windows: Record<string, [number, number]>;
    cards: { id: string; title: string; body: string; formula?: string }[];
    check: { question: string; choices: string[]; highlight_card: string };
    predict_channels: { key: string; name: string }[];
    hypotheses: { code: string; label: string }[];
  };
  recording: { alias: string; origin: string; runs: { from: number; label: string }[] };
  visible_t: number;
  groups: { id: string; title: string; channels: { key: string; name: string; unit: string; open: boolean }[] }[];
  series: Record<string, { name: string; unit: string; points: Point[] }>;
  readings: Reading[];
  hints: { used: number; quota: number; given: string[]; sources: string[] };
  note_from_teacher: string | null;
  mentor_reply: { text: string; chips: string[] } | null;
  can_ask: boolean;
  label: string;
  mentor: string;
  feedback: { outcome: string; message: string; passed: boolean } | null;
  theory_answer: { choice: number; correct: boolean } | null;
  prediction: { directions: Record<string, string>; text: string } | null;
  hypothesis: string | null;
  exit_answer: string | null;
};
export type ExerciseItem = { id: string; number: string; status: string; available: boolean };
export type TeacherExercise = ExerciseItem & { title: string; subtitle: string };
export type LessonSettings = {
  exercise_id: string; class_name: string; date: string; stations: number;
  hint_quota: number; allow_ask: boolean; deduction: "none" | "per_hint"; planned: boolean; setup_ack: boolean;
};
export type LessonItem = {
  id: string; code: string; exercise_id: string; number: string; title: string; joined: number; stations: number;
  class_name: string; date: string; planned: boolean; closed: boolean;
};
export type PrepStation = { id: string; name: string; mode: string; status: string; components: string[]; usable: boolean; reason?: string };
export type Preview = {
  id: string; number: string; title: string; subtitle: string; status: string;
  student: { goal: string; cards: string[]; check: string; predict: string; observe: string; stop_s: number;
    hypotheses: string[]; channels: string[]; hints: string[]; recheck: string | null; exit: string };
  key: { check_answer: string; cause: string; evidence: string[]; conclusion: string };
  timeline: { duration: number; stop_s: number; windows: Record<string, [number, number]>; runs: number };
  setup: {
    mode: string; note: string; point: string;
    components: SetupComponent[];
    expect: { channel: string; name: string; unit: string; value: number }[];
    scenario: { t: [number, number]; component: string; component_name: string; how: "physical" | "software"; action: string; note?: string }[];
    live: { ok: boolean; note: string };
    envelope: { id: string; title: string; status: string; level: "ok" | "warn" | "stop"; value: number | null; limit: number | null }[];
  };
};
export type ContentItem = { id: string; number: string; title: string; subtitle: string; status: string; errors: number; edited: boolean };
export type ContentField = { path: string; label: string; kind: "text" | "list" | "index"; audience: "student" | "teacher";
  source: string; value: unknown; changed: boolean };
export type ContentDoc = {
  id: string; number: number; status: string; base_status: string; approved_by: string | null; approved_at: string | null;
  fields: ContentField[]; errors: { path: string; message: string }[];
  fixed: { recording: string; stop_s: number; cause: string; evidence: string[] };
  history: { exercise: string; at: string; by: string; field: string }[];
};
export type RosterStudent = { id: string; name: string; active: boolean };
export type Mis = { id: string; label: string };
export type StudentsOverview = {
  class_name: string; aspects: string[]; sessions: number; unassigned_sessions: number;
  students: { id: string; name: string; active: boolean; lessons: number; aspects: (number | null)[]; finished: number;
    hints: number | null; misconceptions: Mis[]; trend: (number | null)[]; last: string | null }[];
};
export type StudentDetail = {
  student: RosterStudent; aspects: string[]; averages: (number | null)[];
  sessions: { lesson: string; session: string; date: string; number: number; title: string; group: string; partners: string[];
    stage: string; finished: boolean; scores: (number | null)[]; confirmed: boolean; total: number; hints: number;
    misconceptions: Mis[]; teacher_note: string }[];
  mastery: { id: string; title: string; value: number | null; sessions: number }[];
};
export type ClassData = {
  class_name: string; days: number | null; threshold_s: number; aspects: string[];
  lessons: { id: string; date: string; exercise: string; number: number; groups: number }[];
  heatmap: { label: string; sessions: number; finished: number; aspects: (number | null)[]; hints: number | null; confirmed: number }[];
  misconceptions: { id: string; label: string; groups: number; group_names: string[]; sessions: number;
    trend: { lesson: string; date: string; share: number | null }[]; direction: "up" | "down" | "flat" | null }[];
  stages: { state: string; label: string; sessions: number; median_s: number | null; max_s: number | null; stuck: number; hints: number }[];
  mastery: { id: string; title: string; class: number | null; sessions: number; groups: Record<string, number | null> }[];
};
export type SetupItem = { param: string; value: string | number; unit?: string; note?: string; status?: string; channel?: string; tolerance?: number };
export type SetupComponent = { id: string; name: string; model: string; needed: boolean; channels: string[]; settings: SetupItem[] };

export type Alert = { kind: string; title: string; text: string; suggest: string; station?: string; session?: string };
export type Card = {
  id: string; label: string; members: string[]; member_names?: string[]; index: number; state: string; stage: string; step: number;
  seconds_in_state: number; paused: boolean; hypothesis: string | null; hypothesis_label: string | null;
  hints_used: number; quota: number; flag: string | null; urgency: number; alerts: Alert[];
  rubric: (number | null)[]; total: number; confirmed: boolean;
};
export type Live = {
  lesson: { id: string; code: string; exercise_id: string; title: string; subtitle: string; status: string; stop_s: number; elapsed: number };
  cards: Card[]; alerts: Alert[]; rubric_aspects: string[];
  misconceptions: { id: string; label: string; count: number }[]; steps: string[];
};
export type Detail = {
  id: string; label: string; state: string; stage: string;
  members: string[]; roster: { id: string; name: string }[];
  expected: { cause: string; cause_label: string; conclusion: string };
  prediction: { directions: Record<string, string>; text: string } | null;
  theory_answer: { choice: number; correct: boolean } | null;
  hypothesis_label: string | null; readings: Reading[];
  attempts: { text: string; outcome: string; message: string; passed: boolean; misconception: string | null; missing: string[] }[];
  exit_answer: string | null; rubric: (number | null)[]; rubric_aspects: string[];
  asks: { q: string; a: string; intent: string; source: string; state: string }[];
  confirmed_scores: number[] | null; teacher_note: string;
  hints: { level: number; text: string; by: string }[];
  timeline: { t: number; state: string; type: string; [k: string]: unknown }[];
};

export class ApiError extends Error {}

async function call<T>(method: string, path: string, body?: unknown): Promise<T> {
  const res = await fetch(`/api${path}`, {
    method,
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  if (res.status === 401 && path.startsWith("/teacher")) {
    location.href = `/teacher/login?next=${encodeURIComponent(location.pathname)}`;
    return new Promise<T>(() => {});   // the page is leaving; keep callers waiting instead of erroring
  }
  if (!res.ok) {
    const j = await res.json().catch(() => ({}));
    throw new ApiError(j?.detail?.detail ?? j?.detail ?? res.statusText);
  }
  return res.json();
}

export const api = {
  exercises: () => call<ExerciseItem[]>("GET", "/exercises"),
  create: (exercise_id: string, label = "עמדה 1") => call<View>("POST", "/sessions", { exercise_id, label }),
  join: (code: string, label: string, members: string[] = []) => call<View>("POST", "/join", { code, label, members }),
  joinInfo: (code: string) => call<{ class_name: string; roster: { id: string; name: string; taken: boolean }[] }>("GET", `/join/${code}`),
  get: (id: string) => call<View>("GET", `/sessions/${id}`),
  advance: (id: string) => call<View>("POST", `/sessions/${id}/advance`),
  theory: (id: string, choice: number) => call<View>("POST", `/sessions/${id}/theory`, { choice }),
  predict: (id: string, directions: Record<string, string>, text: string) =>
    call<View>("POST", `/sessions/${id}/prediction`, { directions, text }),
  hypothesis: (id: string, code: string) => call<View>("POST", `/sessions/${id}/hypothesis`, { code }),
  open: (id: string, key: string, expectation: string) =>
    call<View>("POST", `/sessions/${id}/channels/${key}/open`, { expectation }),
  close: (id: string, key: string) => call<View>("POST", `/sessions/${id}/channels/${key}/close`),
  reading: (id: string, channel: string, t: number) => call<View>("POST", `/sessions/${id}/readings`, { channel, t }),
  removeReading: (id: string, rid: string) => call<View>("DELETE", `/sessions/${id}/readings/${rid}`),
  hint: (id: string) => call<View>("POST", `/sessions/${id}/hints`),
  ask: (id: string, text: string) => call<View>("POST", `/sessions/${id}/ask`, { text }),
  status: () => call<{ llm: boolean; llm_configured: boolean; model_phrase: string }>("GET", "/status"),
  reason: (id: string, text: string, cited: string[]) => call<View>("POST", `/sessions/${id}/reason`, { text, cited }),
  exit: (id: string, text: string) => call<View>("POST", `/sessions/${id}/exit`, { text }),
};

export type Me = { user: string; name: string; demo: boolean };
export const authApi = {
  me: () => call<Me>("GET", "/auth/me"),
  login: (username: string, password: string) => call<{ user: string; name: string }>("POST", "/auth/login", { username, password }),
  logout: () => call<{ ok: boolean }>("POST", "/auth/logout"),
};

export const teacherApi = {
  exercises: () => call<TeacherExercise[]>("GET", "/teacher/exercises"),
  createLesson: (body: Partial<LessonSettings> & { exercise_id: string }) => call<Live>("POST", "/teacher/lessons", body),
  lessons: () => call<LessonItem[]>("GET", "/teacher/lessons"),
  openLesson: (lid: string) => call<Live>("POST", `/teacher/lessons/${lid}/open`),
  contentList: () => call<ContentItem[]>("GET", "/teacher/content"),
  content: (id: string) => call<ContentDoc>("GET", `/teacher/content/${id}`),
  contentSave: (id: string, changes: Record<string, unknown>) =>
    call<{ saved: boolean; changed: string[]; errors: { path: string; message: string }[]; exercise: ContentDoc }>("PUT", `/teacher/content/${id}`, { changes }),
  contentAction: (id: string, action: "approve" | "revert") => call<ContentDoc>("POST", `/teacher/content/${id}/${action}`),
  roster: (class_name: string) => call<RosterStudent[]>("GET", `/teacher/roster?class_name=${encodeURIComponent(class_name)}`),
  rosterAdd: (class_name: string, names: string[]) => call<RosterStudent[]>("POST", "/teacher/roster", { class_name, names }),
  rosterEdit: (id: string, class_name: string, patch: { name?: string; active?: boolean }) =>
    call<RosterStudent>("PATCH", `/teacher/roster/${id}`, { class_name, ...patch }),
  setMembers: (sid: string, members: string[]) => call<{ members: string[] }>("POST", `/teacher/sessions/${sid}/members`, { members }),
  students: (class_name: string) => call<StudentsOverview>("GET", `/teacher/students?class_name=${encodeURIComponent(class_name)}`),
  student: (id: string, class_name: string) =>
    call<StudentDetail>("GET", `/teacher/students/${id}?class_name=${encodeURIComponent(class_name)}`),
  classes: () => call<{ name: string; lessons: number }[]>("GET", "/teacher/classes"),
  classView: (name: string, days: number | null) =>
    call<ClassData>("GET", `/teacher/class?name=${encodeURIComponent(name)}${days ? `&days=${days}` : ""}`),
  prepStations: () => call<PrepStation[]>("GET", "/teacher/prep/stations"),
  preview: (id: string) => call<Preview>("GET", `/teacher/prep/${id}`),
  live: (lid: string) => call<Live>("GET", `/teacher/lessons/${lid}`),
  lessonAction: (lid: string, action: "pause" | "resume" | "close") => call<Live>("POST", `/teacher/lessons/${lid}/${action}`),
  detail: (sid: string) => call<Detail>("GET", `/teacher/sessions/${sid}`),
  scores: (sid: string, scores: number[], note: string) => call<Detail>("POST", `/teacher/sessions/${sid}/scores`, { scores, note }),
  action: (sid: string, action: "pause" | "resume" | "hint" | "message", text?: string) =>
    call<Detail>("POST", `/teacher/sessions/${sid}/${action}`, text !== undefined ? { text } : undefined),
};
