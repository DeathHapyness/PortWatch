import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError, api, formatProblemDetail, type ProblemDetail } from './api'

const fetchMock = vi.fn<typeof fetch>()

function response(body: string, init?: ResponseInit): Response {
  return new Response(body, init)
}

function jsonResponse(body: unknown, init?: ResponseInit): Response {
  return response(JSON.stringify(body), {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  })
}

describe('typed API client', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', fetchMock)
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    vi.unstubAllEnvs()
    fetchMock.mockReset()
  })

  it('returns JSON and forwards the abort signal and accepted media types', async () => {
    const payload = { portwatch_status: 'ok', docker_version: '29.0.0' }
    const controller = new AbortController()
    fetchMock.mockResolvedValue(jsonResponse(payload))

    await expect(api.systemSummary(controller.signal)).resolves.toEqual(payload)
    expect(fetchMock).toHaveBeenCalledWith('/api/v1/system/summary', {
      headers: { Accept: 'application/json, application/problem+json' },
      signal: controller.signal,
    })
  })

  it('sends a Bearer Authorization header when VITE_API_TOKEN is configured', async () => {
    vi.stubEnv('VITE_API_TOKEN', 's3cr3t')
    fetchMock.mockResolvedValue(jsonResponse({}))

    await api.systemSummary()

    expect(fetchMock).toHaveBeenCalledWith('/api/v1/system/summary', {
      headers: {
        Accept: 'application/json, application/problem+json',
        Authorization: 'Bearer s3cr3t',
      },
      signal: undefined,
    })
  })

  it('omits Authorization entirely when no token is configured', async () => {
    fetchMock.mockResolvedValue(jsonResponse({}))

    await api.systemSummary()

    const [, init] = fetchMock.mock.calls[0]
    expect(init?.headers).not.toHaveProperty('Authorization')
  })

  it.each(['application/problem+json', 'application/vnd.portwatch.problem+json'])(
    'parses RFC 7807 errors returned as %s',
    async (contentType) => {
      const problem: ProblemDetail = {
        type: 'about:blank',
        title: 'Not Found',
        status: 404,
        detail: 'container not found',
        request_id: 'req-123',
      }
      fetchMock.mockResolvedValue(
        response(JSON.stringify(problem), {
          status: 404,
          headers: { 'Content-Type': `${contentType}; charset=utf-8` },
        }),
      )

      try {
        await api.container('missing')
        expect.unreachable('request should have thrown ApiError')
      } catch (error) {
        expect(error).toBeInstanceOf(ApiError)
        expect(error).toMatchObject({
          name: 'ApiError',
          message: 'container not found',
          status: 404,
          problem,
        })
      }
    },
  )

  it('falls back safely when an error body contains malformed JSON', async () => {
    fetchMock.mockResolvedValue(
      response('{not-json', {
        status: 502,
        headers: { 'Content-Type': 'application/problem+json' },
      }),
    )

    await expect(api.networks()).rejects.toMatchObject({
      name: 'ApiError',
      message: 'API request failed with status 502',
      status: 502,
      problem: null,
    })
  })

  it('does not try to parse a non-JSON error body', async () => {
    fetchMock.mockResolvedValue(
      response('service unavailable', {
        status: 503,
        headers: { 'Content-Type': 'text/plain' },
      }),
    )

    await expect(api.ports()).rejects.toMatchObject({
      status: 503,
      problem: null,
    })
  })

  it('encodes every container filter without losing special characters', async () => {
    fetchMock.mockResolvedValue(jsonResponse([]))

    await api.containers({
      status: 'running',
      network: 'dev network',
      label: 'portwatch.env=dev/sandbox',
      query: 'redis & cache',
    })

    expect(fetchMock).toHaveBeenCalledWith(
      '/api/v1/containers?status_filter=running&network=dev+network&label=portwatch.env%3Ddev%2Fsandbox&q=redis+%26+cache',
      expect.any(Object),
    )
  })

  it('preserves zero-valued port filters instead of treating them as absent', async () => {
    fetchMock.mockImplementation(async () =>
      jsonResponse({ range_start: 0, range_end: 0, entries: [] }),
    )

    await api.ports({ state: 'free', rangeStart: 0, rangeEnd: 0 })
    await api.availablePorts({ rangeStart: 0, rangeEnd: 0, limit: 0 })

    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      '/api/v1/ports?state=free&range_start=0&range_end=0',
      expect.any(Object),
    )
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      '/api/v1/ports/available?range_start=0&range_end=0&limit=0',
      expect.any(Object),
    )
  })

  it('path-encodes container and network identifiers', async () => {
    fetchMock.mockImplementation(async () => jsonResponse({}))

    await api.container('name/with space')
    await api.network('bridge/name with space')

    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      '/api/v1/containers/name%2Fwith%20space',
      expect.any(Object),
    )
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      '/api/v1/networks/bridge%2Fname%20with%20space',
      expect.any(Object),
    )
  })

  it('propagates fetch failures without relabeling them as HTTP errors', async () => {
    const networkError = new TypeError('Failed to fetch')
    fetchMock.mockRejectedValue(networkError)

    await expect(api.systemSummary()).rejects.toBe(networkError)
  })

  it('rejects malformed JSON in a successful response', async () => {
    fetchMock.mockResolvedValue(
      response('{not-json', {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    )

    await expect(api.systemSummary()).rejects.toBeInstanceOf(SyntaxError)
  })

  it('uses formatProblemDetail(detail) for the thrown error message when detail is a FastAPI 422 validation array', async () => {
    // The backend's `detail` on ProblemDetail is `Any` (core/schemas.py) — a
    // 422 response's detail is FastAPI's RequestValidationError.errors(), a
    // list of {loc, msg, type}, not a string. Rendering it directly used to
    // crash React ("Objects are not valid as a React child"); the message
    // built for ApiError must go through the same formatter.
    fetchMock.mockResolvedValue(
      response(
        JSON.stringify({
          type: 'about:blank',
          title: 'Validation Error',
          status: 422,
          detail: [{ loc: ['query', 'range_start'], msg: 'value is not a valid integer' }],
          request_id: 'req-1',
        }),
        { status: 422, headers: { 'Content-Type': 'application/problem+json' } },
      ),
    )

    await expect(api.ports()).rejects.toMatchObject({
      message: 'query.range_start: value is not a valid integer',
    })
  })
})

