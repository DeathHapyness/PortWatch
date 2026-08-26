import { AlertCircle, RefreshCw } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { ApiError, formatProblemDetail } from '@/lib/api'

interface ErrorStateProps {
  error: unknown
  onRetry?: () => void
  title?: string
}

export function ErrorState({ error, onRetry, title = 'Failed to load data' }: ErrorStateProps) {
  const isApiError = error instanceof ApiError
  const problem = isApiError ? error.problem : null
  const status = isApiError ? error.status : null
  const message = error instanceof Error ? error.message : String(error)
  const detail = formatProblemDetail(problem?.detail)

  return (
    <Card className="border-destructive/30 bg-destructive/5 text-foreground">
      <CardContent className="flex flex-col items-center justify-center p-8 text-center">
        <div className="rounded-full bg-destructive/10 p-3 text-destructive mb-3">
          <AlertCircle className="size-6" />
        </div>
        <h3 className="text-base font-semibold text-destructive">{title}</h3>
        <p className="mt-1 max-w-md text-sm text-muted-foreground">{message}</p>

        {problem && (
          <div className="mt-3 w-full max-w-md rounded-lg border border-destructive/20 bg-background/50 p-3 text-left font-mono text-xs text-muted-foreground">
            {problem.title && (
              <div>
                <span className="font-semibold text-foreground">Problem:</span> {problem.title}
              </div>
            )}
            {detail && (
              <div className="mt-1">
                <span className="font-semibold text-foreground">Detail:</span> {detail}
              </div>
            )}
            {status && (
              <div className="mt-1">
                <span className="font-semibold text-foreground">Status code:</span> {status}
              </div>
            )}
            {problem.request_id && (
              <div className="mt-1">
                <span className="font-semibold text-foreground">Request ID:</span>{' '}
                {problem.request_id}
              </div>
            )}
          </div>
        )}

        {onRetry && (
          <Button
            variant="outline"
            size="sm"
            onClick={onRetry}
            className="mt-4 gap-2 border-destructive/30 hover:bg-destructive/10 hover:text-destructive"
          >
            <RefreshCw className="size-3.5" />
            Try again
          </Button>
        )}
      </CardContent>
    </Card>
  )
}
