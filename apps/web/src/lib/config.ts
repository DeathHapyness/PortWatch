/**
 * Frontend-side config knobs — currently just the API bearer token (ADR-0004).
 *
 * REST calls send it as a Bearer token when configured; omitting the header
 * when it is empty preserves the loopback-only development mode. The native
 * browser WebSocket API cannot set an Authorization header during the
 * handshake, so /api/v1/events sends the same value in its first message
 * instead (see docs/adr/0006-websocket-first-message-auth.md).
 */
export function getApiToken(): string {
  return import.meta.env.VITE_API_TOKEN ?? ''
}
