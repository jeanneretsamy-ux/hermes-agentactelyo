import type { Page } from '@playwright/test'

/** Bounded synthetic-test diagnostics. Never retain credentials or prompt bodies. */
export function captureRpc(page: Page, records: unknown[]): void {
  const methods = new Set(['profiles.create', 'setup.runtime_check', 'session.create', 'session.title', 'session.list', 'session.resume', 'prompt.submit'])
  page.on('websocket', socket => {
    const pending = new Map<unknown, string>()
    socket.on('framesent', frame => {
      try {
        const request = JSON.parse(String(frame.payload))
        if (!methods.has(request.method) || records.length >= 200) { return }
        pending.set(request.id, request.method)
        const { profile, session_id, title } = request.params ?? {}
        records.push({ direction: 'request', id: request.id, method: request.method, profile, session_id, title })
      } catch { /* not a JSON-RPC frame */ }
    })
    socket.on('framereceived', frame => {
      try {
        const response = JSON.parse(String(frame.payload)), method = pending.get(response.id)
        if (!method || records.length >= 200) { return }
        pending.delete(response.id)
        const { ok, error, session_id, stored_session_id } = response.result ?? {}
        records.push({ direction: 'response', id: response.id, method, ok, error: response.error ?? error, session_id, stored_session_id })
      } catch { /* not a JSON-RPC frame */ }
    })
  })
}
