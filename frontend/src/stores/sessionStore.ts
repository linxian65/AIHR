import { create } from 'zustand'
import type { HistoryTurn } from '../api/sessions'
import type { Message, PendingApproval } from '../types/events'

export interface SessionMeta {
  id: string
  title: string
  scenario: string
  createdAt: string
  lastActiveAt: string
}

export interface ScenarioInfo {
  key: string
  label: string
}

type AgentStatus = 'idle' | 'thinking' | 'tool_running' | 'awaiting_approval' | 'error'

interface SessionState {
  activeSessionId: string | null
  sessions: SessionMeta[]
  scenarios: ScenarioInfo[]
  messagesBySession: Record<string, Message[]>
  hasMoreBySession: Record<string, boolean>
  sessionCostBySession: Record<string, number>
  agentStatus: AgentStatus
  sseConnected: boolean
  pendingApprovals: PendingApproval[]
  doneCounter: number

  setActiveSession: (id: string) => void
  setSessions: (list: SessionMeta[]) => void
  upsertSession: (meta: SessionMeta) => void
  removeSession: (id: string) => void
  clearSessionMessages: (id: string) => void
  setScenarios: (list: ScenarioInfo[]) => void
  setSessionScenario: (sessionId: string, scenario: string) => void
  replayTurn: (sessionId: string, turn: HistoryTurn) => void
  setHasMore: (sessionId: string, hasMore: boolean) => void
  removeLastUserMessage: (sessionId: string) => void
  setSessionCost: (sessionId: string, cost: number) => void
  addSessionCost: (sessionId: string, delta: number) => void

  addMessage: (m: Message) => void
  appendAssistantDelta: (text: string) => void
  appendThinkingDelta: (text: string) => void
  updateToolUse: (toolUseId: string, patch: Partial<Extract<Message, { kind: 'tool_use' }>>) => void
  upsertBatchMessage: (patch: Partial<Extract<Message, { kind: 'batch' }>['state']>) => void
  appendBatchError: (err: { file: string; message: string }) => void
  addPendingApproval: (a: PendingApproval) => void
  removePendingApproval: (approvalId: string) => void
  setPendingApprovals: (list: PendingApproval[]) => void
  setStatus: (s: AgentStatus) => void
  setSseConnected: (b: boolean) => void
  incDoneCounter: () => void
}

const _updateActiveMessages = (
  s: SessionState,
  updater: (cur: Message[]) => Message[],
): Partial<SessionState> => {
  if (!s.activeSessionId) return {}
  const cur = s.messagesBySession[s.activeSessionId] ?? []
  return {
    messagesBySession: {
      ...s.messagesBySession,
      [s.activeSessionId]: updater(cur),
    },
  }
}

