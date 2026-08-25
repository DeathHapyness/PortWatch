import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { renderHook } from '@testing-library/react'
import type { PropsWithChildren } from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { portwatchQueryKeys } from './queries'
import { useSnapshotEvents } from './useSnapshotEvents'

type Listener = (event: { data?: unknown }) => void

class FakeWebSocket {
  static instances: FakeWebSocket[] = []

  readonly url: string
  readonly sent: string[] = []
  closed = false
  private readonly listeners = new Map<string, Listener[]>()

  constructor(url: string) {
    this.url = url
    FakeWebSocket.instances.push(this)
  }

  addEventListener(type: string, listener: Listener): void {
    const list = this.listeners.get(type) ?? []
    list.push(listener)
    this.listeners.set(type, list)
  }

  send(data: string): void {
    this.sent.push(data)
  }

  close(): void {
    if (this.closed) return
    this.closed = true
    this.dispatch('close', {})
  }

  dispatch(type: string, event: { data?: unknown }): void {
    for (const listener of this.listeners.get(type) ?? []) listener(event)
  }

  static latest(): FakeWebSocket {
    const instance = FakeWebSocket.instances.at(-1)
    if (!instance) throw new Error('no FakeWebSocket was constructed')
    return instance
  }
}

function createWrapper(queryClient: QueryClient) {
  return function Wrapper({ children }: PropsWithChildren) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  }
}

describe('useSnapshotEvents', () => {
  beforeEach(() => {
    FakeWebSocket.instances = []
    vi.stubGlobal('WebSocket', FakeWebSocket)
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    vi.useRealTimers()
  })

  it('opens a socket at /api/v1/events and sends the token as the first message', () => {
    renderHook(() => useSnapshotEvents(), {
      wrapper: createWrapper(new QueryClient()),
    })

    const socket = FakeWebSocket.latest()
    expect(socket.url).toMatch(/^wss?:\/\/.*\/api\/v1\/events$/)

    socket.dispatch('open', {})
    expect(socket.sent).toEqual([JSON.stringify({ token: '' })])
  })

  it('invalidates every PortWatch query on a snapshot.updated message', async () => {
    const queryClient = new QueryClient()
    const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries')

    renderHook(() => useSnapshotEvents(), { wrapper: createWrapper(queryClient) })

    const socket = FakeWebSocket.latest()
    socket.dispatch('message', { data: JSON.stringify({ type: 'snapshot.updated' }) })

    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: portwatchQueryKeys.all })
  })

  it('ignores messages that are not snapshot.updated without throwing', () => {
    const queryClient = new QueryClient()
    const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries')

    renderHook(() => useSnapshotEvents(), { wrapper: createWrapper(queryClient) })

    const socket = FakeWebSocket.latest()
    expect(() => socket.dispatch('message', { data: 'not json' })).not.toThrow()
    expect(() => socket.dispatch('message', { data: '{}' })).not.toThrow()
    expect(() => socket.dispatch('message', { data: 42 })).not.toThrow()

    expect(invalidateSpy).not.toHaveBeenCalled()
  })

  it('reconnects with a growing delay after the socket closes', () => {
    vi.useFakeTimers()

    renderHook(() => useSnapshotEvents(), {
      wrapper: createWrapper(new QueryClient()),
    })
    expect(FakeWebSocket.instances).toHaveLength(1)

    FakeWebSocket.latest().dispatch('close', {})
    expect(FakeWebSocket.instances).toHaveLength(1) // not yet — reconnect is delayed

    vi.advanceTimersByTime(1_000)
    expect(FakeWebSocket.instances).toHaveLength(2)

    FakeWebSocket.latest().dispatch('close', {})
    vi.advanceTimersByTime(1_000)
    expect(FakeWebSocket.instances).toHaveLength(2) // backed off past 1s this time

    vi.advanceTimersByTime(1_000) // total 2s, the doubled delay
    expect(FakeWebSocket.instances).toHaveLength(3)
  })

  it('closes the socket and stops reconnecting on unmount', () => {
    vi.useFakeTimers()

    const { unmount } = renderHook(() => useSnapshotEvents(), {
      wrapper: createWrapper(new QueryClient()),
    })
    const socket = FakeWebSocket.latest()

    unmount()

    expect(socket.closed).toBe(true)
    vi.advanceTimersByTime(60_000)
    expect(FakeWebSocket.instances).toHaveLength(1) // no reconnect after unmount
  })
})
