import { shallowMount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import AppButton from '@/shared/ui/AppButton.vue'

import WorkerCredentialSection from './WorkerCredentialSection.vue'

describe('WorkerCredentialSection', () => {
  it('offers issue only for a device without an active credential', async () => {
    const wrapper = shallowMount(WorkerCredentialSection, {
      props: {
        credential: {
          device_id: 'device-1',
          status: 'not_issued',
          issued_at: null,
        },
      },
      global: { renderStubDefaultSlot: true },
    })

    const issue = wrapper
      .findAllComponents(AppButton)
      .find((button) => button.text() === '签发 Worker Token')
    expect(issue).toBeDefined()
    await issue?.trigger('click')
    expect(wrapper.emitted('issue')).toHaveLength(1)
    expect(wrapper.text()).not.toContain('token_hash')
  })

  it('offers rotate and revoke for an issued credential', async () => {
    const wrapper = shallowMount(WorkerCredentialSection, {
      props: {
        credential: {
          device_id: 'device-1',
          status: 'issued',
          issued_at: '2026-08-23T12:00:00Z',
        },
      },
      global: { renderStubDefaultSlot: true },
    })
    const buttons = wrapper.findAllComponents(AppButton)
    const rotate = buttons.find((button) => button.text() === '轮换 Token')
    const revoke = buttons.find((button) => button.text() === '撤销凭证')

    await rotate?.trigger('click')
    await revoke?.trigger('click')
    expect(wrapper.emitted('rotate')).toHaveLength(1)
    expect(wrapper.emitted('revoke')).toHaveLength(1)
    expect(wrapper.text()).toContain('已签发')
  })

  it('allows a revoked credential to be reissued', () => {
    const wrapper = shallowMount(WorkerCredentialSection, {
      props: {
        credential: {
          device_id: 'device-1',
          status: 'revoked',
          issued_at: '2026-08-23T12:00:00Z',
        },
      },
      global: { renderStubDefaultSlot: true },
    })

    expect(wrapper.text()).toContain('已撤销')
    expect(wrapper.text()).toContain('签发 Worker Token')
  })
})
