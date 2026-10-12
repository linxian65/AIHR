import { useEffect } from 'react'
import { listPendingApprovals } from '../api/approvals'
import { useSessionStore } from '../stores/sessionStore'

/** Pulls any pending approvals from SQLite when the active session changes.

    SSE only fires events from the current run; approvals that arrived
    before a page reload live only in the DB. This hook rehydrates them
    once per session switch.
*/
export function useApprovalSync(sessionId: string | null) {
  const setPendingApprovals = useSessionStore((s) => s.setPendingApprovals)

  useEffect(() => {
    if (!sessionId) return
    let cancelled = false
    ;(async () => {
      try {
        const list = await listPendingApprovals(sessionId)
        if (cancelled) return
        setPendingApprovals(list)
      } catch (e) {
        console.warn('load pending approvals failed', e)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [sessionId])
}