import dayjs from 'dayjs'

export function formatRelativeTime(value: string, now = dayjs()): string {
  const target = dayjs(value)
  if (!target.isValid()) return '—'

  const seconds = Math.max(0, now.diff(target, 'second'))
  if (seconds < 10) return '刚刚'
  if (seconds < 60) return `${seconds} 秒前`

  const minutes = Math.floor(seconds / 60)
  if (minutes < 60) return `${minutes} 分钟前`

  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours} 小时前`

  const days = Math.floor(hours / 24)
  if (days < 7) return `${days} 天前`
  return target.format('YYYY-MM-DD HH:mm')
}
