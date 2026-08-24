import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { renderHook, waitFor } from '@testing-library/react'
import type { PropsWithChildren } from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import {
  portwatchQueryKeys,
  useContainerQuery,
  useContainersQuery,
  useSystemSummaryQuery,
} from './queries'

const fetchMock = vi.fn<typeof fetch>()

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })

  return function Wrapper({ children }: PropsWithChildren) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  }
}

function jsonResponse(body: unknown): Response {
  return new Response(JSON.stringify(body), {
    headers: { 'Content-Type': 'application/json' },
  })
}

describe('PortWatch query hooks', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', fetchMock)
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    fetchMock.mockReset()
  })

  it('shares one cached system request between consumers', async () => {
    fetchMock.mockResolvedValue(jsonResponse({ portwatch_status: 'ok' }))
    const wrapper = createWrapper()

    const first = renderHook(() => useSystemSummaryQuery(), { wrapper })
    const second = renderHook(() => useSystemSummaryQuery(), { wrapper })

    await waitFor(() => expect(first.result.current.isSuccess).toBe(true))
    expect(second.result.current.data?.portwatch_status).toBe('ok')
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })

  it('keeps container filters in both the key and request', async () => {
    fetchMock.mockResolvedValue(jsonResponse([]))
    const filters = { status: 'running', network: 'portwatch-dev-net' } as const

    const { result } = renderHook(() => useContainersQuery(filters), {
      wrapper: createWrapper(),
    })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(portwatchQueryKeys.containerList(filters)).toEqual([
      'portwatch',
      'containers',
      'list',
      filters,
    ])
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/v1/containers?status_filter=running&network=portwatch-dev-net',
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    )
  })

  it('does not request a container detail without an id', () => {
    const { result } = renderHook(() => useContainerQuery(''), {
      wrapper: createWrapper(),
    })

    expect(result.current.fetchStatus).toBe('idle')
    expect(fetchMock).not.toHaveBeenCalled()
  })
})
