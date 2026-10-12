import { useEffect, useRef } from 'react'
import { useSessionStore } from '../stores/sessionStore'

export function useSSE(sessionId: string) {
  const esRef = useRef<EventSource | null>(null)
  const {
    addMessage, appendAssistantDelta, appendThinkingDelta,
    updateToolUse, setStatus, setSseConnected, addPendingApproval,
    incDoneCounter, addSessionCost,
    upsertBatchMessage, appendBatchError,
  } = useSessionStore()

  useEffect(() => {
    if (!sessionId) {
      setSseConnected(false)
      return
    }
    const es = new EventSource(`/api/sessions/${sessionId}/stream`)
    esRef.current = es

    es.onopen = () => setSseConnected(true)
    es.onerror = () => setSseConnected(false)

    const handle = (e: MessageEvent, type: string) => {
      let payload: any
      try { payload = JSON.parse(e.data) } catch { return }
      switch (type) {
        case 'message_delta':
          appendAssistantDelta(payload.text ?? '')
          break
        case 'thinking_delta':
          appendThinkingDelta(payload.text ?? '')
          break
        case 'tool_use_start':
          setStatus('tool_running')
          addMessage({
            kind: 'tool_use',
            id: 't_' + payload.tool_use_id,
            toolUseId: payload.tool_use_id,
            name: payload.name,
            input: payload.input ?? {},
            status: 'running',
          })
          break
        case 'tool_use_result':
          updateToolUse(payload.tool_use_id, {
            status: payload.success ? 'success' : 'failed',
            result: payload.result,
          })
          break
        case 'result':
          console.log('[result] cost=', payload.cost_usd)
          if (typeof payload.cost_usd === 'number') {
            addSessionCost(sessionId, payload.cost_usd)
          }
          break
        case 'approval_required':
          addPendingApproval({
            approval_id: payload.approval_id,
            tool_name: payload.tool_name,
            input: payload.input ?? {},
            createdAt: Date.now(),
          })
          break
        case 'batch_progress':
          upsertBatchMessage({
            total: payload.total ?? 0,
            completed: payload.completed ?? 0,
            current: payload.current ?? null,
            status: 'running',
          })
          break
        case 'batch_error':
          appendBatchError({
            file: payload.file ?? '?',
            message: payload.message ?? '',
          })
          break
        case 'batch_complete':
          upsertBatchMessage({
            status: 'done',
            okCount: payload.ok,
            failedCount: payload.failed,
            summaryPath: payload.summary_path,
          })
          break
        case 'error':
          addMessage({ kind: 'error', id: 'e_' + Date.now(), message: payload.message })
          setStatus('error')
          break
        case 'done':
          setStatus('idle')
          incDoneCounter()
          break
        case 'ping':
          break
      }
    }

    const types = ['message_delta','thinking_delta','tool_use_start','tool_use_result','approval_required','result','error','done','ping','batch_progress','batch_error','batch_complete']
    types.forEach((t) => es.addEventListener(t, (e) => handle(e as MessageEvent, t)))

    return () => {
      es.close()
      esRef.current = null
      setSseConnected(false)
    }
  }, [sessionId])

  return esRef
}
