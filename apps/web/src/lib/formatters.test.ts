import { describe, expect, it } from 'vitest'
import {
  formatDateTime,
  formatPort,
  formatRelativeTime,
  formatShortId,
  getPortStateBadgeInfo,
  getStatusBadgeInfo,
} from './formatters'

describe('formatShortId', () => {
  it('truncates 64-char container IDs to 12 chars by default', () => {
    expect(formatShortId('e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855')).toBe(
      'e3b0c44298fc',
    )
  })

  it('strips sha256: prefix if present', () => {
    expect(
      formatShortId('sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855'),
    ).toBe('e3b0c44298fc')
  })

  it('handles empty or short strings', () => {
    expect(formatShortId('')).toBe('')
    expect(formatShortId('abc')).toBe('abc')
  })
})

describe('formatDateTime', () => {
  it('returns dash for null or undefined', () => {
    expect(formatDateTime(null)).toBe('—')
    expect(formatDateTime(undefined)).toBe('—')
    expect(formatDateTime('')).toBe('—')
  })

  it('formats valid ISO date string', () => {
    const res = formatDateTime('2026-08-24T01:00:00Z')
    expect(res).not.toBe('—')
  })
})

describe('formatRelativeTime', () => {
  it('returns dash for empty values', () => {
    expect(formatRelativeTime(null)).toBe('—')
    expect(formatRelativeTime(undefined)).toBe('—')
  })

  it('formats relative times gracefully', () => {
    const justNow = new Date(Date.now() - 10_000).toISOString()
    expect(formatRelativeTime(justNow)).toBe('10s ago')
  })
})

describe('formatPort', () => {
  it('formats published port with host port and TCP protocol', () => {
    expect(
      formatPort({
        container_port: 80,
        host_port: 8080,
        host_ip: '0.0.0.0',
        protocol: 'tcp',
      }),
    ).toBe('8080 → 80/TCP')
  })

  it('includes specific host IP if not 0.0.0.0', () => {
    expect(
      formatPort({
        container_port: 5432,
        host_port: 5432,
        host_ip: '127.0.0.1',
        protocol: 'tcp',
      }),
    ).toBe('127.0.0.1:5432 → 5432/TCP')
  })

  it('formats container port only if not published to host', () => {
    expect(
      formatPort({
        container_port: 9000,
        host_port: null,
        host_ip: null,
        protocol: 'udp',
      }),
    ).toBe('9000/UDP')
  })
})

describe('getStatusBadgeInfo', () => {
  it('returns appropriate badge info for running status', () => {
    const info = getStatusBadgeInfo('running')
    expect(info.label).toBe('Running')
    expect(info.className).toContain('emerald')
  })

  it('returns appropriate badge info for exited status', () => {
    const info = getStatusBadgeInfo('exited')
    expect(info.label).toBe('Exited')
    expect(info.className).toContain('zinc')
  })
})

describe('getPortStateBadgeInfo', () => {
  it('returns badge info for published port state', () => {
    const info = getPortStateBadgeInfo('published')
    expect(info.label).toBe('Docker Published')
  })

  it('returns badge info for host port state', () => {
    const info = getPortStateBadgeInfo('host')
    expect(info.label).toBe('Host Process')
  })

  it('returns badge info for free port state', () => {
    const info = getPortStateBadgeInfo('free')
    expect(info.label).toBe('Free')
  })
})
