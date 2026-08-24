import { Boxes, Clock, ExternalLink, Layers, Radio, Search, X } from 'lucide-react'
import * as React from 'react'

import { EmptyState } from '@/components/common/EmptyState'
import { ErrorState } from '@/components/common/ErrorState'
import { ContainerDetailDialog } from '@/components/containers/ContainerDetailDialog'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Skeleton } from '@/components/ui/skeleton'
import type { ContainerDetail, ContainerStatus } from '@/lib/api'
import { formatPort, formatRelativeTime, formatShortId, getStatusBadgeInfo } from '@/lib/formatters'
import { useContainersQuery } from '@/lib/queries'

export function ContainersView() {
  const [searchQuery, setSearchQuery] = React.useState('')
  const [statusFilter, setStatusFilter] = React.useState<ContainerStatus | 'all'>('all')
  const [selectedContainerId, setSelectedContainerId] = React.useState<string | null>(null)

  const {
    data: containers,
    isLoading,
    error,
    refetch,
  } = useContainersQuery(
    statusFilter === 'all'
      ? { query: searchQuery || undefined }
      : { status: statusFilter, query: searchQuery || undefined },
  )

  const filteredContainers = React.useMemo(() => {
    if (!containers) return []
    if (!searchQuery) return containers

    const q = searchQuery.toLowerCase()
    return containers.filter(
      (c) =>
        c.name.toLowerCase().includes(q) ||
        c.image.toLowerCase().includes(q) ||
        c.id.toLowerCase().includes(q),
    )
  }, [containers, searchQuery])

  const statuses: Array<{ value: ContainerStatus | 'all'; label: string }> = [
    { value: 'all', label: 'All Statuses' },
    { value: 'running', label: 'Running' },
    { value: 'exited', label: 'Exited' },
    { value: 'paused', label: 'Paused' },
    { value: 'restarting', label: 'Restarting' },
  ]

  return (
    <div className="space-y-6">
      {/* Header & Controls */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold tracking-tight text-foreground">Containers</h2>
          <p className="text-xs text-muted-foreground mt-0.5">
            Real-time status, published port mappings, and runtime metadata.
          </p>
        </div>

        {/* Filter bar */}
        <div className="flex flex-wrap items-center gap-2">
          {/* Search input */}
          <div className="relative min-w-[200px] flex-1 sm:w-64">
            <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 size-3.5 text-muted-foreground" />
            <Input
              placeholder="Filter by name, image, ID…"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-8 text-xs h-8"
            />
            {searchQuery && (
              <button
                type="button"
                onClick={() => setSearchQuery('')}
                className="absolute right-2.5 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                aria-label="Clear search"
              >
                <X className="size-3" />
              </button>
            )}
          </div>

          {/* Status buttons */}
          <div className="flex items-center gap-1 overflow-x-auto rounded-lg border border-border bg-card p-0.5 text-xs">
            {statuses.map((s) => (
              <Button
                key={s.value}
                variant={statusFilter === s.value ? 'default' : 'ghost'}
                size="xs"
                onClick={() => setStatusFilter(s.value)}
                className="h-7 text-xs font-normal"
              >
                {s.label}
              </Button>
            ))}
          </div>
        </div>
      </div>

      {/* Content Area */}
      {isLoading ? (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <Card key={i} className="p-5">
              <div className="flex justify-between items-start mb-3">
                <Skeleton className="h-5 w-32" />
                <Skeleton className="h-4 w-16" />
              </div>
              <Skeleton className="h-3 w-48 mb-2" />
              <Skeleton className="h-3 w-28 mb-4" />
              <Skeleton className="h-7 w-full" />
            </Card>
          ))}
        </div>
      ) : error ? (
        <ErrorState error={error} onRetry={() => refetch()} title="Failed to load containers" />
      ) : filteredContainers.length === 0 ? (
        <EmptyState
          icon={<Boxes className="size-8 text-muted-foreground/60" />}
          title="No containers found"
          description={
            searchQuery || statusFilter !== 'all'
              ? 'Try changing or clearing your search query or status filter.'
              : 'No Docker containers are currently present in the monitored environment.'
          }
          actionLabel={searchQuery || statusFilter !== 'all' ? 'Reset Filters' : undefined}
          onAction={() => {
            setSearchQuery('')
            setStatusFilter('all')
          }}
        />
      ) : (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
          {filteredContainers.map((container) => (
            <ContainerCard
              key={container.id}
              container={container}
              onInspect={() => setSelectedContainerId(container.id)}
            />
          ))}
        </div>
      )}

      {/* Detail Dialog */}
      <ContainerDetailDialog
        containerId={selectedContainerId}
        onClose={() => setSelectedContainerId(null)}
      />
    </div>
  )
}

