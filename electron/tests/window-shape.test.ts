import assert from 'node:assert/strict'
import test from 'node:test'
import { needsWindowsRegion, roundedWindowRegion } from '../main/window-shape'

test('only pre-Windows-11 uses native regions; Windows 11 keeps system corners', () => {
  assert.equal(needsWindowsRegion('win32', '10.0.19044'), true)
  assert.equal(needsWindowsRegion('win32', '10.0.22631'), false)
  assert.equal(needsWindowsRegion('darwin', '23.1.0'), false)
})

test('native region clips all four outer corners without cutting central controls or edges', () => {
  for (const [width, height] of [
    [1280, 800],
    [960, 640],
  ]) {
    const rects = roundedWindowRegion(width!, height!)
    const contains = (x: number, y: number) =>
      rects.some(
        (r) => x >= r.x && x < r.x + r.width && y >= r.y && y < r.y + r.height,
      )
    for (const [x, y] of [
      [0, 0],
      [width! - 1, 0],
      [0, height! - 1],
      [width! - 1, height! - 1],
    ]) {
      assert.equal(contains(x!, y!), false)
    }
    for (const [x, y] of [
      [0, 20],
      [width! - 1, 20],
      [width! / 2, 0],
      [width! / 2, height! - 1],
    ]) {
      assert.equal(contains(x!, y!), true)
    }
    assert.ok(rects.every((r) => r.width > 0 && r.height > 0))
  }
})
