import { readdirSync, readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { describe, expect, it } from 'vitest'

import { visualColorTokenRegistry } from '@/dev/visual-token-tuner'

const mobileRoot = process.cwd()
const colorLiteralPattern = /#[0-9a-fA-F]{3,8}\b|rgba?\(|hsla?\(/u

function sourceFiles(relativeDirectory: string): string[] {
  const directory = resolve(mobileRoot, relativeDirectory)
  return readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const relativePath = `${relativeDirectory}/${entry.name}`
    if (entry.isDirectory()) return sourceFiles(relativePath)
    return /\.(vue|ts|css)$/u.test(entry.name) ? [relativePath] : []
  })
}

function read(relativePath: string): string {
  return readFileSync(resolve(mobileRoot, relativePath), 'utf8')
}

function tokenBlock(tokens: string, theme: 'light' | 'dark'): string {
  const darkStart = tokens.indexOf(":root[data-theme='dark']")
  if (theme === 'dark') {
    return tokens.slice(darkStart)
  }
  return tokens.slice(0, darkStart)
}

describe('Stage 3A semantic color contract', () => {
  it('uses one semantic color template to generate matching Light and Dark registries', () => {
    const registrySource = read(
      'src/dev/visual-token-tuner/visual-token-registry.ts',
    )
    const lightDefinitions = visualColorTokenRegistry.filter(
      (definition) => definition.theme === 'light',
    )
    const darkDefinitions = visualColorTokenRegistry.filter(
      (definition) => definition.theme === 'dark',
    )

    expect(registrySource).toContain('const visualColorTokenTemplates')
    expect(registrySource).toContain("['light', 'dark'] as const")
    expect(registrySource).not.toContain("key: 'light-bg-app'")
    expect(registrySource).not.toContain("key: 'dark-bg-app'")
    expect(lightDefinitions.map((definition) => definition.cssVar)).toEqual(
      darkDefinitions.map((definition) => definition.cssVar),
    )
  })

  it('keeps every registered Light / Dark color baseline in the sole token source', () => {
    const tokens = read('src/shared/styles/tokens.css')

    expect(tokens).toContain('--bg-control:')
    expect(tokens).toContain('--border-divider:')
    expect(tokens).toContain('--text-muted:')
    expect(tokens).not.toMatch(/frontend\/.*tokens\.css/u)

    for (const definition of visualColorTokenRegistry) {
      expect(tokenBlock(tokens, definition.theme)).toContain(
        `${definition.cssVar}:`,
      )
    }

    expect(
      read('src/dev/visual-token-tuner/visual-token-registry.ts'),
    ).not.toMatch(colorLiteralPattern)
  })

  it('keeps Vant on Mobile semantic surface and divider tokens', () => {
    const vantTheme = read('src/shared/styles/vant-theme.css')

    expect(vantTheme).toContain('--van-background-3: var(--bg-control);')
    expect(vantTheme).toContain('--van-border-color: var(--border-divider);')
    expect(vantTheme).toContain(
      '--van-cell-border-color: var(--border-divider);',
    )
    expect(vantTheme).toContain('--van-text-color-3: var(--text-tertiary);')
  })

  it('does not allow business UI to introduce literal CSS colors outside tokens', () => {
    const businessUiFiles = [
      ...sourceFiles('src/pages'),
      ...sourceFiles('src/features'),
      ...sourceFiles('src/entities'),
      ...sourceFiles('src/shared/ui'),
    ]
    const filesWithLiterals = businessUiFiles.filter((relativePath) =>
      colorLiteralPattern.test(read(relativePath)),
    )

    expect(filesWithLiterals).toEqual([])
  })
})
