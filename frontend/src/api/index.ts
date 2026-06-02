export interface SearchRequest {
  series_url: string | null
  isbns: string | null
}

export interface SearchResponse {
  task_id: string | null
  html: string | null
  cached: boolean
}

export interface TaskStatus {
  status: string
  total_series: number
  current_series: number
  current_url: string
  error: string | null
  total_books: number
}

export interface TaskResult {
  html: string | null
  error: string | null
  status: string | null
  total_books: number
}

export interface HistoryEntry {
  task_id: string
  display_name: string
  status: string
  total_books: number
  created_at: string
}

const BASE = "/api"

export async function createSearch(data: SearchRequest): Promise<SearchResponse> {
  const res = await fetch(`${BASE}/search`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  })
  return res.json()
}

export async function getTaskStatus(taskId: string): Promise<TaskStatus> {
  const res = await fetch(`${BASE}/task/${taskId}`)
  return res.json()
}

export async function getTaskResult(taskId: string): Promise<TaskResult> {
  const res = await fetch(`${BASE}/result/${taskId}`)
  return res.json()
}

export async function getHistory(): Promise<HistoryEntry[]> {
  const res = await fetch(`${BASE}/history`)
  return res.json()
}

export async function clearHistory(): Promise<{ cleared: number }> {
  const res = await fetch(`${BASE}/history`, { method: "DELETE" })
  return res.json()
}
