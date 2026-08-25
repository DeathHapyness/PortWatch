import { useQueryClient } from '@tanstack/react-query'
import * as React from 'react'

import { Header, type TabType } from '@/components/layout/Header'
import { ContainersView } from '@/components/views/ContainersView'
import { NetworksView } from '@/components/views/NetworksView'
import { OverviewView } from '@/components/views/OverviewView'
import { PortsView } from '@/components/views/PortsView'
import { portwatchQueryKeys, useSystemSummaryQuery } from '@/lib/queries'
import { useSnapshotEvents } from '@/lib/useSnapshotEvents'

export function App() {
  const [activeTab, setActiveTab] = React.useState<TabType>('overview')
  const queryClient = useQueryClient()
  useSnapshotEvents()

  const {
    data: systemSummary,
    isLoading: isSummaryLoading,
    isFetching: isSummaryFetching,
    error: summaryError,
    refetch: refetchSummary,
  } = useSystemSummaryQuery()

  const handleRefreshAll = () => {
    queryClient.invalidateQueries({ queryKey: portwatchQueryKeys.all })
  }

  return (
    <div className="min-h-screen bg-background text-foreground flex flex-col antialiased selection:bg-primary selection:text-primary-foreground">
      {/* Header with Navigation and Live Stats */}
      <Header
        activeTab={activeTab}
        onTabChange={setActiveTab}
        systemSummary={systemSummary}
        isLoading={isSummaryLoading}
        isFetching={isSummaryFetching}
        onRefresh={handleRefreshAll}
      />

      {/* Main Content Area */}
      <main className="flex-1 mx-auto w-full max-w-7xl px-4 sm:px-6 py-6 sm:py-8">
        {activeTab === 'overview' && (
          <OverviewView
            systemSummary={systemSummary}
            isLoading={isSummaryLoading}
            error={summaryError}
            onRetry={refetchSummary}
            onNavigate={setActiveTab}
          />
        )}

        {activeTab === 'containers' && <ContainersView />}

        {activeTab === 'ports' && <PortsView />}

        {activeTab === 'networks' && <NetworksView />}
      </main>

      {/* Footer */}
      <footer className="border-t border-border/80 bg-card/50 py-4 text-center text-xs text-muted-foreground">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 flex flex-col sm:flex-row items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <span className="font-semibold text-foreground">PortWatch</span>
            <span>—</span>
            <span>Homelab Observation Engine</span>
          </div>

          <div className="flex items-center gap-4 text-[11px]">
            <span className="rounded bg-muted/60 px-2 py-0.5 font-medium">
              Read-Only v1 (Safe Mode)
            </span>
            <span>Local dev environment</span>
          </div>
        </div>
      </footer>
    </div>
  )
}

export default App
