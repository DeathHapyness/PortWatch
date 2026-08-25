import { useQueryClient } from '@tanstack/react-query'
import * as React from 'react'

import { getApiToken } from './config'
import { portwatchQueryKeys } from './queries'

const RECONNECT_BASE_DELAY_MS = 1_000
const RECONNECT_MAX_DELAY_MS = 30_000

interface SnapshotUpdatedMessage {
  type: 'snapshot.updated'
}

function isSnapshotUpdatedMessage(value: unknown): value is SnapshotUpdatedMessage {
  return (
    typeof value === 'object' &&
    value !== null &&
    (value as { type?: unknown }).type === 'snapshot.updated'
  )
}

function eventsSocketUrl(): string {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${protocol}//${window.location.host}/api/v1/events`
}

/**
 * Subscribes to /api/v1/events and invalidates every PortWatch query as
 * soon as the Collector publishes a new snapshot, instead of waiting for
 * the next poll (queries.ts's snapshotQueryDefaults keep polling too, as a
 * fallback if the socket is ever down).
 *
 * Auth: the native browser WebSocket API can't set a custom Authorization
 * header on the handshake, so this always authenticates via the
 * first-message path — sending `{"token": ...}` right after `open` (see
 * docs/adr/0006-websocket-first-message-auth.md). That message is harmless
 * even when the backend has no token configured (the dev default): the
 * server's auth step is a no-op in that case and the unrequired message is
 * just read and discarded by the main event loop (api/events.py).
 */
export function useSnapshotEvents(): void {
  const queryClient = useQueryClient()

  React.useEffect(() => {
    let socket: WebSocket | null = null
    let reconnectTimer: ReturnType<typeof setTimeout> | undefined
    let reconnectDelayMs = RECONNECT_BASE_DELAY_MS
    let stopped = false

    function scheduleReconnect(): void {
      if (stopped) return
      const delay = reconnectDelayMs
      reconnectDelayMs = Math.min(reconnectDelayMs * 2, RECONNECT_MAX_DELAY_MS)
      reconnectTimer = setTimeout(connect, delay)
    }

    function connect(): void {
      if (stopped) return
      const nextSocket = new WebSocket(eventsSocketUrl())
      socket = nextSocket

      nextSocket.addEventListener('open', () => {
        reconnectDelayMs = RECONNECT_BASE_DELAY_MS
        nextSocket.send(JSON.stringify({ token: getApiToken() }))
      })

      nextSocket.addEventListener('message', (event) => {
        if (typeof event.data !== 'string') return
        let payload: unknown
        try {
          payload = JSON.parse(event.data)
        } catch {
          return
        }
        if (isSnapshotUpdatedMessage(payload)) {
          void queryClient.invalidateQueries({ queryKey: portwatchQueryKeys.all })
        }
      })

      // A socket that never finished connecting (or was rejected during
      // auth) still fires 'close' — one handler covers both "connected,
      // then dropped" and "never got in" without duplicating reconnect logic.
      nextSocket.addEventListener('close', scheduleReconnect)
      nextSocket.addEventListener('error', () => nextSocket.close())
    }

    connect()

    return () => {
      stopped = true
      if (reconnectTimer !== undefined) clearTimeout(reconnectTimer)
      socket?.close()
    }
  }, [queryClient])
}
