import { queryOptions, useQuery } from '@tanstack/react-query'

import { api, type AvailablePortFilters, type ContainerFilters, type PortFilters } from './api'

const SNAPSHOT_STALE_TIME_MS = 15_000
const SNAPSHOT_REFETCH_INTERVAL_MS = 30_000

const snapshotQueryDefaults = {
  staleTime: SNAPSHOT_STALE_TIME_MS,
  refetchInterval: SNAPSHOT_REFETCH_INTERVAL_MS,
  refetchIntervalInBackground: false,
} as const

export const portwatchQueryKeys = {
  all: ['portwatch'] as const,
  system: () => [...portwatchQueryKeys.all, 'system'] as const,
  systemSummary: () => [...portwatchQueryKeys.system(), 'summary'] as const,
  containers: () => [...portwatchQueryKeys.all, 'containers'] as const,
  containerList: (filters: ContainerFilters = {}) =>
    [...portwatchQueryKeys.containers(), 'list', filters] as const,
  container: (id: string) => [...portwatchQueryKeys.containers(), 'detail', id] as const,
  networks: () => [...portwatchQueryKeys.all, 'networks'] as const,
  networkList: () => [...portwatchQueryKeys.networks(), 'list'] as const,
  network: (id: string) => [...portwatchQueryKeys.networks(), 'detail', id] as const,
  ports: () => [...portwatchQueryKeys.all, 'ports'] as const,
  portList: (filters: PortFilters = {}) =>
    [...portwatchQueryKeys.ports(), 'list', filters] as const,
  availablePorts: (filters: AvailablePortFilters = {}) =>
    [...portwatchQueryKeys.ports(), 'available', filters] as const,
}

export function systemSummaryQueryOptions() {
  return queryOptions({
    queryKey: portwatchQueryKeys.systemSummary(),
    queryFn: ({ signal }) => api.systemSummary(signal),
    ...snapshotQueryDefaults,
  })
}

export function containersQueryOptions(filters: ContainerFilters = {}) {
  return queryOptions({
    queryKey: portwatchQueryKeys.containerList(filters),
    queryFn: ({ signal }) => api.containers(filters, signal),
    ...snapshotQueryDefaults,
  })
}

export function containerQueryOptions(id: string) {
  return queryOptions({
    queryKey: portwatchQueryKeys.container(id),
    queryFn: ({ signal }) => api.container(id, signal),
    enabled: id.length > 0,
    ...snapshotQueryDefaults,
  })
}

export function networksQueryOptions() {
  return queryOptions({
    queryKey: portwatchQueryKeys.networkList(),
    queryFn: ({ signal }) => api.networks(signal),
    ...snapshotQueryDefaults,
  })
}

export function networkQueryOptions(id: string) {
  return queryOptions({
    queryKey: portwatchQueryKeys.network(id),
    queryFn: ({ signal }) => api.network(id, signal),
    enabled: id.length > 0,
    ...snapshotQueryDefaults,
  })
}

export function portsQueryOptions(filters: PortFilters = {}) {
  return queryOptions({
    queryKey: portwatchQueryKeys.portList(filters),
    queryFn: ({ signal }) => api.ports(filters, signal),
    ...snapshotQueryDefaults,
  })
}

export function availablePortsQueryOptions(filters: AvailablePortFilters = {}) {
  return queryOptions({
    queryKey: portwatchQueryKeys.availablePorts(filters),
    queryFn: ({ signal }) => api.availablePorts(filters, signal),
    ...snapshotQueryDefaults,
  })
}

export const useSystemSummaryQuery = () => useQuery(systemSummaryQueryOptions())

export const useContainersQuery = (filters: ContainerFilters = {}) =>
  useQuery(containersQueryOptions(filters))

export const useContainerQuery = (id: string) => useQuery(containerQueryOptions(id))

export const useNetworksQuery = () => useQuery(networksQueryOptions())

export const useNetworkQuery = (id: string) => useQuery(networkQueryOptions(id))

export const usePortsQuery = (filters: PortFilters = {}) => useQuery(portsQueryOptions(filters))

export const useAvailablePortsQuery = (filters: AvailablePortFilters = {}) =>
  useQuery(availablePortsQueryOptions(filters))
