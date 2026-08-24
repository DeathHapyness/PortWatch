import { Boxes, Check, Copy, Radio, Search, Server, Sparkles, X } from 'lucide-react'
import * as React from 'react'

import { EmptyState } from '@/components/common/EmptyState'
import { ErrorState } from '@/components/common/ErrorState'
import { AvailablePortsFinder } from '@/components/ports/AvailablePortsFinder'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Skeleton } from '@/components/ui/skeleton'
import type { PortState } from '@/lib/api'
import { getPortStateBadgeInfo } from '@/lib/formatters'
import { usePortsQuery } from '@/lib/queries'

export function PortsView() {
  const [stateFilter, setStateFilter] = React.useState<PortState | 'all'>('all')
  const [searchQuery, setSearchQuery] = React.useState('')
  const [rangePreset, setRangePreset] = React.useState<'services' | 'all'>('services')
  const [showAllocator, setShowAllocator] = React.useState<boolean>(false)
  const [copiedPort, setCopiedPort] = React.useState<number | null>(null)

  const activeRange = React.useMemo(() => {
    if (rangePreset === 'services') return { start: 1, end: 10000 }
    return { start: 1, end: 65535 }
  }, [rangePreset])

  const {
    data: portsData,
    isLoading,
    error,
    refetch,
  } = usePortsQuery({
    state: stateFilter === 'all' ? undefined : stateFilter,
    rangeStart: activeRange.start,
    rangeEnd: activeRange.end,
  })

  const filteredEntries = React.useMemo(() => {
    if (!portsData?.entries) return []
    if (!searchQuery) return portsData.entries

    const q = searchQuery.toLowerCase()
    return portsData.entries.filter(
      (entry) =>
        String(entry.port).includes(q) ||
        (entry.owner && entry.owner.toLowerCase().includes(q)) ||
        entry.state.toLowerCase().includes(q) ||
        entry.protocol.toLowerCase().includes(q),
    )
  }, [portsData, searchQuery])

  const handleCopy = (port: number) => {
    navigator.clipboard.writeText(String(port))
    setCopiedPort(port)
    setTimeout(() => setCopiedPort(null), 2000)
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold tracking-tight text-foreground">Port Matrix</h2>
          <p className="text-xs text-muted-foreground mt-0.5">
            Observing active Docker container ports, host process bindings, and free ranges.
          </p>
        </div>

        <Button
          variant={showAllocator ? 'default' : 'outline'}
          size="sm"
          onClick={() => setShowAllocator(!showAllocator)}
          className="gap-1.5 text-xs"
        >
          <Sparkles className="size-3.5" />
          {showAllocator ? 'Hide Port Allocator' : 'Free Port Allocator'}
        </Button>
      </div>

      {/* Available Ports Tool Collapsible */}
      {showAllocator && <AvailablePortsFinder />}

      {/* Filter and Search Bar */}
      <div className="flex flex-col gap-3 rounded-xl border border-border bg-card p-4 shadow-xs">
        <div className="flex flex-wrap items-center justify-between gap-3">
          {/* Search Input */}
          <div className="relative min-w-[200px] flex-1 sm:max-w-xs">
            <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 size-3.5 text-muted-foreground" />
            <Input
              placeholder="Search port number, owner…"
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

          {/* State Filter Buttons */}
          <div className="flex items-center gap-1 overflow-x-auto rounded-lg border border-border bg-muted/30 p-0.5 text-xs">
            <Button
              variant={stateFilter === 'all' ? 'default' : 'ghost'}
              size="xs"
              onClick={() => setStateFilter('all')}
              className="h-7 text-xs font-normal"
            >
              All States
            </Button>
            <Button
              variant={stateFilter === 'published' ? 'default' : 'ghost'}
              size="xs"
              onClick={() => setStateFilter('published')}
              className="h-7 text-xs font-normal"
            >
              Published
            </Button>
            <Button
              variant={stateFilter === 'host' ? 'default' : 'ghost'}
              size="xs"
              onClick={() => setStateFilter('host')}
              className="h-7 text-xs font-normal"
            >
              Host Processes
            </Button>
            <Button
              variant={stateFilter === 'free' ? 'default' : 'ghost'}
              size="xs"
              onClick={() => setStateFilter('free')}
              className="h-7 text-xs font-normal"
            >
              Free
            </Button>
          </div>

          {/* Range Presets */}
          <div className="flex items-center gap-1 text-xs">
            <span className="text-[11px] text-muted-foreground mr-1">Range:</span>
            <Button
              variant={rangePreset === 'services' ? 'secondary' : 'ghost'}
              size="xs"
              onClick={() => setRangePreset('services')}
              className="h-7 text-xs"
            >
              1–10,000
            </Button>
            <Button
              variant={rangePreset === 'all' ? 'secondary' : 'ghost'}
              size="xs"
              onClick={() => setRangePreset('all')}
              className="h-7 text-xs"
            >
              1–65,535
            </Button>
          </div>
        </div>
      </div>

      {/* Ports Table */}
      {isLoading ? (
        <Card className="p-4 space-y-3">
          <Skeleton className="h-6 w-full" />
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-10 w-full" />
        </Card>
      ) : error ? (
        <ErrorState error={error} onRetry={() => refetch()} title="Failed to load ports matrix" />
      ) : filteredEntries.length === 0 ? (
        <EmptyState
          icon={<Radio className="size-8 text-muted-foreground/60" />}
          title="No ports matched the criteria"
          description="No port allocations found matching your current range, state filter, or search query."
          actionLabel="Reset Filters"
          onAction={() => {
            setStateFilter('all')
            setSearchQuery('')
            setRangePreset('services')
          }}
        />
      ) : (
        <Card className="overflow-hidden shadow-xs">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="border-b border-border bg-muted/40 text-muted-foreground font-medium uppercase tracking-wider text-[10px]">
                <tr>
                  <th className="px-4 py-3">Port</th>
                  <th className="px-4 py-3">Protocol</th>
                  <th className="px-4 py-3">State</th>
                  <th className="px-4 py-3">Owner / Service</th>
                  <th className="px-4 py-3 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border/60">
                {filteredEntries.map((entry) => {
                  const stateInfo = getPortStateBadgeInfo(entry.state)
                  return (
                    <tr
                      key={`${entry.port}-${entry.protocol}`}
                      className="hover:bg-muted/20 transition-colors"
                    >
                      <td className="px-4 py-3 font-mono font-bold text-foreground">
                        {entry.port}
                      </td>
                      <td className="px-4 py-3 font-mono uppercase text-muted-foreground">
                        <Badge variant="outline" className="font-mono text-[10px] px-1.5 py-0">
                          {entry.protocol}
                        </Badge>
                      </td>
                      <td className="px-4 py-3">
                        <span
                          className={`inline-flex items-center rounded-md border px-2 py-0.5 text-[11px] font-medium ${stateInfo.className}`}
                        >
                          {stateInfo.label}
                        </span>
                      </td>
                      <td className="px-4 py-3 font-mono text-foreground font-medium">
                        {entry.owner ? (
                          <span className="flex items-center gap-1.5">
                            {entry.state === 'published' ? (
                              <Boxes className="size-3.5 text-sky-500" />
                            ) : (
                              <Server className="size-3.5 text-purple-500" />
                            )}
                            {entry.owner}
                          </span>
                        ) : (
                          <span className="text-muted-foreground italic text-[11px]">
                            Unassigned
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-right">
                        <Button
                          variant="ghost"
                          size="xs"
                          onClick={() => handleCopy(entry.port)}
                          title="Copy Port"
                          className="h-6 gap-1 text-[11px] text-muted-foreground hover:text-foreground"
                        >
                          {copiedPort === entry.port ? (
                            <>
                              <Check className="size-3 text-emerald-500" />
                              <span className="text-emerald-500">Copied</span>
                            </>
                          ) : (
                            <>
                              <Copy className="size-3" />
                              <span>Copy</span>
                            </>
                          )}
                        </Button>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
          <div className="border-t border-border bg-muted/20 px-4 py-2 text-[11px] text-muted-foreground flex justify-between items-center">
            <span>Showing {filteredEntries.length} port entries</span>
            <span>
              Range [{portsData?.range_start}–{portsData?.range_end}]
            </span>
          </div>
        </Card>
      )}
    </div>
  )
}
