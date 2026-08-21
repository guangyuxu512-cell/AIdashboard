import { describe, expect, it } from 'vitest'

import { createMockNotificationChannelDataSource } from './notification-channel-data-source'

const input = {
  channelType: 'feishu_webhook' as const,
  name: '运营告警群',
  enabled: true,
  webhookUrl: 'https://example.test/webhook/secret-value',
  deviceOfflineEnabled: true,
  deviceRecoveredEnabled: true,
}

describe('notification channel data source', () => {
  it('returns only configured state and preserves the secret on blank edit', async () => {
    const source = createMockNotificationChannelDataSource()
    const created = await source.create(input)
    const updated = await source.update(created.channelId, {
      ...input,
      name: '设备通知群',
      webhookUrl: '',
    })
    const [listed] = await source.list()

    expect(updated.webhookConfigured).toBe(true)
    expect(listed).toEqual(updated)
    expect(JSON.stringify(listed)).not.toContain('secret-value')
  })

  it('requires a webhook for a new channel and supports test delivery', async () => {
    const source = createMockNotificationChannelDataSource()
    await expect(source.create({ ...input, webhookUrl: '' })).rejects.toThrow(
      '首次配置必须填写 Webhook URL',
    )
    const created = await source.create(input)
    await expect(source.test(created.channelId)).resolves.toBeUndefined()
  })
})
