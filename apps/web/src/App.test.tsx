import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import App from './App'

const fetchMock = vi.fn<typeof fetch>()

function renderApp() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
    },
  })

  return render(
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>,
  )
}

function jsonResponse(body: unknown, init?: ResponseInit): Response {
  return new Response(JSON.stringify(body), {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  })
}

const mockSystemSummary = {
  portwatch_status: 'ok',
  docker_version: '28.0.1',
  docker_api_version: '1.48',
  containers_running: 3,
  containers_stopped: 1,
  networks_total: 2,
  ports_used_total: 4,
  ports_free_sample: 65531,
  host_ports_enabled: true,
  collector_last_poll: '2026-08-24T01:00:00Z',
}

const mockContainers = [
  {
    id: 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
    name: '/portwatch-fixture-web',
    image: 'nginx:alpine',
    status: 'running',
    health: 'healthy',
    created_at: '2026-08-24T00:50:00Z',
    networks: ['bridge'],
    ports: [
      {
        container_port: 80,
        host_port: 8080,
        host_ip: '0.0.0.0',
        protocol: 'tcp',
      },
    ],
    labels: { 'portwatch.env': 'dev-sandbox' },
    command: 'nginx -g "daemon off;"',
    env_redacted: ['PATH', 'NGINX_VERSION'],
    mounts: [],
  },
]

const mockPorts = {
  range_start: 1,
  range_end: 10000,
  entries: [
    {
      port: 8080,
      protocol: 'tcp',
      state: 'published',
      owner: 'portwatch-fixture-web',
    },
  ],
}

const mockNetworks = [
  {
    id: 'a1b2c3d4e5f6',
    name: 'custom-bridge-net',
    driver: 'bridge',
    scope: 'local',
    containers: ['portwatch-fixture-web'],
    subnet: '172.17.0.0/16',
    gateway: '172.17.0.1',
  },
]

