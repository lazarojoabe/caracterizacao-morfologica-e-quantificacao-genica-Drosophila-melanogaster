import type { Config, Job, Result, Session } from "./types";

const API = import.meta.env.VITE_API_URL ?? "http://localhost:8000/api";
async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API}${url}`, init);
  if (!response.ok) { const body = await response.json().catch(() => ({})); throw new Error(body.detail?.message ?? body.detail ?? `Erro HTTP ${response.status}`); }
  return response.json() as Promise<T>;
}
export function createSession(nucleus: File, protein: File | null, config: Config): Promise<Session> {
  const form = new FormData(); form.append("nucleus_file", nucleus); if (protein) form.append("protein_file", protein); form.append("config_json", JSON.stringify(config));
  return request<Session>("/sessions", { method: "POST", body: form });
}
export const getResult = (id: string) => request<Result>(`/sessions/${id}/result`);
export const getJob = (id: string) => request<Job>(`/jobs/${id}`);
export function edit(id: string, payload: Record<string, unknown>) { return request<Result>(`/sessions/${id}/edits`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) }); }
export function undo(id: string, revision: number) { return request<Result>(`/sessions/${id}/undo`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ base_revision: revision }) }); }
export function redo(id: string, revision: number) { return request<Result>(`/sessions/${id}/redo`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ base_revision: revision }) }); }
export function reprocess(id: string, revision: number, config: Config) { return request<Job>(`/sessions/${id}/reprocess`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ base_revision: revision, config }) }); }
export function imageUrl(id: string, kind: "nucleus" | "protein" | "mask") { return `${API}/sessions/${id}/images/${kind}.png`; }
export function exportUrl(id: string, format: "csv" | "json") { return `${API}/sessions/${id}/export.${format}`; }
export function subscribeJob(id: string, onJob: (job: Job) => void, onDone: () => void) { const source = new EventSource(`${API}/sessions/${id}/events`); source.addEventListener("job", (event) => { const job = JSON.parse((event as MessageEvent).data) as Job; onJob(job); if (["completed", "error"].includes(job.status)) { source.close(); onDone(); } }); source.onerror = () => source.close(); return () => source.close(); }
