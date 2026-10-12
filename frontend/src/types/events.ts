export type SSEEvent =
  | { type: 'thinking_delta'; text: string }
  | { type: 'message_delta'; text: string }
  | { type: 'tool_use_start'; tool_use_id: string; name: string; input: Record<string, unknown> }
  | { type: 'tool_use_result'; tool_use_id: string; success: boolean; result: string }
  | { type: 'approval_required'; approval_id: string; tool_name: string; input: Record<string, unknown> }
  | { type: 'result'; subtype: string; cost_usd: number | null }
  | { type: 'error'; message: string; errorType?: string }
  | { type: 'done' }
  | { type: 'ping' }

export type Message =
  | { kind: 'user'; id: string; text: string }
  | { kind: 'assistant'; id: string; text: string; thinking: string }
  | { kind: 'tool_use'; id: string; toolUseId: string; name: string; input: Record<string, unknown>; status: 'running' | 'success' | 'failed'; result?: string }
  | { kind: 'error'; id: string; message: string }

export interface PendingApproval {
  approval_id: string
  tool_name: string
  input: Record<string, unknown>
  createdAt: number
}
