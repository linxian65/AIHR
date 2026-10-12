import type { SessionMeta, ScenarioInfo } from '../stores/sessionStore'

export interface HistoryTurn {
  turn_index: number
  user_content: string
  events: Array<{ event: string; data: any }>
  status: string
  cost_usd: number | null
  created_at: string
}

export async function listSessions(): Promise<SessionMeta[]> {
  const res = await fetch('/api/sessions')
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  const data = await res.json()
  return data.sessions ?? []
}

export async function listScenarios(): Promise<ScenarioInfo[]> {
  const res = await fetch('/api/sessions/scenarios')
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  const data = await res.json()
  return data.scenarios ?? []
}

export async function createSession(
  session_id: string,
  title?: string,
  scenario?: string,
): Promise<SessionMeta> {
  const res = await fetch('/api/sessions', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id, title, scenario }),
  })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

export async function patchSession(
  id: string,
  patch: { title?: string; scenario?: string },
): Promise<SessionMeta> {
  const res = await fetch(`/api/sessions/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(patch),
  })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

export async function renameSession(id: string, title: string): Promise<SessionMeta> {
  return patchSession(id, { title })
}

export async function deleteSession(id: string): Promise<void> {
  const res = await fetch(`/api/sessions/${id}`, { method: 'DELETE' })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
}

export async function fetchHistory(
  sessionId: string,
  limit = 20,
  before?: number,
): Promise<{ turns: HistoryTurn[]; total: number; has_more: boolean }> {
  const params = new URLSearchParams({ limit: String(limit) })
  if (before) params.set('before', String(before))
  const res = await fetch(`/api/sessions/${sessionId}/history?${params}`)
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}
