import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { describe, expect, it } from 'vitest'

interface ManifestIcon {
  src: string
  sizes: string
  type: string
  purpose: string
}

interface MobileManifest {
  id: string
  name: string
  short_name: string
  start_url: string
  scope: string
  display: string
  icons: ManifestIcon[]
}

function readPngDimensions(relativePath: string): {
  width: number
  height: number
} {
  const png = readFileSync(resolve(process.cwd(), relativePath))
  expect(png.subarray(1, 4).toString()).toBe('PNG')
  return {
    width: png.readUInt32BE(16),
    height: png.readUInt32BE(20),
  }
}

describe('Mobile Production PWA contract', () => {
  it('keeps installation identity and navigation inside /mobile/', () => {
    const manifest = JSON.parse(
      readFileSync(
        resolve(process.cwd(), 'public/manifest.webmanifest'),
        'utf8',
      ),
    ) as MobileManifest

    expect(manifest).toMatchObject({
      id: '/mobile/',
      name: '思余AI中控台',
      short_name: '思余中控台',
      start_url: '/mobile/',
      scope: '/mobile/',
      display: 'standalone',
    })
    expect(manifest.icons).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ sizes: '192x192', purpose: 'any' }),
        expect.objectContaining({ sizes: '512x512', purpose: 'any' }),
        expect.objectContaining({ sizes: '512x512', purpose: 'maskable' }),
      ]),
    )
  })

  it('ships valid square PNG installation assets', () => {
    expect(readPngDimensions('public/icons/icon-192.png')).toEqual({
      width: 192,
      height: 192,
    })
    expect(readPngDimensions('public/icons/icon-512.png')).toEqual({
      width: 512,
      height: 512,
    })
    expect(readPngDimensions('public/icons/icon-maskable-512.png')).toEqual({
      width: 512,
      height: 512,
    })
    expect(readPngDimensions('public/icons/apple-touch-icon.png')).toEqual({
      width: 180,
      height: 180,
    })
  })

  it('links platform metadata through the Vite base without a service worker', () => {
    const indexHtml = readFileSync(resolve(process.cwd(), 'index.html'), 'utf8')
    const sourceFiles = [
      'src/main.ts',
      'src/App.vue',
      'src/app/router/index.ts',
    ].map((path) => readFileSync(resolve(process.cwd(), path), 'utf8'))

    expect(indexHtml).toContain('href="%BASE_URL%manifest.webmanifest"')
    expect(indexHtml).toContain('rel="apple-touch-icon"')
    expect(indexHtml).toContain('apple-mobile-web-app-capable')
    expect(indexHtml).toContain('apple-mobile-web-app-status-bar-style')
    expect(indexHtml).toContain('data-mobile-theme-color')
    expect(sourceFiles.join('\n')).not.toMatch(
      /serviceWorker|navigator\.serviceWorker/,
    )
  })
})
