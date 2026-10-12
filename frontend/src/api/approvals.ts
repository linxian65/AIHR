import type { PendingApproval } from '../types/events'

interface RawApproval {
  id: string
  tool_name: string
  input: Record<string, unknown>
  created_at: string
}

export async function listPendingApprovals(sessionId: string): Promise<PendingApproval[]> {
  const res = await fetch(`/api/sessions/${sessionId}/approvals`)
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  const data = await res.json()
  return (data.pending ?? []).map((x: RawApproval) => ({
    approval_id: x.id,
    tool_name: x.tool_name,
    input: x.input,
    createdAt: new Date(x.created_at).getTime(),
    fromDb: true,
  }))
}