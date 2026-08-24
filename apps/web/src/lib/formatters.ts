import type { ContainerStatus, PortState, PublishedPort } from './api'

export function formatShortId(id: string, length = 12): string {
  if (!id) return ''
  const cleanId = id.startsWith('sha256:') ? id.slice(7) : id
  return cleanId.slice(0, length)
}

export function formatDateTime(dateInput: string | Date | null | undefined): string {
  if (!dateInput) return '—'
  try {
    const date = typeof dateInput === 'string' ? new Date(dateInput) : dateInput
    if (isNaN(date.getTime())) return String(dateInput)
    return new Intl.DateTimeFormat(undefined, {
      dateStyle: 'medium',
      timeStyle: 'medium',
    }).format(date)
  } catch {
    return String(dateInput)
  }
}

export function formatRelativeTime(dateInput: string | Date | null | undefined): string {
  if (!dateInput) return '—'
  try {
    const date = typeof dateInput === 'string' ? new Date(dateInput) : dateInput
    if (isNaN(date.getTime())) return String(dateInput)

    const now = Date.now()
    const diffInSeconds = Math.round((date.getTime() - now) / 1000)

    const absDiff = Math.abs(diffInSeconds)
    if (absDiff < 60) {
      return diffInSeconds >= 0 ? 'just now' : `${absDiff}s ago`
    }
    const diffInMinutes = Math.round(diffInSeconds / 60)
    if (Math.abs(diffInMinutes) < 60) {
      const abs = Math.abs(diffInMinutes)
      return diffInMinutes >= 0 ? `in ${abs}m` : `${abs}m ago`
    }
    const diffInHours = Math.round(diffInMinutes / 60)
    if (Math.abs(diffInHours) < 24) {
      const abs = Math.abs(diffInHours)
      return diffInHours >= 0 ? `in ${abs}h` : `${abs}h ago`
    }
    const diffInDays = Math.round(diffInHours / 24)
    if (Math.abs(diffInDays) < 30) {
      const abs = Math.abs(diffInDays)
      return diffInDays >= 0 ? `in ${abs}d` : `${abs}d ago`
    }
    const diffInMonths = Math.round(diffInDays / 30)
    if (Math.abs(diffInMonths) < 12) {
      const abs = Math.abs(diffInMonths)
      return diffInMonths >= 0 ? `in ${abs}mo` : `${abs}mo ago`
    }
    const diffInYears = Math.round(diffInDays / 365)
    const abs = Math.abs(diffInYears)
    return diffInYears >= 0 ? `in ${abs}y` : `${abs}y ago`
  } catch {
    return String(dateInput)
  }
}

export function formatPort(port: PublishedPort): string {
  const proto = port.protocol ? port.protocol.toUpperCase() : 'TCP'
  if (port.host_port !== null && port.host_port !== undefined) {
    if (port.host_ip && port.host_ip !== '0.0.0.0' && port.host_ip !== '::') {
      return `${port.host_ip}:${port.host_port} → ${port.container_port}/${proto}`
    }
    return `${port.host_port} → ${port.container_port}/${proto}`
  }
  return `${port.container_port}/${proto}`
}

export function getStatusBadgeInfo(status: ContainerStatus | string): {
  label: string
  className: string
  dotClassName: string
} {
  switch (status.toLowerCase()) {
    case 'running':
      return {
        label: 'Running',
        className: 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20',
        dotClassName: 'bg-emerald-500 animate-pulse',
      }
    case 'exited':
      return {
        label: 'Exited',
        className: 'bg-zinc-500/10 text-zinc-600 dark:text-zinc-400 border-zinc-500/20',
        dotClassName: 'bg-zinc-400',
      }
    case 'paused':
      return {
        label: 'Paused',
        className: 'bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/20',
        dotClassName: 'bg-amber-500',
      }
    case 'restarting':
      return {
        label: 'Restarting',
        className: 'bg-blue-500/10 text-blue-600 dark:text-blue-400 border-blue-500/20',
        dotClassName: 'bg-blue-500 animate-spin',
      }
    case 'dead':
      return {
        label: 'Dead',
        className: 'bg-rose-500/10 text-rose-600 dark:text-rose-400 border-rose-500/20',
        dotClassName: 'bg-rose-500',
      }
    case 'created':
      return {
        label: 'Created',
        className: 'bg-cyan-500/10 text-cyan-600 dark:text-cyan-400 border-cyan-500/20',
        dotClassName: 'bg-cyan-500',
      }
    default:
      return {
        label: status,
        className: 'bg-zinc-500/10 text-zinc-600 dark:text-zinc-400 border-zinc-500/20',
        dotClassName: 'bg-zinc-400',
      }
  }
}

export function getPortStateBadgeInfo(state: PortState | string): {
  label: string
  className: string
} {
  switch (state.toLowerCase()) {
    case 'published':
      return {
        label: 'Docker Published',
        className: 'bg-sky-500/10 text-sky-600 dark:text-sky-400 border-sky-500/20',
      }
    case 'host':
      return {
        label: 'Host Process',
        className: 'bg-purple-500/10 text-purple-600 dark:text-purple-400 border-purple-500/20',
      }
    case 'free':
      return {
        label: 'Free',
        className: 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20',
      }
    default:
      return {
        label: state,
        className: 'bg-zinc-500/10 text-zinc-600 dark:text-zinc-400 border-zinc-500/20',
      }
  }
}
