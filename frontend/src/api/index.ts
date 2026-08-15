export interface SearchRequest {
  series_url: string | null
  isbns: string | null
}

export interface SearchResponse {
  task_id: string | null
  html: string | null
  cached: boolean
  failed?: boolean
}

export interface TaskStatus {
  status: string
  total_series: number
  current_series: number
  current_url: string
  error: string | null
  total_books: number
  aa_current: number
  aa_total: number
}

export interface TaskResult {
  html: string | null
  error: string | null
  status: string | null
  total_books: number
  display_name: string
}

export interface HistoryEntry {
  task_id: string
  display_name: string
  status: string
  total_books: number
  created_at: string
}

const BASE = "/api"

let _token = ""

export function setToken(t: string): void {
  _token = t
}

export function getToken(): string {
  return _token
}

function headers(extra?: Record<string, string>): Record<string, string> {
  const h: Record<string, string> = { ...extra }
  if (_token) {
    h["X-Token"] = _token
  }
  return h
}

export async function createSearch(data: SearchRequest): Promise<SearchResponse> {
  const res = await fetch(`${BASE}/search`, {
    method: "POST",
    headers: headers({ "Content-Type": "application/json" }),
    body: JSON.stringify(data),
    cache: "no-store",
  })
  return res.json()
}

export async function getTaskStatus(taskId: string): Promise<TaskStatus> {
  const res = await fetch(`${BASE}/task/${taskId}`, { headers: headers(), cache: "no-store" })
  return res.json()
}

export async function getTaskResult(taskId: string): Promise<TaskResult> {
  const res = await fetch(`${BASE}/result/${taskId}`, { headers: headers(), cache: "no-store" })
  return res.json()
}

export async function getHistory(): Promise<HistoryEntry[]> {
  const res = await fetch(`${BASE}/history`, { headers: headers(), cache: "no-store" })
  return res.json()
}

export async function clearHistory(): Promise<{ cleared: number }> {
  const res = await fetch(`${BASE}/history`, { method: "DELETE", headers: headers(), cache: "no-store" })
  return res.json()
}
