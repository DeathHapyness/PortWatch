/**
 * Frontend-side config knobs — currently just the API bearer token (ADR-0004).
 *
 * REST calls (api.ts) don't send this yet: in dev, the backend binds to
 * loopback with no token configured, so every REST request already works
 * unauthenticated (see core/config.py's validate_bind_security). The
 * WebSocket handshake is different — a browser can't set a custom
 * Authorization header on it at all, so /api/v1/events needs the token
 * regardless (first-message auth, see
 * docs/adr/0006-websocket-first-message-auth.md) even though REST doesn't
 * strictly need it yet. Wiring REST auth too is a separate, larger decision
 * (only relevant once LAN/remote exposure is opted into) — out of scope here.
 */
export function getApiToken(): string {
  return import.meta.env.VITE_API_TOKEN ?? ''
}
