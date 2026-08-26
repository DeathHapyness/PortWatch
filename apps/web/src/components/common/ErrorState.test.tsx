import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { ErrorState } from './ErrorState'
import { ApiError, type ProblemDetail } from '@/lib/api'

function problem(overrides: Partial<ProblemDetail> = {}): ProblemDetail {
  return {
    type: 'about:blank',
    title: 'Something went wrong',
    status: 500,
    detail: null,
    request_id: null,
    ...overrides,
  }
}

describe('ErrorState', () => {
  it('renders a plain error message for a non-ApiError', () => {
    render(<ErrorState error={new Error('boom')} />)

    expect(screen.getByText('boom')).toBeInTheDocument()
  })

  it('renders the problem title, status, and request id', () => {
    // ApiError's message falls back to the title when detail is null, so
    // "Not Found" legitimately appears twice (summary line + detail box) —
    // assert presence rather than a single-match count.
    const apiError = new ApiError(
      404,
      problem({ title: 'Not Found', detail: null, status: 404, request_id: 'req-123' }),
    )

    render(<ErrorState error={apiError} />)

    expect(screen.getAllByText(/Not Found/).length).toBeGreaterThan(0)
    expect(screen.getByText('404', { exact: false })).toBeInTheDocument()
    expect(screen.getByText('req-123')).toBeInTheDocument()
  })

  it('renders a string detail', () => {
    const apiError = new ApiError(404, problem({ detail: 'container not found' }))

    render(<ErrorState error={apiError} />)

    // Appears both as the summary message and in the Detail: line — assert
    // presence, not a single-match count.
    expect(screen.getAllByText(/container not found/).length).toBeGreaterThan(0)
  })

  it('formats a FastAPI validation-error array instead of crashing', () => {
    const apiError = new ApiError(
      422,
      problem({
        title: 'Validation Error',
        detail: [{ loc: ['query', 'range_start'], msg: 'value is not a valid integer' }],
        status: 422,
      }),
    )

    expect(() => render(<ErrorState error={apiError} />)).not.toThrow()
    expect(
      screen.getAllByText(/query\.range_start: value is not a valid integer/).length,
    ).toBeGreaterThan(0)
  })

  it('omits the Detail line when detail is null', () => {
    const apiError = new ApiError(500, problem({ detail: null }))

    render(<ErrorState error={apiError} />)

    expect(screen.queryByText('Detail:')).not.toBeInTheDocument()
  })

  it('calls onRetry when the retry button is clicked', () => {
    let retried = false
    render(<ErrorState error={new Error('boom')} onRetry={() => (retried = true)} />)

    screen.getByRole('button', { name: /try again/i }).click()

    expect(retried).toBe(true)
  })
})
