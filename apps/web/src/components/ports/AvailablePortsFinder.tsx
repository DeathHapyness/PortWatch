import { Check, Copy, Radio, Sparkles } from 'lucide-react'
import * as React from 'react'

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Skeleton } from '@/components/ui/skeleton'
import { useAvailablePortsQuery } from '@/lib/queries'

export function AvailablePortsFinder() {
  const [rangeStart, setRangeStart] = React.useState<number>(8000)
  const [rangeEnd, setRangeEnd] = React.useState<number>(9000)
  const [limit, setLimit] = React.useState<number>(10)
  const [copiedPort, setCopiedPort] = React.useState<number | null>(null)

  const { data, isLoading, error } = useAvailablePortsQuery({
    rangeStart,
    rangeEnd,
    limit,
  })

  const handleCopy = (port: number) => {
    navigator.clipboard.writeText(String(port))
    setCopiedPort(port)
    setTimeout(() => setCopiedPort(null), 2000)
  }

  return (
    <Card className="border-border/80 shadow-xs">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="flex size-7 items-center justify-center rounded-md bg-emerald-500/10 text-emerald-600 dark:text-emerald-400">
              <Sparkles className="size-4" />
            </div>
            <div>
              <CardTitle className="text-sm font-semibold">Available Port Allocator</CardTitle>
              <CardDescription className="text-xs">
                Find verified free ports to assign to new homelab services and containers.
              </CardDescription>
            </div>
          </div>
        </div>
      </CardHeader>

      <CardContent className="space-y-4">
        {/* Controls */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <div>
            <label className="text-[11px] font-medium text-muted-foreground block mb-1">
              Range Start
            </label>
            <Input
              type="number"
              min={1}
              max={65535}
              value={rangeStart}
              onChange={(e) => setRangeStart(Number(e.target.value) || 1)}
              className="h-8 text-xs font-mono"
            />
          </div>

          <div>
            <label className="text-[11px] font-medium text-muted-foreground block mb-1">
              Range End
            </label>
            <Input
              type="number"
              min={1}
              max={65535}
              value={rangeEnd}
              onChange={(e) => setRangeEnd(Number(e.target.value) || 65535)}
              className="h-8 text-xs font-mono"
            />
          </div>

          <div>
            <label className="text-[11px] font-medium text-muted-foreground block mb-1">
              Number of Free Ports
            </label>
            <Input
              type="number"
              min={1}
              max={100}
              value={limit}
              onChange={(e) => setLimit(Number(e.target.value) || 10)}
              className="h-8 text-xs font-mono"
            />
          </div>
        </div>

        {/* Results */}
        {isLoading ? (
          <div className="flex flex-wrap gap-2 pt-2">
            {Array.from({ length: 8 }).map((_, i) => (
              <Skeleton key={i} className="h-8 w-20" />
            ))}
          </div>
        ) : error ? (
          <div className="rounded-lg border border-destructive/20 bg-destructive/5 p-3 text-xs text-destructive">
            Failed to query available ports: {String(error)}
          </div>
        ) : data && data.entries.length > 0 ? (
          <div className="space-y-2 pt-1">
            <span className="text-xs text-muted-foreground">
              Found <strong className="text-foreground">{data.entries.length}</strong> free ports in
              range [{data.range_start}–{data.range_end}]:
            </span>
            <div className="flex flex-wrap gap-2">
              {data.entries.map((entry) => (
                <button
                  key={`${entry.port}-${entry.protocol}`}
                  type="button"
                  onClick={() => handleCopy(entry.port)}
                  className="group inline-flex items-center gap-1.5 rounded-lg border border-emerald-500/30 bg-emerald-500/5 px-2.5 py-1 text-xs font-mono font-medium text-emerald-700 dark:text-emerald-400 hover:bg-emerald-500/15 hover:border-emerald-500/50 transition-all cursor-pointer"
                  title="Click to copy port"
                >
                  <Radio className="size-3 text-emerald-500" />
                  <span>{entry.port}</span>
                  {copiedPort === entry.port ? (
                    <Check className="size-3 text-emerald-600 dark:text-emerald-300" />
                  ) : (
                    <Copy className="size-3 opacity-40 group-hover:opacity-100 transition-opacity" />
                  )}
                </button>
              ))}
            </div>
          </div>
        ) : (
          <p className="text-xs text-muted-foreground italic pt-1">
            No free ports found in the specified range.
          </p>
        )}
      </CardContent>
    </Card>
  )
}
