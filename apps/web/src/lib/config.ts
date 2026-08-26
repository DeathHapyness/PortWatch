/**
 * Frontend-side config knobs — currently just the API bearer token (ADR-0004).
 *
 * REST calls send it as a Bearer token when configured; omitting the header
 * when it is empty preserves the loopback-only development mode. The native
 * browser WebSocket API cannot set an Authorization header during the
 * handshake, so /api/v1/events sends the same value in its first message
 * instead (see docs/adr/0006-websocket-first-message-auth.md).
 *
 * Storage: the token entered via the Settings dialog (see
 * components/layout/ApiTokenDialog.tsx) is kept only in this browser's
 * localStorage — the same per-browser pattern Header.tsx already uses for
 * the theme. `VITE_API_TOKEN` is still read as a fallback for local
 * development convenience, but it is NOT the recommended path for a real
 * deployment: Vite embeds any `VITE_*` env var in plain text in the built
 * JS bundle, so anyone who loads the page can read it straight out of
 * dist/assets/*.js. That's harmless when only the machine's own user ever
 * loads the page; it stops being a secret the moment the page is reachable
 * by anyone else — exactly the case a public, MIT-licensed deployment has
 * to assume. The localStorage-backed token never ends up in a shared file,
 * so it stays the right default for anything beyond solo loopback use.
 */
const STORAGE_KEY = 'portwatch-api-token'

export function getApiToken(): string {
  const stored = readStoredToken()
  if (stored) return stored
  return import.meta.env.VITE_API_TOKEN ?? ''
}

/** Persists (or, given an empty/whitespace-only value, clears) the token. */
export function setApiToken(token: string): void {
  const trimmed = token.trim()
  try {
    if (trimmed) {
      localStorage.setItem(STORAGE_KEY, trimmed)
    } else {
      localStorage.removeItem(STORAGE_KEY)
    }
  } catch {
    // localStorage can throw (private browsing in some browsers, storage
    // disabled by policy, quota errors). Not fatal — the token just won't
    // persist across reloads; getApiToken() still falls back to the
    // build-time env var, if any, for the rest of this session.
  }
}

function readStoredToken(): string {
  try {
    return localStorage.getItem(STORAGE_KEY) ?? ''
  } catch {
    return ''
  }
}