describe('App Dashboard', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', fetchMock)
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    fetchMock.mockReset()
    localStorage.clear()
  })

  it('renders the dashboard with system summary data', async () => {
    fetchMock.mockImplementation(async (input) => {
      const url = String(input)
      if (url.includes('/api/v1/system/summary')) return jsonResponse(mockSystemSummary)
      return jsonResponse({}, { status: 404 })
    })

    renderApp()

    expect(screen.getAllByText('PortWatch').length).toBeGreaterThanOrEqual(1)
    expect(await screen.findByText('Docker 28.0.1')).toBeInTheDocument()
    expect(screen.getByText('Running Containers')).toBeInTheDocument()
    expect(screen.getAllByText('3').length).toBeGreaterThanOrEqual(1)
    expect(screen.getByText('Stopped Containers')).toBeInTheDocument()
    expect(screen.getAllByText('1').length).toBeGreaterThanOrEqual(1)
  })

  it('switches between navigation tabs and renders containers view', async () => {
    fetchMock.mockImplementation(async (input) => {
      const url = String(input)
      if (url.includes('/api/v1/system/summary')) return jsonResponse(mockSystemSummary)
      if (url.includes('/api/v1/containers')) return jsonResponse(mockContainers)
      return jsonResponse({}, { status: 404 })
    })

    renderApp()

    await screen.findByText('Docker 28.0.1')

    const nav = screen.getByRole('navigation')
    const containersTab = within(nav).getByRole('button', { name: /containers/i })
    fireEvent.click(containersTab)

    expect(await screen.findByText('portwatch-fixture-web')).toBeInTheDocument()
    expect(screen.getByText('nginx:alpine')).toBeInTheDocument()
    expect(screen.getByText('8080 → 80/TCP')).toBeInTheDocument()
  })

  it('groups containers by Docker Compose stack when toggled on', async () => {
    // PortWatch never persists its own state (see CLAUDE.md) — "category"
    // has to come from Docker itself. com.docker.compose.project is the
    // grouping key ContainersView uses; a container without it falls into
    // the "Standalone" bucket instead of being dropped.
    const mockGroupedContainers = [
      {
        id: 'a'.repeat(64),
        name: '/media-jellyfin',
        image: 'jellyfin/jellyfin:latest',
        status: 'running',
        health: null,
        created_at: '2026-08-24T00:50:00Z',
        networks: ['bridge'],
        ports: [],
        labels: { 'com.docker.compose.project': 'media-server' },
        command: null,
        env_redacted: [],
        mounts: [],
      },
      {
        id: 'b'.repeat(64),
        name: '/media-sonarr',
        image: 'linuxserver/sonarr:latest',
        status: 'running',
        health: null,
        created_at: '2026-08-24T00:50:00Z',
        networks: ['bridge'],
        ports: [],
        labels: { 'com.docker.compose.project': 'media-server' },
        command: null,
        env_redacted: [],
        mounts: [],
      },
      {
        id: 'c'.repeat(64),
        name: '/adhoc-debug-shell',
        image: 'alpine:latest',
        status: 'running',
        health: null,
        created_at: '2026-08-24T00:50:00Z',
        networks: ['bridge'],
        ports: [],
        labels: {},
        command: null,
        env_redacted: [],
        mounts: [],
      },
    ]

    fetchMock.mockImplementation(async (input) => {
      const url = String(input)
      if (url.includes('/api/v1/system/summary')) return jsonResponse(mockSystemSummary)
      if (url.includes('/api/v1/containers')) return jsonResponse(mockGroupedContainers)
      return jsonResponse({}, { status: 404 })
    })

    renderApp()

    await screen.findByText('Docker 28.0.1')

    const nav = screen.getByRole('navigation')
    fireEvent.click(within(nav).getByRole('button', { name: /containers/i }))

    // Flat by default — no group headers, all three cards visible together.
    expect(await screen.findByText('media-jellyfin')).toBeInTheDocument()
    expect(screen.getByText('media-sonarr')).toBeInTheDocument()
    expect(screen.getByText('adhoc-debug-shell')).toBeInTheDocument()
    expect(screen.queryByText('media-server')).not.toBeInTheDocument()
    expect(screen.queryByText('Standalone')).not.toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Group by Stack' }))

    // Grouped: one header per compose project, the label-less container
    // under "Standalone".
    expect(await screen.findByText('media-server')).toBeInTheDocument()
    expect(screen.getByText('Standalone')).toBeInTheDocument()
    expect(screen.getByText('media-jellyfin')).toBeInTheDocument()
    expect(screen.getByText('media-sonarr')).toBeInTheDocument()
    expect(screen.getByText('adhoc-debug-shell')).toBeInTheDocument()

    // Toggling off returns to the flat view.
    fireEvent.click(screen.getByRole('button', { name: 'Grouped by Stack' }))
    expect(screen.queryByText('Standalone')).not.toBeInTheDocument()
  })

  it('switches to ports tab and displays port matrix', async () => {
    fetchMock.mockImplementation(async (input) => {
      const url = String(input)
      if (url.includes('/api/v1/system/summary')) return jsonResponse(mockSystemSummary)
      if (url.includes('/api/v1/ports')) return jsonResponse(mockPorts)
      return jsonResponse({}, { status: 404 })
    })

    renderApp()

    await screen.findByText('Docker 28.0.1')

    const nav = screen.getByRole('navigation')
    const portsTab = within(nav).getByRole('button', { name: /ports/i })
    fireEvent.click(portsTab)

    expect(await screen.findByText('Port Matrix')).toBeInTheDocument()
    expect(await screen.findByText('8080')).toBeInTheDocument()
    expect(screen.getByText('Docker Published')).toBeInTheDocument()
  })

  it('filters ports by Free state using the available-ports endpoint, not the plain ports list', async () => {
    // Regression test: the Collector's snapshot only ever records ports it
    // actually observed occupied (published/host) — GET /api/v1/ports
    // never returns a "free" entry, no matter the state filter, because
    // the Collector never stores one. "Free" only exists as a computed
    // result from GET /api/v1/ports/available. The Free filter button used
    // to query the former, which meant it always rendered zero results
    // regardless of what was actually free — see PortsView.tsx.
    const mockAvailablePorts = {
      range_start: 1,
      range_end: 10000,
      entries: [
        { port: 9000, protocol: 'tcp', state: 'free', owner: null },
        { port: 9001, protocol: 'tcp', state: 'free', owner: null },
      ],
    }

    fetchMock.mockImplementation(async (input) => {
      const url = String(input)
      if (url.includes('/api/v1/system/summary')) return jsonResponse(mockSystemSummary)
      if (url.includes('/api/v1/ports/available')) return jsonResponse(mockAvailablePorts)
      if (url.includes('/api/v1/ports')) return jsonResponse(mockPorts)
      return jsonResponse({}, { status: 404 })
    })

    renderApp()

    await screen.findByText('Docker 28.0.1')

    const nav = screen.getByRole('navigation')
    const portsTab = within(nav).getByRole('button', { name: /ports/i })
    fireEvent.click(portsTab)

    // "All States" (default) shows the observed/published port.
    expect(await screen.findByText('8080')).toBeInTheDocument()

    const freeButton = screen.getByRole('button', { name: 'Free' })
    fireEvent.click(freeButton)

    expect(await screen.findByText('9000')).toBeInTheDocument()
    expect(screen.getByText('9001')).toBeInTheDocument()
    expect(screen.queryByText('No ports matched the criteria')).not.toBeInTheDocument()
    // The observed port (8080) isn't a "free" entry — shouldn't reappear
    // once filtered to Free.
    expect(screen.queryByText('8080')).not.toBeInTheDocument()
  })

  it('switches to networks tab and displays docker networks', async () => {
    fetchMock.mockImplementation(async (input) => {
      const url = String(input)
      if (url.includes('/api/v1/system/summary')) return jsonResponse(mockSystemSummary)
      if (url.includes('/api/v1/networks')) return jsonResponse(mockNetworks)
      return jsonResponse({}, { status: 404 })
    })

    renderApp()

    await screen.findByText('Docker 28.0.1')

    const nav = screen.getByRole('navigation')
    const networksTab = within(nav).getByRole('button', { name: /networks/i })
    fireEvent.click(networksTab)

    expect(await screen.findByText('Docker Networks')).toBeInTheDocument()
    expect(await screen.findByText('custom-bridge-net')).toBeInTheDocument()
    expect(screen.getByText('172.17.0.0/16')).toBeInTheDocument()
  })

  it('handles backend failure with error state display', async () => {
    fetchMock.mockImplementation(async () => {
      return jsonResponse(
        {
          type: 'https://tools.ietf.org/html/rfc7807',
          title: 'Collector Snapshot Unavailable',
          status: 503,
          detail: 'Docker daemon socket proxy is unreachable',
          request_id: 'req_123',
        },
        { status: 503 },
      )
    })

    renderApp()

    expect(await screen.findByText('Unable to load PortWatch System Summary')).toBeInTheDocument()
    expect(screen.getAllByText('Docker daemon socket proxy is unreachable').length).toBeGreaterThan(
      0,
    )
    expect(screen.getByText('req_123')).toBeInTheDocument()
  })
})
