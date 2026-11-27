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
  recording: { alias: string; origin: string };
  visible_t: number;
  groups: { id: string; title: string; channels: { key: string; name: string; unit: string; open: boolean }[] }[];
  series: Record<string, { name: string; unit: string; points: Point[] }>;
  readings: Reading[];
  hints: { used: number; quota: number; given: string[] };
  mentor: string;
  feedback: { outcome: string; message: string; passed: boolean } | null;
  theory_answer: { choice: number; correct: boolean } | null;
  prediction: { directions: Record<string, string>; text: string } | null;
  hypothesis: string | null;
  exit_answer: string | null;
};
export type ExerciseItem = { id: string; title: string; subtitle: string; status: string; available: boolean };

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
  create: (exercise_id: string) => call<View>("POST", "/sessions", { exercise_id }),
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
  reason: (id: string, text: string, cited: string[]) => call<View>("POST", `/sessions/${id}/reason`, { text, cited }),
  exit: (id: string, text: string) => call<View>("POST", `/sessions/${id}/exit`, { text }),
};
