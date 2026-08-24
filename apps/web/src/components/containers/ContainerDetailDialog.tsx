import { Check, Clock, Copy, Folder, Globe, Layers, Lock, Radio, Tag, Terminal } from 'lucide-react'
import * as React from 'react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  DialogBackdrop,
  DialogClose,
  DialogHeader,
  DialogPopup,
  DialogPortal,
  DialogRoot,
  DialogTitle,
} from '@/components/ui/dialog'
import { Skeleton } from '@/components/ui/skeleton'
import { useContainerQuery } from '@/lib/queries'
import {
  formatDateTime,
  formatPort,
  formatRelativeTime,
  formatShortId,
  getStatusBadgeInfo,
} from '@/lib/formatters'

interface ContainerDetailDialogProps {
  containerId: string | null
  onClose: () => void
}

export function ContainerDetailDialog({ containerId, onClose }: ContainerDetailDialogProps) {
  const isOpen = Boolean(containerId)
  const { data: container, isLoading, error } = useContainerQuery(containerId ?? '')
  const [copied, setCopied] = React.useState(false)

  const handleCopyId = () => {
    if (!containerId) return
    navigator.clipboard.writeText(containerId)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const statusInfo = container ? getStatusBadgeInfo(container.status) : null

  return (
    <DialogRoot
      open={isOpen}
      onOpenChange={(open) => {
        if (!open) onClose()
      }}
    >
      <DialogPortal>
        <DialogBackdrop />
        <DialogPopup className="max-w-3xl">
          <DialogClose />
          <DialogHeader>
            <div className="flex items-center gap-2">
              <DialogTitle className="text-base font-semibold">
                {container ? container.name : 'Container Details'}
              </DialogTitle>
              {statusInfo && (
                <span
                  className={`inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-xs font-medium ${statusInfo.className}`}
                >
                  <span className={`size-1.5 rounded-full ${statusInfo.dotClassName}`} />
                  {statusInfo.label}
                </span>
              )}
            </div>
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              <span>ID:</span>
              <span className="font-mono text-foreground">
                {containerId ? formatShortId(containerId) : '—'}
              </span>
              <button
                type="button"
                onClick={handleCopyId}
                className="inline-flex items-center text-muted-foreground hover:text-foreground transition-colors"
                title="Copy Container ID"
                aria-label="Copy container id"
              >
                {copied ? (
                  <Check className="size-3 text-emerald-500" />
                ) : (
                  <Copy className="size-3" />
                )}
              </button>
            </div>
          </DialogHeader>

          <div className="flex-1 overflow-y-auto pr-1 py-4 space-y-5 text-sm">
            {isLoading ? (
              <div className="space-y-4">
                <Skeleton className="h-16 w-full" />
                <Skeleton className="h-24 w-full" />
                <Skeleton className="h-24 w-full" />
              </div>
            ) : error ? (
              <div className="rounded-lg border border-destructive/20 bg-destructive/5 p-4 text-xs text-destructive">
                Failed to load container details: {String(error)}
              </div>
            ) : container ? (
              <>
                {/* Basic Details Grid */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
                  <div className="rounded-lg border border-border bg-muted/20 p-3">
                    <span className="text-muted-foreground flex items-center gap-1">
                      <Layers className="size-3.5" /> Image
                    </span>
                    <p className="mt-1 font-mono font-medium text-foreground break-all">
                      {container.image}
                    </p>
                  </div>

                  <div className="rounded-lg border border-border bg-muted/20 p-3">
                    <span className="text-muted-foreground flex items-center gap-1">
                      <Clock className="size-3.5" /> Created
                    </span>
                    <p className="mt-1 font-medium text-foreground">
                      {formatDateTime(container.created_at)} (
                      {formatRelativeTime(container.created_at)})
                    </p>
                  </div>
                </div>

                {/* Command */}
                {container.command && (
                  <div>
                    <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-1.5 flex items-center gap-1.5">
                      <Terminal className="size-3.5" /> Command / Entrypoint
                    </h4>
                    <div className="rounded-lg border border-border bg-muted/40 p-2.5 font-mono text-xs text-foreground overflow-x-auto">
                      {container.command}
                    </div>
                  </div>
                )}

                {/* Ports */}
                <div>
                  <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-1.5 flex items-center gap-1.5">
                    <Radio className="size-3.5" /> Port Mappings ({container.ports.length})
                  </h4>
                  {container.ports.length === 0 ? (
                    <p className="text-xs text-muted-foreground italic">
                      No published ports for this container.
                    </p>
                  ) : (
                    <div className="flex flex-wrap gap-2">
                      {container.ports.map((p, idx) => (
                        <Badge key={idx} variant="outline" className="font-mono text-xs">
                          {formatPort(p)}
                        </Badge>
                      ))}
                    </div>
                  )}
                </div>

                {/* Networks */}
                <div>
                  <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-1.5 flex items-center gap-1.5">
                    <Globe className="size-3.5" /> Connected Networks ({container.networks.length})
                  </h4>
                  {container.networks.length === 0 ? (
                    <p className="text-xs text-muted-foreground italic">No attached networks.</p>
                  ) : (
                    <div className="flex flex-wrap gap-2">
                      {container.networks.map((net) => (
                        <Badge key={net} variant="secondary" className="text-xs">
                          {net}
                        </Badge>
                      ))}
                    </div>
                  )}
                </div>

                {/* Environment Keys (Redacted) */}
                <div>
                  <div className="flex items-center justify-between mb-1.5">
                    <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider flex items-center gap-1.5">
                      <Lock className="size-3.5" /> Environment Variables (
                      {container.env_redacted.length})
                    </h4>
                    <span className="text-[10px] text-muted-foreground italic">
                      Values redacted for security
                    </span>
                  </div>
                  {container.env_redacted.length === 0 ? (
                    <p className="text-xs text-muted-foreground italic">
                      No environment keys exposed.
                    </p>
                  ) : (
                    <div className="flex flex-wrap gap-1.5 max-h-36 overflow-y-auto rounded-lg border border-border bg-muted/20 p-2.5">
                      {container.env_redacted.map((envKey) => (
                        <span
                          key={envKey}
                          className="rounded bg-background px-1.5 py-0.5 font-mono text-[11px] text-foreground border border-border/60"
                        >
                          {envKey}
                        </span>
                      ))}
                    </div>
                  )}
                </div>

                {/* Mounts / Volumes */}
                {container.mounts && container.mounts.length > 0 && (
                  <div>
                    <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-1.5 flex items-center gap-1.5">
                      <Folder className="size-3.5" /> Mounts & Volumes ({container.mounts.length})
                    </h4>
                    <ul className="space-y-1 rounded-lg border border-border bg-muted/20 p-2.5 text-xs font-mono">
                      {container.mounts.map((mount, idx) => (
                        <li key={idx} className="text-foreground break-all">
                          {mount}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                {/* Labels */}
                {Object.keys(container.labels).length > 0 && (
                  <div>
                    <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-1.5 flex items-center gap-1.5">
                      <Tag className="size-3.5" /> Docker Labels (
                      {Object.keys(container.labels).length})
                    </h4>
                    <div className="max-h-36 overflow-y-auto rounded-lg border border-border bg-muted/20 p-2.5 space-y-1 text-xs font-mono">
                      {Object.entries(container.labels).map(([k, v]) => (
                        <div key={k} className="flex items-start gap-1">
                          <span className="font-semibold text-foreground shrink-0">{k}:</span>
                          <span className="text-muted-foreground break-all">{v}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </>
            ) : null}
          </div>

          <div className="flex justify-end pt-3 border-t border-border mt-2">
            <Button variant="outline" size="sm" onClick={onClose}>
              Close
            </Button>
          </div>
        </DialogPopup>
      </DialogPortal>
    </DialogRoot>
  )
}
