import { useEffect, useRef } from 'react'
import { fetchHistory } from '../api/sessions'
import { useSessionStore } from '../stores/sessionStore'

/** Loads stored turns for `sessionId` whenever it changes.

    Clears any in-memory messages for that session first, then replays
    each turn's stored events into the message store. Future SSE deltas
    appended during a live run continue from where the replay left off.

    If the most recent turn is still `pending` (agent run in flight),
    starts a 5s poll loop that re-replays history until the turn
    finalizes. The poll is cancelled when the session changes or the
    hook unmounts.
*/
export function useHistory(sessionId: string | null) {
  const {
    clearSessionMessages, replayTurn, setHasMore, setSessionCost,
  } = useSessionStore()
  const pollingRef = useRef<number | null>(null)

  useEffect(() => {
    if (!sessionId) return
    let cancelled = false

    const stopPolling = () => {
      if (pollingRef.current !== null) {
        window.clearInterval(pollingRef.current)
        pollingRef.current = null
      }
    }

    const reloadAll = async () => {
      const data = await fetchHistory(sessionId, 20)
      if (cancelled) return
      clearSessionMessages(sessionId)
      for (const turn of data.turns) {
        replayTurn(sessionId, turn)
      }
      setHasMore(sessionId, data.has_more)
      setSessionCost(sessionId, data.total_cost ?? 0)
      return data
    }

    const startPolling = () => {
      if (pollingRef.current !== null) return
      pollingRef.current = window.setInterval(async () => {
        try {
          const data = await reloadAll()
          if (!data) return
          const last = data.turns[data.turns.length - 1]
          if (!last || last.status !== 'pending') stopPolling()
        } catch {
          // ignore transient errors; next tick will retry
        }
      }, 5000)
    }

    ;(async () => {
      try {
        const data = await reloadAll()
        if (cancelled || !data) return
        const last = data.turns[data.turns.length - 1]
        if (last && last.status === 'pending') startPolling()
      } catch (e) {
        console.error('load history failed', e)
      }
    })()

    return () => {
      cancelled = true
      stopPolling()
    }
  }, [sessionId])
}