export type ContainerStatus = 'running' | 'exited' | 'paused' | 'restarting' | 'dead' | 'created'

export type PortProtocol = 'tcp' | 'udp'
export type PortState = 'host' | 'published' | 'free'

export interface PublishedPort {
  container_port: number
  host_port: number | null
  host_ip: string | null
  protocol: PortProtocol
}

export interface ContainerDetail {
  id: string
  name: string
  image: string
  status: ContainerStatus
  health: string | null
  created_at: string
  networks: string[]
  ports: PublishedPort[]
  labels: Record<string, string>
  command: string | null
  env_redacted: string[]
  mounts: string[]
}

export interface NetworkDetail {
  id: string
  name: string
  driver: string
  scope: string
  containers: string[]
  subnet: string | null
  gateway: string | null
}

export interface PortEntry {
  port: number
  protocol: PortProtocol
  state: PortState
  owner: string | null
}

export interface PortsResponse {
  range_start: number
  range_end: number
  entries: PortEntry[]
}

export interface SystemSummary {
  portwatch_status: string
  docker_version: string | null
  docker_api_version: string | null
  containers_running: number
  containers_stopped: number
  networks_total: number
  ports_used_total: number
  ports_free_sample: number
  host_ports_enabled: boolean
  collector_last_poll: string | null
}

export interface ProblemDetail {
  type: string
  title: string
  status: number
  detail: string | null
  request_id: string | null
}

export class ApiError extends Error {
  readonly status: number
  readonly problem: ProblemDetail | null

  constructor(status: number, problem: ProblemDetail | null) {
    super(problem?.detail ?? problem?.title ?? `API request failed with status ${status}`)
    this.name = 'ApiError'
    this.status = status
    this.problem = problem
  }
}

export interface ContainerFilters {
  status?: ContainerStatus
  network?: string
  label?: string
  query?: string
}

export interface PortFilters {
  state?: PortState
  rangeStart?: number
  rangeEnd?: number
}

export interface AvailablePortFilters {
  rangeStart?: number
  rangeEnd?: number
  limit?: number
}

function queryString(values: Record<string, string | number | undefined>): string {
  const params = new URLSearchParams()
  for (const [key, value] of Object.entries(values)) {
    if (value !== undefined) params.set(key, String(value))
  }
  const serialized = params.toString()
  return serialized ? `?${serialized}` : ''
}

async function readProblem(response: Response): Promise<ProblemDetail | null> {
  const mediaType = response.headers.get('content-type')?.split(';', 1)[0].trim().toLowerCase()
  if (mediaType !== 'application/json' && !mediaType?.endsWith('+json')) return null

  try {
    return (await response.json()) as ProblemDetail
  } catch {
    return null
  }
}

async function get<T>(path: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(path, {
    headers: { Accept: 'application/json, application/problem+json' },
    signal,
  })

  if (!response.ok) throw new ApiError(response.status, await readProblem(response))
  return (await response.json()) as T
}

export const api = {
  systemSummary: (signal?: AbortSignal) => get<SystemSummary>('/api/v1/system/summary', signal),

  containers: (filters: ContainerFilters = {}, signal?: AbortSignal) =>
    get<ContainerDetail[]>(
      `/api/v1/containers${queryString({
        status_filter: filters.status,
        network: filters.network,
        label: filters.label,
        q: filters.query,
      })}`,
      signal,
    ),

  container: (id: string, signal?: AbortSignal) =>
    get<ContainerDetail>(`/api/v1/containers/${encodeURIComponent(id)}`, signal),

  networks: (signal?: AbortSignal) => get<NetworkDetail[]>('/api/v1/networks', signal),

  network: (id: string, signal?: AbortSignal) =>
    get<NetworkDetail>(`/api/v1/networks/${encodeURIComponent(id)}`, signal),

  ports: (filters: PortFilters = {}, signal?: AbortSignal) =>
    get<PortsResponse>(
      `/api/v1/ports${queryString({
        state: filters.state,
        range_start: filters.rangeStart,
        range_end: filters.rangeEnd,
      })}`,
      signal,
    ),

  availablePorts: (filters: AvailablePortFilters = {}, signal?: AbortSignal) =>
    get<PortsResponse>(
      `/api/v1/ports/available${queryString({
        range_start: filters.rangeStart,
        range_end: filters.rangeEnd,
        limit: filters.limit,
      })}`,
      signal,
    ),
}
