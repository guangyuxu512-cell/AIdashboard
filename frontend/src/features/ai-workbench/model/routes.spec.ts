import { describe, expect, it } from 'vitest'

import { AI_WORKBENCH_NAVIGATION, AI_WORKBENCH_ROUTES } from './routes'

describe('AI workbench routes', () => {
  it('keeps the four product entries explicit and ordered', () => {
    expect(AI_WORKBENCH_NAVIGATION.map((item) => item.label)).toEqual([
      'AI生图',
      '素材库',
      '模板库',
      '生成记录',
    ])
    expect(AI_WORKBENCH_NAVIGATION.map((item) => item.path)).toEqual([
      '/ai-workbench/generate',
      '/ai-workbench/assets',
      '/ai-workbench/templates',
      '/ai-workbench/records',
    ])
  })

  it('uses unique route names and paths', () => {
    const routeNames = Object.values(AI_WORKBENCH_ROUTES).map(
      (route) => route.name,
    )
    const routePaths = Object.values(AI_WORKBENCH_ROUTES).map(
      (route) => route.path,
    )

    expect(new Set(routeNames).size).toBe(routeNames.length)
    expect(new Set(routePaths).size).toBe(routePaths.length)
  })
})
