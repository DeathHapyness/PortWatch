import * as React from 'react'

import { Button } from '@/components/ui/button'
import {
  DialogBackdrop,
  DialogClose,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogPopup,
  DialogPortal,
  DialogRoot,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { getApiToken, setApiToken } from '@/lib/config'

interface ApiTokenDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
}

/**
 * Lets the operator enter the API bearer token at runtime instead of the
 * backend needing it baked into the production build. See lib/config.ts for
 * why: a build-time VITE_API_TOKEN is readable in plain text by anyone who
 * loads the page. The value entered here goes only to this browser's
 * localStorage — never into a file another visitor could read.
 */
export function ApiTokenDialog({ open, onOpenChange }: ApiTokenDialogProps) {
  // Header.tsx remounts this component (via a `key` bump) each time it
  // opens the dialog, so this lazy initializer re-reads the current token
  // fresh on every open — no effect needed to keep it in sync.
  const [value, setValue] = React.useState(() => getApiToken())

  const handleSave = () => {
    setApiToken(value)
    onOpenChange(false)
    // A full reload is simpler and more robust than threading a
    // token-changed event through TanStack Query and the WebSocket hook —
    // both pick up the new token cleanly on the next request/connection.
    window.location.reload()
  }

  const handleClear = () => {
    setApiToken('')
    setValue('')
  }

  return (
    <DialogRoot open={open} onOpenChange={onOpenChange}>
      <DialogPortal>
        <DialogBackdrop />
        <DialogPopup className="max-w-md">
          <DialogClose />
          <DialogHeader>
            <DialogTitle>API Token</DialogTitle>
            <DialogDescription>
              Sent as a bearer token on every request. Stored only in this browser — never in a file
              another visitor could read. Leave empty if this backend has no token configured.
            </DialogDescription>
          </DialogHeader>

          <div className="py-4">
            <Input
              type="password"
              autoComplete="off"
              spellCheck={false}
              placeholder="Paste your PORTWATCH_API_TOKEN"
              value={value}
              onChange={(event) => setValue(event.target.value)}
              aria-label="API token"
            />
          </div>

          <DialogFooter>
            <Button variant="ghost" onClick={handleClear}>
              Clear
            </Button>
            <Button onClick={handleSave}>Save &amp; reload</Button>
          </DialogFooter>
        </DialogPopup>
      </DialogPortal>
    </DialogRoot>
  )
}