describe('formatProblemDetail', () => {
  it('returns null for a null or undefined detail', () => {
    expect(formatProblemDetail(null)).toBeNull()
    expect(formatProblemDetail(undefined)).toBeNull()
  })

  it('returns null for an empty or whitespace-only string', () => {
    expect(formatProblemDetail('')).toBeNull()
    expect(formatProblemDetail('   ')).toBeNull()
  })

  it('trims and returns a normal string detail unchanged', () => {
    expect(formatProblemDetail('  container not found  ')).toBe('container not found')
  })

  it('truncates an overly long string detail with an ellipsis', () => {
    const long = 'x'.repeat(600)

    const result = formatProblemDetail(long)

    expect(result).toHaveLength(500)
    expect(result?.endsWith('…')).toBe(true)
    expect(result?.startsWith('x'.repeat(499))).toBe(true)
  })

  it('formats a single FastAPI validation issue with its field path', () => {
    const detail = [{ loc: ['body', 'port'], msg: 'value is not a valid integer' }]

    expect(formatProblemDetail(detail)).toBe('body.port: value is not a valid integer')
  })

  it('joins multiple validation issues and includes numeric list indices in the path', () => {
    const detail = [
      { loc: ['body', 'items', 0, 'port'], msg: 'field required' },
      { loc: ['query', 'range_start'], msg: 'value is not a valid integer' },
    ]

    expect(formatProblemDetail(detail)).toBe(
      'body.items.0.port: field required; query.range_start: value is not a valid integer',
    )
  })

  it('omits the field path when loc is absent, keeping just the message', () => {
    expect(formatProblemDetail([{ msg: 'something went wrong' }])).toBe('something went wrong')
  })

  it('filters out malformed issues but keeps the well-formed ones', () => {
    const detail = [{ msg: 'first problem' }, { loc: ['x'] }, 'not an object', 42, null]

    expect(formatProblemDetail(detail)).toBe('first problem')
  })

  it('falls back to JSON.stringify when every array entry is unusable', () => {
    const detail = ['not an object', 42, null]

    expect(formatProblemDetail(detail)).toBe(JSON.stringify(detail))
  })

  it('falls back to JSON.stringify for a plain object detail', () => {
    const detail = { unexpected: 'shape' }

    expect(formatProblemDetail(detail)).toBe(JSON.stringify(detail))
  })

  it('falls back to JSON.stringify for a bare number or boolean detail', () => {
    expect(formatProblemDetail(404)).toBe('404')
    expect(formatProblemDetail(false)).toBe('false')
  })
})
