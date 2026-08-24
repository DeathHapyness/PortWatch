import { Boxes, Network, Search, X } from 'lucide-react'
import * as React from 'react'

import { EmptyState } from '@/components/common/EmptyState'
import { ErrorState } from '@/components/common/ErrorState'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Skeleton } from '@/components/ui/skeleton'
import type { NetworkDetail } from '@/lib/api'
import { formatShortId } from '@/lib/formatters'
import { useNetworksQuery } from '@/lib/queries'

export function NetworksView() {
  const [searchQuery, setSearchQuery] = React.useState('')
  const { data: networks, isLoading, error, refetch } = useNetworksQuery()

  const filteredNetworks = React.useMemo(() => {
    if (!networks) return []
    if (!searchQuery) return networks

    const q = searchQuery.toLowerCase()
    return networks.filter(
      (n) =>
        n.name.toLowerCase().includes(q) ||
        n.driver.toLowerCase().includes(q) ||
        n.id.toLowerCase().includes(q) ||
        n.containers.some((c) => c.toLowerCase().includes(q)),
    )
  }, [networks, searchQuery])

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold tracking-tight text-foreground">Docker Networks</h2>
          <p className="text-xs text-muted-foreground mt-0.5">
            Network topologies, drivers, subnets, and attached containers.
          </p>
        </div>

        {/* Search */}
        <div className="relative min-w-[200px] sm:w-64">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 size-3.5 text-muted-foreground" />
          <Input
            placeholder="Search network name, driver, container…"
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
      </div>

      {/* Content */}
      {isLoading ? (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 4 }).map((_, i) => (
            <Card key={i} className="p-5">
              <Skeleton className="h-5 w-32 mb-2" />
              <Skeleton className="h-3 w-48 mb-4" />
              <Skeleton className="h-12 w-full" />
            </Card>
          ))}
        </div>
      ) : error ? (
        <ErrorState
          error={error}
          onRetry={() => refetch()}
          title="Failed to load Docker networks"
        />
      ) : filteredNetworks.length === 0 ? (
        <EmptyState
          icon={<Network className="size-8 text-muted-foreground/60" />}
          title="No networks found"
          description={
            searchQuery
              ? 'No Docker networks matched your search query.'
              : 'No Docker networks detected on the host daemon.'
          }
          actionLabel={searchQuery ? 'Clear Search' : undefined}
          onAction={() => setSearchQuery('')}
        />
      ) : (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
          {filteredNetworks.map((net) => (
            <NetworkCard key={net.id} network={net} />
          ))}
        </div>
      )}
    </div>
  )
}

function NetworkCard({ network }: { network: NetworkDetail }) {
  const shortId = formatShortId(network.id)

  return (
    <Card className="flex flex-col justify-between hover:border-border/80 transition-all shadow-xs">
      <CardContent className="p-5">
        {/* Top: Name and Driver */}
        <div className="flex items-start justify-between gap-2 mb-3">
          <div className="min-w-0 flex-1">
            <h3 className="font-semibold text-foreground text-sm truncate" title={network.name}>
              {network.name}
            </h3>
            <span className="font-mono text-[11px] text-muted-foreground">ID: {shortId}</span>
          </div>

          <Badge variant="outline" className="font-mono text-xs uppercase px-2 py-0.5 shrink-0">
            {network.driver}
          </Badge>
        </div>

        {/* Scope / Subnet / Gateway */}
        <div className="grid grid-cols-2 gap-2 text-xs mb-4 rounded-lg border border-border/60 bg-muted/20 p-2.5">
          <div>
            <span className="text-[10px] uppercase font-semibold text-muted-foreground block">
              Scope
            </span>
            <span className="font-mono text-foreground">{network.scope}</span>
          </div>

          <div>
            <span className="text-[10px] uppercase font-semibold text-muted-foreground block">
              Subnet
            </span>
            <span
              className="font-mono text-foreground truncate block"
              title={network.subnet ?? '—'}
            >
              {network.subnet ?? '—'}
            </span>
          </div>

          {network.gateway && (
            <div className="col-span-2 pt-1 border-t border-border/40">
              <span className="text-[10px] uppercase font-semibold text-muted-foreground block">
                Gateway
              </span>
              <span className="font-mono text-foreground">{network.gateway}</span>
            </div>
          )}
        </div>

        {/* Connected Containers */}
        <div>
          <div className="flex items-center justify-between text-xs text-muted-foreground mb-1.5">
            <span className="font-medium flex items-center gap-1">
              <Boxes className="size-3 text-muted-foreground" />
              Connected Containers:
            </span>
            <Badge variant="secondary" className="text-[10px] px-1.5 py-0">
              {network.containers.length}
            </Badge>
          </div>

          {network.containers.length === 0 ? (
            <span className="text-[11px] text-muted-foreground italic">
              No containers attached.
            </span>
          ) : (
            <div className="flex flex-wrap gap-1 max-h-24 overflow-y-auto">
              {network.containers.map((c) => (
                <span
                  key={c}
                  className="rounded bg-background px-2 py-0.5 font-mono text-[11px] text-foreground border border-border/60"
                >
                  {c.startsWith('/') ? c.slice(1) : c}
                </span>
              ))}
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  )
}
