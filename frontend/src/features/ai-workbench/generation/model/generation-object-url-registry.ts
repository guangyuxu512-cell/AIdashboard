export interface GenerationObjectUrlRegistryDependencies {
  createObjectUrl?: (file: Blob) => string
  revokeObjectUrl?: (url: string) => void
}

interface GenerationObjectUrlEntry {
  owners: Set<string>
}

export function createGenerationObjectUrlRegistry(
  dependencies: GenerationObjectUrlRegistryDependencies = {},
) {
  const createObjectUrl =
    dependencies.createObjectUrl ?? ((file: Blob) => URL.createObjectURL(file))
  const revokeObjectUrl =
    dependencies.revokeObjectUrl ?? ((url: string) => URL.revokeObjectURL(url))
  const entries = new Map<string, GenerationObjectUrlEntry>()

  function register(url: string, owner: string): void {
    const entry = entries.get(url)
    if (entry) {
      entry.owners.add(owner)
      return
    }
    entries.set(url, { owners: new Set([owner]) })
  }

  function create(file: Blob, owner: string): string {
    const url = createObjectUrl(file)
    register(url, owner)
    return url
  }

  function retain(url: string, owner: string): boolean {
    const entry = entries.get(url)
    if (!entry) return false
    entry.owners.add(owner)
    return true
  }

  function release(url: string, owner: string): boolean {
    const entry = entries.get(url)
    if (!entry || !entry.owners.delete(owner)) return false
    if (entry.owners.size > 0) return true
    entries.delete(url)
    revokeObjectUrl(url)
    return true
  }

  function isManaged(url: string): boolean {
    return entries.has(url)
  }

  function ownerCount(url: string): number {
    return entries.get(url)?.owners.size ?? 0
  }

  function disposeAll(): void {
    for (const url of entries.keys()) revokeObjectUrl(url)
    entries.clear()
  }

  return {
    create,
    retain,
    release,
    isManaged,
    ownerCount,
    disposeAll,
  }
}
