import { create } from 'zustand'
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

  addMessage: (m: Message) => void
  appendAssistantDelta: (text: string) => void
  appendThinkingDelta: (text: string) => void
  updateToolUse: (toolUseId: string, patch: Partial<Extract<Message, { kind: 'tool_use' }>>) => void
  addPendingApproval: (a: PendingApproval) => void
  removePendingApproval: (approvalId: string) => void
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

  addPendingApproval: (a) => set((s) => ({
    pendingApprovals: [...s.pendingApprovals.filter((x) => x.approval_id !== a.approval_id), a],
    agentStatus: 'awaiting_approval',
  })),

  removePendingApproval: (id) => set((s) => ({
    pendingApprovals: s.pendingApprovals.filter((x) => x.approval_id !== id),
    agentStatus: s.pendingApprovals.length <= 1 ? 'thinking' : 'awaiting_approval',
  })),

  setStatus: (agentStatus) => set({ agentStatus }),
  setSseConnected: (sseConnected) => set({ sseConnected }),
  incDoneCounter: () => set((s) => ({ doneCounter: s.doneCounter + 1 })),
}))
