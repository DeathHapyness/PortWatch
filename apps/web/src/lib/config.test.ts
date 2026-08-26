import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { getApiToken, setApiToken } from './config'

describe('getApiToken / setApiToken', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  afterEach(() => {
    localStorage.clear()
    vi.unstubAllEnvs()
  })

  it('returns an empty string when nothing is configured', () => {
    expect(getApiToken()).toBe('')
  })

  it('falls back to VITE_API_TOKEN when nothing is stored', () => {
    vi.stubEnv('VITE_API_TOKEN', 'env-token')

    expect(getApiToken()).toBe('env-token')
  })

  it('setApiToken persists a token that getApiToken then returns', () => {
    setApiToken('stored-token')

    expect(getApiToken()).toBe('stored-token')
    expect(localStorage.getItem('portwatch-api-token')).toBe('stored-token')
  })

  it('a stored token takes precedence over VITE_API_TOKEN', () => {
    vi.stubEnv('VITE_API_TOKEN', 'env-token')
    setApiToken('stored-token')

    expect(getApiToken()).toBe('stored-token')
  })

  it('trims whitespace around a saved token', () => {
    setApiToken('  padded-token  ')

    expect(getApiToken()).toBe('padded-token')
  })

  it('setApiToken with an empty string clears any stored token', () => {
    setApiToken('stored-token')
    setApiToken('')

    expect(localStorage.getItem('portwatch-api-token')).toBeNull()
    expect(getApiToken()).toBe('')
  })

  it('setApiToken with only whitespace clears any stored token', () => {
    setApiToken('stored-token')
    setApiToken('   ')

    expect(localStorage.getItem('portwatch-api-token')).toBeNull()
  })

  it('clearing a stored token falls back to VITE_API_TOKEN again', () => {
    vi.stubEnv('VITE_API_TOKEN', 'env-token')
    setApiToken('stored-token')
    setApiToken('')

    expect(getApiToken()).toBe('env-token')
  })

  it('getApiToken degrades gracefully when localStorage.getItem throws', () => {
    const spy = vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new DOMException('blocked', 'SecurityError')
    })

    expect(() => getApiToken()).not.toThrow()
    expect(getApiToken()).toBe('')

    spy.mockRestore()
  })

  it('setApiToken degrades gracefully when localStorage.setItem throws', () => {
    const spy = vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new DOMException('quota exceeded', 'QuotaExceededError')
    })

    expect(() => setApiToken('stored-token')).not.toThrow()

    spy.mockRestore()
  })
})
