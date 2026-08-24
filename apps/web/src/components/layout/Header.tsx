import { Activity, Boxes, Moon, Network, Radio, RefreshCw, Sun } from 'lucide-react'
import * as React from 'react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import type { SystemSummary } from '@/lib/api'
import { formatRelativeTime } from '@/lib/formatters'

export type TabType = 'overview' | 'containers' | 'ports' | 'networks'

interface HeaderProps {
  activeTab: TabType
  onTabChange: (tab: TabType) => void
  systemSummary?: SystemSummary
  isLoading?: boolean
  isFetching?: boolean
  onRefresh: () => void
}

export function Header({
  activeTab,
  onTabChange,
  systemSummary,
  isLoading = false,
  isFetching = false,
  onRefresh,
}: HeaderProps) {
  const [theme, setTheme] = React.useState<'dark' | 'light'>(() => {
    if (typeof window !== 'undefined') {
      const stored = localStorage.getItem('portwatch-theme')
      if (stored === 'dark' || stored === 'light') return stored
      if (typeof window.matchMedia === 'function') {
        return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
      }
    }
    return 'dark'
  })

  React.useEffect(() => {
    const root = document.documentElement
    if (theme === 'dark') {
      root.classList.add('dark')
    } else {
      root.classList.remove('dark')
    }
    localStorage.setItem('portwatch-theme', theme)
  }, [theme])

  const toggleTheme = () => {
    setTheme((prev) => (prev === 'dark' ? 'light' : 'dark'))
  }

  const isHealthy = systemSummary?.portwatch_status === 'ok'

  return (
    <header className="sticky top-0 z-40 w-full border-b border-border bg-background/90 backdrop-blur-md">
      <div className="mx-auto flex max-w-7xl items-center justify-between px-4 sm:px-6 h-16">
        {/* Brand & Logo */}
        <div className="flex items-center gap-3">
          <div className="flex size-9 items-center justify-center rounded-lg bg-primary text-primary-foreground shadow-xs">
            <Radio className="size-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-bold tracking-tight text-foreground text-lg">PortWatch</span>
              <span className="rounded bg-muted px-1.5 py-0.5 text-[10px] font-semibold text-muted-foreground uppercase">
                v1
              </span>
            </div>
            <p className="text-xs text-muted-foreground hidden sm:block">
              Homelab Docker & Port Monitor
            </p>
          </div>
        </div>

        {/* Navigation Tabs */}
        <nav className="flex items-center gap-1 sm:gap-2">
          <Button
            variant={activeTab === 'overview' ? 'default' : 'ghost'}
            size="sm"
            onClick={() => onTabChange('overview')}
            className="gap-1.5 text-xs sm:text-sm"
          >
            <Activity className="size-4" />
            <span>Overview</span>
          </Button>

          <Button
            variant={activeTab === 'containers' ? 'default' : 'ghost'}
            size="sm"
            onClick={() => onTabChange('containers')}
            className="gap-1.5 text-xs sm:text-sm"
          >
            <Boxes className="size-4" />
            <span>Containers</span>
            {systemSummary && (
              <Badge
                variant="secondary"
                className="ml-0.5 h-4 px-1 text-[10px] font-semibold leading-none"
              >
                {systemSummary.containers_running}
              </Badge>
            )}
          </Button>

          <Button
            variant={activeTab === 'ports' ? 'default' : 'ghost'}
            size="sm"
            onClick={() => onTabChange('ports')}
            className="gap-1.5 text-xs sm:text-sm"
          >
            <Radio className="size-4" />
            <span>Ports</span>
            {systemSummary && (
              <Badge
                variant="secondary"
                className="ml-0.5 h-4 px-1 text-[10px] font-semibold leading-none"
              >
                {systemSummary.ports_used_total}
              </Badge>
            )}
          </Button>

          <Button
            variant={activeTab === 'networks' ? 'default' : 'ghost'}
            size="sm"
            onClick={() => onTabChange('networks')}
            className="gap-1.5 text-xs sm:text-sm"
          >
            <Network className="size-4" />
            <span>Networks</span>
            {systemSummary && (
              <Badge
                variant="secondary"
                className="ml-0.5 h-4 px-1 text-[10px] font-semibold leading-none"
              >
                {systemSummary.networks_total}
              </Badge>
            )}
          </Button>
        </nav>

        {/* Right Status & Actions */}
        <div className="flex items-center gap-2">
          {/* Status Indicator */}
          <div className="hidden lg:flex items-center gap-2 rounded-full border border-border bg-card px-2.5 py-1 text-xs text-muted-foreground">
            <span
              className={`size-2 rounded-full ${
                isHealthy ? 'bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.6)]' : 'bg-amber-500'
              }`}
            />
            <span>
              {systemSummary?.collector_last_poll
                ? `Updated ${formatRelativeTime(systemSummary.collector_last_poll)}`
                : isHealthy
                  ? 'Collector Ready'
                  : 'Connecting…'}
            </span>
          </div>

          {/* Refresh Button */}
          <Button
            variant="outline"
            size="icon"
            onClick={onRefresh}
            disabled={isLoading}
            title="Refresh snapshot"
            aria-label="Refresh data"
          >
            <RefreshCw className={`size-4 ${isFetching ? 'animate-spin' : ''}`} />
          </Button>

          {/* Theme Toggle */}
          <Button
            variant="ghost"
            size="icon"
            onClick={toggleTheme}
            title={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
            aria-label="Toggle theme"
          >
            {theme === 'dark' ? <Sun className="size-4" /> : <Moon className="size-4" />}
          </Button>
        </div>
      </div>
    </header>
  )
}
