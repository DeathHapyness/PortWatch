import {
  Activity,
  ArrowRight,
  Boxes,
  CheckCircle2,
  Cpu,
  Info,
  Network,
  Radio,
  Server,
  ShieldCheck,
  Zap,
} from 'lucide-react'

import { ErrorState } from '@/components/common/ErrorState'
import type { TabType } from '@/components/layout/Header'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import type { SystemSummary } from '@/lib/api'
import { formatDateTime, formatRelativeTime } from '@/lib/formatters'

interface OverviewViewProps {
  systemSummary?: SystemSummary
  isLoading: boolean
  error: unknown
  onRetry: () => void
  onNavigate: (tab: TabType) => void
}

export function OverviewView({
  systemSummary,
  isLoading,
  error,
  onRetry,
  onNavigate,
}: OverviewViewProps) {
  if (isLoading) {
    return (
      <div className="space-y-6">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <Card key={i} className="p-6">
              <Skeleton className="h-4 w-24 mb-2" />
              <Skeleton className="h-8 w-16 mb-1" />
              <Skeleton className="h-3 w-32" />
            </Card>
          ))}
        </div>
        <Card className="p-6">
          <Skeleton className="h-6 w-48 mb-4" />
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <Skeleton className="h-20 w-full" />
            <Skeleton className="h-20 w-full" />
            <Skeleton className="h-20 w-full" />
          </div>
        </Card>
      </div>
    )
  }

  if (error) {
    return (
      <ErrorState error={error} onRetry={onRetry} title="Unable to load PortWatch System Summary" />
    )
  }

  if (!systemSummary) return null

  const totalContainers = systemSummary.containers_running + systemSummary.containers_stopped

  return (
    <div className="space-y-6">
      {/* Top Banner / System Status */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 rounded-xl border border-border bg-gradient-to-r from-card to-muted/40 p-5 shadow-xs">
        <div className="flex items-start sm:items-center gap-3.5">
          <div className="flex size-10 items-center justify-center rounded-lg bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20">
            <ShieldCheck className="size-6" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-base font-semibold text-foreground">
                Docker Observer Node Active
              </h2>
              <Badge variant="success">Read-Only v1</Badge>
            </div>
            <p className="text-xs text-muted-foreground mt-0.5">
              Atomic snapshot engine deriving real-time homelab telemetry via socket proxy.
            </p>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {systemSummary.docker_version && (
            <Badge variant="outline" className="gap-1 font-mono text-xs">
              <Cpu className="size-3 text-muted-foreground" />
              Docker {systemSummary.docker_version}
            </Badge>
          )}
          {systemSummary.host_ports_enabled ? (
            <Badge variant="info" className="gap-1 text-xs">
              <Zap className="size-3" />
              Host Netprobe On
            </Badge>
          ) : (
            <Badge variant="secondary" className="gap-1 text-xs">
              <Info className="size-3 text-muted-foreground" />
              Host Netprobe Disabled
            </Badge>
          )}
        </div>
      </div>

      {/* KPI Cards Grid */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {/* Running Containers */}
        <Card
          className="cursor-pointer hover:border-emerald-500/40 transition-all"
          onClick={() => onNavigate('containers')}
        >
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-xs font-medium text-muted-foreground">
              Running Containers
            </CardTitle>
            <div className="flex size-7 items-center justify-center rounded-md bg-emerald-500/10 text-emerald-600 dark:text-emerald-400">
              <Boxes className="size-4" />
            </div>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-foreground">
              {systemSummary.containers_running}
            </div>
            <p className="text-xs text-muted-foreground mt-1 flex items-center gap-1">
              <span className="font-semibold text-foreground">{totalContainers}</span> total in
              sandbox
            </p>
          </CardContent>
        </Card>

        {/* Stopped Containers */}
        <Card
          className="cursor-pointer hover:border-border/80 transition-all"
          onClick={() => onNavigate('containers')}
        >
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-xs font-medium text-muted-foreground">
              Stopped Containers
            </CardTitle>
            <div className="flex size-7 items-center justify-center rounded-md bg-muted text-muted-foreground">
              <Boxes className="size-4" />
            </div>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-foreground">
              {systemSummary.containers_stopped}
            </div>
            <p className="text-xs text-muted-foreground mt-1">Exited or paused state</p>
          </CardContent>
        </Card>

        {/* Used Ports */}
        <Card
          className="cursor-pointer hover:border-sky-500/40 transition-all"
          onClick={() => onNavigate('ports')}
        >
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-xs font-medium text-muted-foreground">
              Active Ports
            </CardTitle>
            <div className="flex size-7 items-center justify-center rounded-md bg-sky-500/10 text-sky-600 dark:text-sky-400">
              <Radio className="size-4" />
            </div>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-foreground">
              {systemSummary.ports_used_total}
            </div>
            <p className="text-xs text-muted-foreground mt-1">Docker published & host bindings</p>
          </CardContent>
        </Card>

        {/* Total Networks */}
        <Card
          className="cursor-pointer hover:border-purple-500/40 transition-all"
          onClick={() => onNavigate('networks')}
        >
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-xs font-medium text-muted-foreground">
              Docker Networks
            </CardTitle>
            <div className="flex size-7 items-center justify-center rounded-md bg-purple-500/10 text-purple-600 dark:text-purple-400">
              <Network className="size-4" />
            </div>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-foreground">{systemSummary.networks_total}</div>
            <p className="text-xs text-muted-foreground mt-1">Bridge, host & overlays</p>
          </CardContent>
        </Card>
      </div>

      {/* Details & Architecture Info */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* System & Daemon Metadata */}
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle className="text-sm font-semibold flex items-center gap-2">
              <Server className="size-4 text-primary" />
              Daemon Telemetry & Observation Engine
            </CardTitle>
            <CardDescription className="text-xs">
              Live metadata reported by the Docker daemon collector snapshot.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <dl className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-sm">
              <div className="rounded-lg border border-border/60 bg-muted/20 p-3">
                <dt className="text-xs font-medium text-muted-foreground">PortWatch Status</dt>
                <dd className="mt-1 flex items-center gap-1.5 font-semibold text-foreground">
                  <CheckCircle2 className="size-4 text-emerald-500" />
                  {systemSummary.portwatch_status.toUpperCase()}
                </dd>
              </div>

              <div className="rounded-lg border border-border/60 bg-muted/20 p-3">
                <dt className="text-xs font-medium text-muted-foreground">Docker API Version</dt>
                <dd className="mt-1 font-mono text-sm font-semibold text-foreground">
                  {systemSummary.docker_api_version ?? '—'}
                </dd>
              </div>

              <div className="rounded-lg border border-border/60 bg-muted/20 p-3">
                <dt className="text-xs font-medium text-muted-foreground">Last Collector Poll</dt>
                <dd className="mt-1 text-xs font-medium text-foreground">
                  {systemSummary.collector_last_poll ? (
                    <>
                      <span>{formatDateTime(systemSummary.collector_last_poll)}</span>
                      <span className="text-muted-foreground ml-1.5">
                        ({formatRelativeTime(systemSummary.collector_last_poll)})
                      </span>
                    </>
                  ) : (
                    '—'
                  )}
                </dd>
              </div>

              <div className="rounded-lg border border-border/60 bg-muted/20 p-3">
                <dt className="text-xs font-medium text-muted-foreground">Host Netprobe Reading</dt>
                <dd className="mt-1 text-xs font-medium text-foreground">
                  {systemSummary.host_ports_enabled
                    ? 'Enabled (/proc/net scanning active)'
                    : 'Disabled (Docker-only mode)'}
                </dd>
              </div>
            </dl>
          </CardContent>
        </Card>

        {/* Quick Navigation Cards */}
        <Card className="flex flex-col justify-between">
          <CardHeader>
            <CardTitle className="text-sm font-semibold flex items-center gap-2">
              <Activity className="size-4 text-primary" />
              Quick Actions
            </CardTitle>
            <CardDescription className="text-xs">
              Fast navigation across your homelab infrastructure.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-2.5">
            <Button
              variant="outline"
              className="w-full justify-between text-xs"
              onClick={() => onNavigate('containers')}
            >
              <div className="flex items-center gap-2">
                <Boxes className="size-3.5" />
                <span>View Containers ({totalContainers})</span>
              </div>
              <ArrowRight className="size-3.5 text-muted-foreground" />
            </Button>

            <Button
              variant="outline"
              className="w-full justify-between text-xs"
              onClick={() => onNavigate('ports')}
            >
              <div className="flex items-center gap-2">
                <Radio className="size-3.5" />
                <span>Scan & Allocate Ports</span>
              </div>
              <ArrowRight className="size-3.5 text-muted-foreground" />
            </Button>

            <Button
              variant="outline"
              className="w-full justify-between text-xs"
              onClick={() => onNavigate('networks')}
            >
              <div className="flex items-center gap-2">
                <Network className="size-3.5" />
                <span>Inspect Docker Networks ({systemSummary.networks_total})</span>
              </div>
              <ArrowRight className="size-3.5 text-muted-foreground" />
            </Button>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
