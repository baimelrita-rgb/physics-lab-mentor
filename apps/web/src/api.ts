export type Point = { t: number; value: number | null; quality: string; age_s: number };
export type Reading = {
  id: string; channel: string; t: number; value: number | null; unit: string;
  quality: string; age_s: number; name: string;
};
export type View = {
  id: string; state: string; state_rev: number; paused: boolean; step: number; steps: string[];
  exercise: {
    id: string; title: string; subtitle: string; goal: string; status: string; stop_s: number;
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
export type ExerciseItem = { id: string; title: string; subtitle: string; status: string; available: boolean };

export type Alert = { kind: string; title: string; text: string; suggest: string; station?: string; session?: string };
export type Card = {
  id: string; label: string; index: number; state: string; stage: string; step: number;
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
  if (!res.ok) {
    const j = await res.json().catch(() => ({}));
    throw new ApiError(j?.detail?.detail ?? j?.detail ?? res.statusText);
  }
  return res.json();
}

export const api = {
  exercises: () => call<ExerciseItem[]>("GET", "/exercises"),
  create: (exercise_id: string, label = "עמדה 1") => call<View>("POST", "/sessions", { exercise_id, label }),
  join: (code: string, label: string) => call<View>("POST", "/join", { code, label }),
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

export const teacherApi = {
  createLesson: (exercise_id: string) => call<Live>("POST", "/teacher/lessons", { exercise_id }),
  live: (lid: string) => call<Live>("GET", `/teacher/lessons/${lid}`),
  lessonAction: (lid: string, action: "pause" | "resume" | "close") => call<Live>("POST", `/teacher/lessons/${lid}/${action}`),
  detail: (sid: string) => call<Detail>("GET", `/teacher/sessions/${sid}`),
  scores: (sid: string, scores: number[], note: string) => call<Detail>("POST", `/teacher/sessions/${sid}/scores`, { scores, note }),
  action: (sid: string, action: "pause" | "resume" | "hint" | "message", text?: string) =>
    call<Detail>("POST", `/teacher/sessions/${sid}/${action}`, text !== undefined ? { text } : undefined),
};