export const useSessionStore = create<SessionState>((set) => ({
  activeSessionId: null,
  sessions: [],
  scenarios: [],
  messagesBySession: {},
  hasMoreBySession: {},
  sessionCostBySession: {},
  agentStatus: 'idle',
  sseConnected: false,
  pendingApprovals: [],
  doneCounter: 0,

  setActiveSession: (id) => set({ activeSessionId: id, agentStatus: 'idle', pendingApprovals: [] }),

  setSessions: (list) => set({ sessions: list }),

  upsertSession: (meta) => set((s) => {
    const idx = s.sessions.findIndex((x) => x.id === meta.id)
    if (idx >= 0) {
      const next = s.sessions.slice()
      next[idx] = meta
      return { sessions: next }
    }
    return { sessions: [meta, ...s.sessions] }
  }),

  removeSession: (id) => set((s) => {
    const sessions = s.sessions.filter((x) => x.id !== id)
    const { [id]: _drop, ...messagesBySession } = s.messagesBySession
    let activeSessionId = s.activeSessionId
    if (s.activeSessionId === id) {
      activeSessionId = sessions[0]?.id ?? null
    }
    return {
      sessions,
      messagesBySession,
      activeSessionId,
      agentStatus: 'idle',
      pendingApprovals: [],
    }
  }),

  clearSessionMessages: (id) => set((s) => {
    if (!s.messagesBySession[id]) return {}
    return { messagesBySession: { ...s.messagesBySession, [id]: [] } }
  }),

  setScenarios: (scenarios) => set({ scenarios }),

  replayTurn: (sessionId, turn) => set((s) => {
    const cur = s.messagesBySession[sessionId] ?? []
    const newMsgs: Message[] = []

    newMsgs.push({
      kind: 'user',
      id: `u_${turn.turn_index}`,
      text: turn.user_content,
    })

    // Pending turn: agent run is still in flight. Stop here so we
    // don't try to consume an empty (or partial) events stream.
    if (turn.status === 'pending') {
      newMsgs.push({
        kind: 'pending',
        id: `p_${turn.turn_index}`,
        turnIndex: turn.turn_index,
      })
      return {
        messagesBySession: {
          ...s.messagesBySession,
          [sessionId]: [...cur, ...newMsgs],
        },
      }
    }

    let assistantMsg: Extract<Message, { kind: 'assistant' }> | null = null
    const toolMap: Record<string, Extract<Message, { kind: 'tool_use' }>> = {}
    let batchMsg: Extract<Message, { kind: 'batch' }> | null = null

    for (const ev of turn.events) {
      if (ev.event === 'thinking_delta' || ev.event === 'message_delta') {
        if (!assistantMsg) {
          assistantMsg = {
            kind: 'assistant',
            id: `a_${turn.turn_index}`,
            text: '',
            thinking: '',
          }
          newMsgs.push(assistantMsg)
        }
        if (ev.event === 'thinking_delta') {
          assistantMsg.thinking += ev.data.text ?? ''
        } else {
          assistantMsg.text += ev.data.text ?? ''
        }
      } else if (ev.event === 'tool_use_start') {
        // tool call breaks the current assistant segment; start fresh
        assistantMsg = null
        const tm: Extract<Message, { kind: 'tool_use' }> = {
          kind: 'tool_use',
          id: `t_${ev.data.tool_use_id}`,
          toolUseId: ev.data.tool_use_id,
          name: ev.data.name,
          input: ev.data.input ?? {},
          status: 'running',
        }
        toolMap[ev.data.tool_use_id] = tm
        newMsgs.push(tm)
      } else if (ev.event === 'tool_use_result') {
        const tm = toolMap[ev.data.tool_use_id]
        if (tm) {
          tm.status = ev.data.success ? 'success' : 'failed'
          tm.result = ev.data.result
        }
      } else if (ev.event === 'error') {
        newMsgs.push({
          kind: 'error',
          id: `e_${turn.turn_index}_${newMsgs.length}`,
          message: ev.data.message ?? '未知错误',
        })
      } else if (ev.event === 'batch_progress') {
        if (!batchMsg) {
          batchMsg = {
            kind: 'batch',
            id: `b_${turn.turn_index}`,
            state: {
              total: ev.data.total ?? 0,
              completed: ev.data.completed ?? 0,
              current: ev.data.current ?? null,
              errors: [],
              status: 'running',
            },
          }
          newMsgs.push(batchMsg)
        } else {
          batchMsg.state.total = ev.data.total ?? batchMsg.state.total
          batchMsg.state.completed = ev.data.completed ?? batchMsg.state.completed
          batchMsg.state.current = ev.data.current ?? batchMsg.state.current
        }
      } else if (ev.event === 'batch_error') {
        if (batchMsg) {
          batchMsg.state.errors = [
            ...batchMsg.state.errors,
            { file: ev.data.file ?? '?', message: ev.data.message ?? '' },
          ]
        }
      } else if (ev.event === 'batch_complete') {
        if (batchMsg) {
          batchMsg.state.status = 'done'
          batchMsg.state.okCount = ev.data.ok
          batchMsg.state.failedCount = ev.data.failed
          batchMsg.state.summaryPath = ev.data.summary_path
        } else {
          // No prior batch_progress; synthesize from complete payload.
          batchMsg = {
            kind: 'batch',
            id: `b_${turn.turn_index}`,
            state: {
              total: ev.data.total ?? 0,
              completed: ev.data.total ?? 0,
              current: null,
              errors: [],
              status: 'done',
              okCount: ev.data.ok,
              failedCount: ev.data.failed,
              summaryPath: ev.data.summary_path,
            },
          }
          newMsgs.push(batchMsg)
        }
      }
    }
    return {
      messagesBySession: {
        ...s.messagesBySession,
        [sessionId]: [...cur, ...newMsgs],
      },
    }
  }),

  setHasMore: (sessionId, hasMore) => set((s) => ({
    hasMoreBySession: { ...s.hasMoreBySession, [sessionId]: hasMore },
  })),

  removeLastUserMessage: (sessionId) => set((s) => {
    const cur = s.messagesBySession[sessionId] ?? []
    if (cur.length === 0) return {}
    const last = cur[cur.length - 1]
    if (last.kind !== 'user') return {}
    return {
      messagesBySession: {
        ...s.messagesBySession,
        [sessionId]: cur.slice(0, -1),
      },
    }
  }),

  setSessionCost: (sessionId, cost) => set((s) => ({
    sessionCostBySession: { ...s.sessionCostBySession, [sessionId]: cost },
  })),

  addSessionCost: (sessionId, delta) => set((s) => {
    const cur = s.sessionCostBySession[sessionId] ?? 0
    return {
      sessionCostBySession: {
        ...s.sessionCostBySession,
        [sessionId]: cur + delta,
      },
    }
  }),

  setSessionScenario: (sessionId, scenario) => set((s) => {
    const idx = s.sessions.findIndex((x) => x.id === sessionId)
    if (idx < 0) return {}
    const next = s.sessions.slice()
    next[idx] = { ...next[idx], scenario }
    return { sessions: next }
  }),

  addMessage: (m) => set((s) => _updateActiveMessages(s, (cur) => [...cur, m])),

  appendAssistantDelta: (text) => set((s) => {
    const next = _updateActiveMessages(s, (cur) => {
      const last = cur[cur.length - 1]
      if (last && last.kind === 'assistant') {
        const updated = { ...last, text: last.text + text }
        return [...cur.slice(0, -1), updated]
      }
      return [...cur, { kind: 'assistant', id: 'a_' + Date.now(), text, thinking: '' }]
    })
    return { ...next, agentStatus: 'thinking' }
  }),

  appendThinkingDelta: (text) => set((s) => _updateActiveMessages(s, (cur) => {
    const last = cur[cur.length - 1]
    if (last && last.kind === 'assistant') {
      const updated = { ...last, thinking: last.thinking + text }
      return [...cur.slice(0, -1), updated]
    }
    return [...cur, { kind: 'assistant', id: 'a_' + Date.now(), text: '', thinking: text }]
  })),

  updateToolUse: (toolUseId, patch) => set((s) => _updateActiveMessages(s, (cur) =>
    cur.map((m) => (m.kind === 'tool_use' && m.toolUseId === toolUseId ? { ...m, ...patch } : m))
  )),

  upsertBatchMessage: (patch) => set((s) => _updateActiveMessages(s, (cur) => {
    const last = cur[cur.length - 1]
    if (last && last.kind === 'batch') {
      const updated: Extract<Message, { kind: 'batch' }> = {
        ...last,
        state: { ...last.state, ...patch },
      }
      return [...cur.slice(0, -1), updated]
    }
    const fresh: Extract<Message, { kind: 'batch' }> = {
      kind: 'batch',
      id: 'b_' + Date.now(),
      state: {
        total: 0,
        completed: 0,
        current: null,
        errors: [],
        status: 'running',
        ...patch,
      },
    }
    return [...cur, fresh]
  })),

  appendBatchError: (err) => set((s) => _updateActiveMessages(s, (cur) => {
    const last = cur[cur.length - 1]
    if (!last || last.kind !== 'batch') return cur
    const updated: Extract<Message, { kind: 'batch' }> = {
      ...last,
      state: { ...last.state, errors: [...last.state.errors, err] },
    }
    return [...cur.slice(0, -1), updated]
  })),

  addPendingApproval: (a) => set((s) => ({
    pendingApprovals: [...s.pendingApprovals.filter((x) => x.approval_id !== a.approval_id), a],
    agentStatus: 'awaiting_approval',
  })),

  removePendingApproval: (id) => set((s) => ({
    pendingApprovals: s.pendingApprovals.filter((x) => x.approval_id !== id),
    agentStatus: s.pendingApprovals.length <= 1 ? 'thinking' : 'awaiting_approval',
  })),

  setPendingApprovals: (list) => set({ pendingApprovals: list }),

  setStatus: (agentStatus) => set({ agentStatus }),
  setSseConnected: (sseConnected) => set({ sseConnected }),
  incDoneCounter: () => set((s) => ({ doneCounter: s.doneCounter + 1 })),
}))
