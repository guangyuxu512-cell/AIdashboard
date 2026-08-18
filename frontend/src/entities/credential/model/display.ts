export function maskCredentialIdentifier(value: string): string {
  const normalized = value.trim()
  if (normalized.includes('@')) {
    const [local = '', domain = ''] = normalized.split('@')
    const visible = local.length >= 3 ? local.slice(0, 3) : local.slice(0, 1)
    return `${visible}***@${domain}`
  }
  if (/^\d{7,}$/.test(normalized)) {
    return `${normalized.slice(0, 3)}****${normalized.slice(-4)}`
  }
  if (normalized.length <= 2) return '*'.repeat(normalized.length)
  return `${normalized.slice(0, 2)}***${normalized.slice(-2)}`
}
