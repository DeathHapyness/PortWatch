import { useQuery } from '@tanstack/react-query'
import { Button } from '@/components/ui/button'

type SystemSummary = { portwatch_status: string; docker_version: string | null }

async function fetchSystemSummary(): Promise<SystemSummary> {
  const res = await fetch('/api/v1/system/summary')
  if (!res.ok) throw new Error(`backend returned ${res.status}`)
  return res.json()
}

function App() {
  const { data, error, isLoading, refetch } = useQuery({
    queryKey: ['system-summary'],
    queryFn: fetchSystemSummary,
  })

  return (
    <main className="flex min-h-svh flex-col items-center justify-center gap-4 bg-background text-foreground">
      <h1 className="text-2xl font-semibold">PortWatch</h1>
      <p className="text-muted-foreground">
        Foundation check — frontend talking to the backend through the dev proxy.
      </p>
      <p className="font-mono text-sm">
        {isLoading && 'checking /api/v1/system/summary…'}
        {error && `error: ${(error as Error).message} (is the backend running?)`}
        {data && `status: ${data.portwatch_status} · docker: ${data.docker_version}`}
      </p>
      <Button onClick={() => refetch()}>Recheck</Button>
    </main>
  )
}

export default App