function ContainerCard({
  container,
  onInspect,
}: {
  container: ContainerDetail
  onInspect: () => void
}) {
  const statusInfo = getStatusBadgeInfo(container.status)
  const shortId = formatShortId(container.id)

  return (
    <Card className="flex flex-col justify-between hover:border-border/80 transition-all shadow-xs">
      <CardContent className="p-5">
        {/* Top: Name & Status */}
        <div className="flex items-start justify-between gap-2 mb-2">
          <div className="min-w-0 flex-1">
            <h3
              className="font-semibold text-foreground text-sm truncate hover:text-primary cursor-pointer transition-colors"
              onClick={onInspect}
              title={container.name}
            >
              {container.name.startsWith('/') ? container.name.slice(1) : container.name}
            </h3>
            <span className="font-mono text-[11px] text-muted-foreground">ID: {shortId}</span>
          </div>

          <span
            className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] font-medium shrink-0 ${statusInfo.className}`}
          >
            <span className={`size-1.5 rounded-full ${statusInfo.dotClassName}`} />
            {statusInfo.label}
          </span>
        </div>

        {/* Image */}
        <div className="flex items-center gap-1.5 text-xs text-muted-foreground mb-3 truncate font-mono">
          <Layers className="size-3.5 shrink-0 text-muted-foreground/70" />
          <span className="truncate" title={container.image}>
            {container.image}
          </span>
        </div>

        {/* Ports Summary */}
        <div className="mb-3">
          <div className="flex items-center gap-1 text-xs text-muted-foreground mb-1.5">
            <Radio className="size-3" />
            <span className="font-medium text-[11px]">Ports:</span>
          </div>
          {container.ports.length === 0 ? (
            <span className="text-[11px] text-muted-foreground/70 italic">None exposed</span>
          ) : (
            <div className="flex flex-wrap gap-1">
              {container.ports.slice(0, 3).map((p, idx) => (
                <Badge key={idx} variant="outline" className="font-mono text-[10px] px-1.5 py-0">
                  {formatPort(p)}
                </Badge>
              ))}
              {container.ports.length > 3 && (
                <Badge variant="secondary" className="text-[10px] px-1 py-0">
                  +{container.ports.length - 3} more
                </Badge>
              )}
            </div>
          )}
        </div>

        {/* Networks */}
        {container.networks.length > 0 && (
          <div className="flex flex-wrap gap-1 mb-3">
            {container.networks.map((net) => (
              <span
                key={net}
                className="rounded bg-muted px-1.5 py-0.5 text-[10px] text-muted-foreground font-medium"
              >
                {net}
              </span>
            ))}
          </div>
        )}

        {/* Footer: Created time & Inspect button */}
        <div className="flex items-center justify-between pt-3 border-t border-border/60 text-xs">
          <span className="text-muted-foreground text-[11px] flex items-center gap-1">
            <Clock className="size-3" />
            {formatRelativeTime(container.created_at)}
          </span>

          <Button
            variant="ghost"
            size="xs"
            onClick={onInspect}
            className="gap-1 text-xs text-primary hover:text-primary"
          >
            <span>Inspect</span>
            <ExternalLink className="size-3" />
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}
