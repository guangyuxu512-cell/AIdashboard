import { afterEach, describe, expect, it, vi } from 'vitest'

import { httpClient } from '@/shared/api'

import { automationApplicationApi } from './automation-application-api'

describe('automation parameter preset api', () => {
  afterEach(() => vi.restoreAllMocks())

  it('uses the team-scoped preset routes and sends only the preset payload', async () => {
    const get = vi.spyOn(httpClient, 'get').mockResolvedValue({ data: [] })
    const post = vi.spyOn(httpClient, 'post').mockResolvedValue({ data: {} })
    const patch = vi.spyOn(httpClient, 'patch').mockResolvedValue({ data: {} })
    const appId = '影刀 / app'
    const presetId = 'preset / one'
    const data = {
      name: '店铺覆盖',
      common_parameters: { 数量: 0, 启用: false },
      shop_overrides: { 'shop-1': { 数量: 0 } },
    }
    const updateData = { ...data, expected_version: 3 }
    const path =
      '/api/v1/automation-app-configs/yingdao/%E5%BD%B1%E5%88%80%20%2F%20app/parameter-presets'

    await automationApplicationApi.listPresets(appId)
    await automationApplicationApi.createPreset(appId, data)
    await automationApplicationApi.updatePreset(appId, presetId, updateData)
    await automationApplicationApi.copyPreset(appId, presetId, '副本')

    expect(get).toHaveBeenCalledWith(path)
    expect(post).toHaveBeenNthCalledWith(1, path, data)
    expect(patch).toHaveBeenCalledWith(
      `${path}/preset%20%2F%20one`,
      updateData,
    )
    expect(post).toHaveBeenNthCalledWith(
      2,
      `${path}/preset%20%2F%20one/copy`,
      { name: '副本' },
    )
  })

  it('uses the actor-scoped application catalog and management list filters', async () => {
    const get = vi.spyOn(httpClient, 'get').mockResolvedValue({ data: [] })

    await automationApplicationApi.listYingdaoApplications()
    await automationApplicationApi.listAllPresets({
      appId: 'daily-collection',
      query: '日常 采集',
    })

    expect(get).toHaveBeenNthCalledWith(
      1,
      '/api/v1/automation-app-configs/yingdao/applications',
    )
    expect(get).toHaveBeenNthCalledWith(
      2,
      '/api/v1/automation-parameter-presets',
      { params: { app_id: 'daily-collection', q: '日常 采集' } },
    )
  })
})
