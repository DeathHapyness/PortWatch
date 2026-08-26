import { fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiTokenDialog } from './ApiTokenDialog'
import { getApiToken, setApiToken } from '@/lib/config'

describe('ApiTokenDialog', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.stubGlobal('location', { ...window.location, reload: vi.fn() })
  })

  afterEach(() => {
    localStorage.clear()
    vi.unstubAllGlobals()
  })

  it('renders nothing accessible when closed', () => {
    render(<ApiTokenDialog open={false} onOpenChange={vi.fn()} />)

    expect(screen.queryByLabelText('API token')).not.toBeInTheDocument()
  })

  it('seeds the field with the currently configured token when opened', () => {
    setApiToken('existing-token')

    render(<ApiTokenDialog open onOpenChange={vi.fn()} />)

    expect(screen.getByLabelText('API token')).toHaveValue('existing-token')
  })

  it('saves the entered token, closes, and reloads the page', () => {
    const onOpenChange = vi.fn()
    render(<ApiTokenDialog open onOpenChange={onOpenChange} />)

    fireEvent.change(screen.getByLabelText('API token'), { target: { value: 'new-token' } })
    fireEvent.click(screen.getByRole('button', { name: /save/i }))

    expect(getApiToken()).toBe('new-token')
    expect(onOpenChange).toHaveBeenCalledWith(false)
    expect(window.location.reload).toHaveBeenCalledOnce()
  })

  it('clears the stored token without closing the dialog', () => {
    setApiToken('existing-token')
    const onOpenChange = vi.fn()

    render(<ApiTokenDialog open onOpenChange={onOpenChange} />)
    fireEvent.click(screen.getByRole('button', { name: /clear/i }))

    expect(getApiToken()).toBe('')
    expect(screen.getByLabelText('API token')).toHaveValue('')
    expect(onOpenChange).not.toHaveBeenCalled()
    expect(window.location.reload).not.toHaveBeenCalled()
  })
})
