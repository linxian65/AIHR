import type { SessionMeta, ScenarioInfo } from '../stores/sessionStore'

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
