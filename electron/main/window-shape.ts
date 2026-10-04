import type { Rectangle } from 'electron'

// Rounded client shell is 12 CSS px; Windows 10 needs a real native region too.
export const shellCornerRadius = 12

export function roundedWindowRegion(
  width: number,
  height: number,
): Rectangle[] {
  const radius = Math.min(
    shellCornerRadius,
    Math.floor(width / 2),
    Math.floor(height / 2),
  )
  if (radius <= 0) return []
  const region: Rectangle[] = [
    { x: 0, y: radius, width, height: height - 2 * radius },
  ]
  for (let y = 0; y < radius; y++) {
    const inset = Math.ceil(
      radius - Math.sqrt(radius * radius - (radius - y - 0.5) ** 2),
    )
    region.push(
      { x: inset, y, width: width - 2 * inset, height: 1 },
      { x: inset, y: height - y - 1, width: width - 2 * inset, height: 1 },
    )
  }
  return region
}

export function needsWindowsRegion(platform: string, release: string): boolean {
  return platform === 'win32' && Number(release.split('.')[2]) < 22000
}
