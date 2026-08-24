import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import App from './App'

const fetchMock = vi.fn<typeof fetch>()

function renderApp() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
    },
  })

  return render(
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>,
  )
}

function jsonResponse(body: unknown, init?: ResponseInit): Response {
  return new Response(JSON.stringify(body), {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  })
}

describe('App', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', fetchMock)
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    fetchMock.mockReset()
  })

  it('loads the system summary from the versioned API', async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse({ portwatch_status: 'ok', docker_version: '29.0.0' }),
    )

    renderApp()

    expect(screen.getByText('checking /api/v1/system/summary…')).toBeInTheDocument()
    expect(await screen.findByText('status: ok · docker: 29.0.0')).toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalledWith('/api/v1/system/summary')
  })

  it('shows an actionable message when the backend request fails', async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse({}, { status: 503 }))

    renderApp()

    expect(
      await screen.findByText('error: backend returned 503 (is the backend running?)'),
    ).toBeInTheDocument()
  })

  it('requests a fresh summary when the user rechecks', async () => {
    fetchMock
      .mockResolvedValueOnce(jsonResponse({ portwatch_status: 'ok', docker_version: null }))
      .mockResolvedValueOnce(jsonResponse({ portwatch_status: 'ok', docker_version: '29.0.1' }))
    const user = userEvent.setup()

    renderApp()
    await screen.findByText('status: ok · docker: null')

    await user.click(screen.getByRole('button', { name: 'Recheck' }))

    expect(await screen.findByText('status: ok · docker: 29.0.1')).toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalledTimes(2)
  })
})
