import { flushPromises, mount } from '@vue/test-utils'
import { QueryClient, VueQueryPlugin } from '@tanstack/vue-query'
import { describe, expect, it, vi } from 'vitest'
import { defineComponent, h, ref } from 'vue'
import { NDescriptions, NMessageProvider, NTooltip, NCollapse } from 'naive-ui'
import { AppButton } from '@/shared/ui'
import { createSelectionMockHandlers } from '../api/selection-mock-handlers'
import {
  formatCandidateDate,
  formatCandidateTime,
  formatReviewRate,
} from '../model/candidate-display'
import CandidateDetailDrawer from './CandidateDetailDrawer.vue'
import ExternalProductImage from './ExternalProductImage.vue'
import type { SelectionService } from '../model/contracts'
import type { SelectionBasicRunDto } from '../api/selection-read-api'

describe('candidate details preserve the draft contract', () => {
  it('shows identity, missing metrics, block state and raw ranges with the existing preview', async () => {
    const service = createSelectionMockHandlers()
    await service.demoAction('candidate-000', 'block')
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false, gcTime: 0 } },
    })
    const selectedId = ref('candidate-000')
    const Wrapper = defineComponent({
      setup: () => () =>
        h(
          NMessageProvider,
          {},
          {
            default: () =>
              h(CandidateDetailDrawer, {
                id: selectedId.value,
                service,
                contextKey: 'actor:team',
              }),
          },
        ),
    })
    const wrapper = mount(Wrapper, {
      global: {
        plugins: [[VueQueryPlugin, { queryClient }]],
        stubs: {
          DetailDrawer: {
            template: '<div><slot /><slot name="footer" /></div>',
          },
          ExternalProductImage: true,
        },
      },
    })
    await flushPromises()
    const row = await service.candidate('candidate-000')
    expect(
      wrapper
        .findAll('section')
        .map((section) => section.attributes('aria-label')),
    ).toEqual(['罗盘视频数据', '排名与发现', '商品基础信息', '数据来源'])
    const metrics = wrapper.get('section[aria-label="罗盘视频数据"]')
    expect(metrics.findComponent(NDescriptions).props('column')).toBe(2)
    const metadata = wrapper.get('.candidate-detail__metadata')
    expect(metadata.text()).toContain(`罗盘：${row.sourceContext.periodLabel}`)
    expect(metadata.text()).toContain(
      `更新 ${formatCandidateTime(row.metricsRetrievedAt, 'MM-DD HH:mm')}`,
    )
    expect(wrapper.get('.candidate-detail__headline').text()).toContain(
      row.title,
    )
    expect(metrics.text()).not.toContain('统计周期')
    expect(metrics.text()).not.toContain('指标获取时间')
    expect(metrics.text()).not.toContain(row.sourceContext.statisticalPeriod)
    const descriptions = wrapper.findAllComponents(NDescriptions)
    expect(descriptions).toHaveLength(3)
    for (const description of descriptions) {
      expect(description.props('bordered')).toBe(true)
      expect(description.props('themeOverrides')).toEqual({
        thPaddingBorderedMedium: 'var(--space-2)',
        tdPaddingBorderedMedium: 'var(--space-2)',
        fontSizeMedium: 'var(--font-size-secondary)',
        thFontWeight: 'var(--font-weight-regular)',
        thTextColor: 'var(--text-secondary)',
        tdTextColor: 'var(--text-primary)',
      })
      expect(description.props('labelStyle')).toEqual({
        fontSize: 'var(--font-size-secondary)',
      })
    }
    expect(descriptions[1].props('column')).toBe(2)
    expect(
      wrapper.findComponent(NCollapse).props('defaultExpandedNames'),
    ).toEqual([])
    expect(wrapper.text()).not.toContain('请求罗盘使用的自有店铺')
    expect(wrapper.findAll('.candidate-detail__metadata')).toHaveLength(1)
    expect(
      metrics.findAll('.candidate-detail__metric').map((item) => item.text()),
    ).toEqual(['—', '1000–5000', '100–500', '10–50'])
    expect(wrapper.findComponent(ExternalProductImage).props('src')).toBe(
      row.imageUrl,
    )
    await wrapper.get('.n-collapse-item__header-main').trigger('click')
    await flushPromises()
    for (const label of [
      '商品所属商家',
      '请求罗盘使用的自有店铺',
      '类目',
      '价格带',
      '上架日期',
      '差评率',
      '屏蔽状态',
      '来源',
      '完整统计区间',
      '本次排名',
      '首次上榜',
      '榜单检查时间',
    ])
      expect(wrapper.text()).toContain(label)
    expect(wrapper.text()).toContain('已屏蔽')
    expect(wrapper.text()).toContain(row.shopName)
    expect(wrapper.text()).toContain(row.merchant!.name)
    expect(wrapper.text()).toContain('9087654321098765000')
    expect(wrapper.text()).toContain('1000–5000')
    expect(wrapper.text()).toContain('100–500')
    expect(wrapper.text()).toContain('—')
    const marker = vi.spyOn(service, 'markCompetitor')
    await wrapper
      .findAllComponents(AppButton)
      .find((button) => button.text() === '标记为竞品店铺')!
      .trigger('click')
    await flushPromises()
    expect(marker).toHaveBeenCalledExactlyOnceWith(row.merchant!.shopId)
    expect(wrapper.text()).toContain('已标记竞品店铺')
    expect(
      wrapper
        .findAllComponents(AppButton)
        .find((button) => button.text() === '采集资料')!
        .props('tone'),
    ).toBe('primary')
    expect(
      wrapper
        .findAllComponents(AppButton)
        .find((button) => button.text() === '更新基础信息')!
        .props('tone'),
    ).toBe('secondary')
    selectedId.value = 'candidate-005'
    await flushPromises()
    expect(wrapper.text()).toContain('0.00%')
    expect(wrapper.text()).toContain('1万–5万')
    expect(wrapper.text()).not.toContain('单位未确认')
    expect(wrapper.text()).not.toContain('请求罗盘使用的自有店铺')
    expect(
      wrapper
        .findAllComponents(NTooltip)
        .find(
          (item) =>
            item.vm.$slots
              .default?.()
              .some((node) => node.children === '单位未确认') &&
            !item.props('disabled'),
        ),
    ).toBeDefined()
    wrapper.unmount()
    queryClient.clear()
    expect(formatCandidateDate(null)).toBe('—')
    expect(formatReviewRate(null)).toBe('—')
    expect(formatReviewRate(0)).toBe('0.00%')
  })
  it('keeps zero metrics prominent and a missing acquisition time unknown instead of using leaderboard or discovery time', async () => {
    const fixture =
      await createSelectionMockHandlers().candidate('candidate-000')
    const row = {
      ...fixture,
      metricsRetrievedAt: null,
      userPaidAmountRange: '0',
      clicksRange: '0',
      soldUnitsRange: '0',
      videoCountRange: null,
      collectionStatus: 'unknown' as const,
      sourceContext: {
        ...fixture.sourceContext,
        periodLabel: '',
        rankFrom: null,
        rankTo: null,
        checkedAt: '2026-10-09T09:00:00',
      },
    }
    const service = createSelectionMockHandlers([row])
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false, gcTime: 0 } },
    })
    const wrapper = mount(
      defineComponent({
        setup: () => () =>
          h(
            NMessageProvider,
            {},
            {
              default: () =>
                h(CandidateDetailDrawer, {
                  id: row.id,
                  service,
                  contextKey: 'actor:team',
                }),
            },
          ),
      }),
      {
        global: {
          plugins: [[VueQueryPlugin, { queryClient }]],
          stubs: {
            DetailDrawer: {
              template: '<div><slot /><slot name="footer" /></div>',
            },
            ExternalProductImage: true,
          },
        },
      },
    )
    await flushPromises()
    expect(wrapper.get('.candidate-detail__metadata').text()).toContain(
      '罗盘：— · 更新 —',
    )
    expect(wrapper.get('.candidate-detail__metadata').text()).not.toContain(
      '09:00',
    )
    expect(
      wrapper
        .findAll('.candidate-detail__metric')
        .map((metric) => metric.text()),
    ).toEqual(['0', '0', '0', '—'])
    await wrapper.get('.n-collapse-item__header-main').trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('榜单检查时间')
    expect(wrapper.text()).toContain('2026-10-09 09:00')
    expect(wrapper.text()).toContain('第—–—名')
    expect(wrapper.text()).toContain(row.sourceContext.statisticalPeriod)
    wrapper.unmount()
    queryClient.clear()
  })
  it('does not enable competitor marking when the product merchant is unknown, even with a valid request shop', async () => {
    const fixture =
      await createSelectionMockHandlers().candidate('candidate-000')
    const service = createSelectionMockHandlers([
      { ...fixture, merchant: null },
    ])
    const marker = vi.spyOn(service, 'markCompetitor')
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false, gcTime: 0 } },
    })
    const wrapper = mount(
      defineComponent({
        setup: () => () =>
          h(
            NMessageProvider,
            {},
            {
              default: () =>
                h(CandidateDetailDrawer, {
                  id: fixture.id,
                  service,
                  contextKey: 'actor:team',
                }),
            },
          ),
      }),
      {
        global: {
          plugins: [[VueQueryPlugin, { queryClient }]],
          stubs: {
            DetailDrawer: {
              template: '<div><slot /><slot name="footer" /></div>',
            },
            ExternalProductImage: true,
          },
        },
      },
    )
    await flushPromises()
    const button = wrapper
      .findAllComponents(AppButton)
      .find((button) => button.text() === '标记为竞品店铺')!
    expect(button.props('disabled')).toBe(true)
    expect(wrapper.text()).toContain('商品商家身份未确认')
    expect(wrapper.text()).not.toContain(fixture.shopName)
    await wrapper.get('.n-collapse-item__header-main').trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain(fixture.shopName)
    button.vm.$emit('click', new MouseEvent('click'))
    await flushPromises()
    expect(marker).not.toHaveBeenCalled()
    wrapper.unmount()
    queryClient.clear()
  })
})

describe('candidate detail current availability is independent of stored feedback', () => {
  async function renderRuntime(status: SelectionBasicRunDto['status'] | null) {
    const mock = createSelectionMockHandlers()
    const fixture = await mock.candidate('candidate-000')
    const availableField = {
      last_attempt_state: 'available' as const,
      last_success_at: '2026-10-15T02:00:00Z',
    }
    const submit = vi.fn(async () => {
      throw new Error('Disabled updates must not submit')
    })
    const service: SelectionService = {
      ...mock,
      available: false,
      candidate: async () => ({
        ...fixture,
        basicInfoStatus: {
          version: 1,
          attempted_at: '2026-10-15T02:00:00Z',
          request_started_at: '2026-10-15T01:59:00Z',
          state: 'succeeded',
          category_path: availableField,
          first_on_shelf_date: availableField,
          bad_comment_rate: availableField,
          error_code: null,
          error_stage: null,
          platform_business_code: null,
        },
      }),
      manual: {
        capabilities: async () => ({
          execution_enabled: false,
          manual_execution_available: false,
          basic_info_available: false,
          unavailable_reason: 'EXECUTION_DISABLED',
        }),
        submit,
      },
      basic: {
        submit,
        latest: async () =>
          status
            ? {
                run_id: 'basic-1',
                operation_kind: 'basic_info',
                target_observation_id: fixture.id,
                status,
                saved_count: 0,
                supplemented_count: status === 'succeeded' ? 1 : 0,
                supplement_failed_count: status === 'partial' ? 1 : 0,
                error_code:
                  status === 'failed'
                    ? 'DOUYIN_SELECTION_BUSINESS_REJECTED'
                    : null,
                error_stage: status === 'failed' ? 'platform_business' : null,
                platform_business_code: status === 'failed' ? 600002 : null,
                created_at: '2026-10-15T01:59:00Z',
                finished_at: null,
              }
            : null,
      },
    }
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false, gcTime: 0 } },
    })
    const wrapper = mount(
      defineComponent({
        setup: () => () =>
          h(
            NMessageProvider,
            {},
            {
              default: () =>
                h(CandidateDetailDrawer, {
                  id: fixture.id,
                  service,
                  contextKey: 'readonly-runtime',
                }),
            },
          ),
      }),
      {
        global: {
          plugins: [[VueQueryPlugin, { queryClient }]],
          stubs: {
            DetailDrawer: {
              template: '<div><slot /><slot name="footer" /></div>',
            },
            ExternalProductImage: true,
          },
        },
      },
    )
    await flushPromises()
    return { wrapper, queryClient, submit }
  }

  it.each([
    [null, '上次基础信息已更新'],
    ['succeeded', '上次基础信息已更新'],
    ['pending', '基础信息等待更新'],
    ['running', '基础信息更新中'],
    ['partial', '基础信息部分更新，未取得字段保留原值'],
    ['failed', '平台业务拒绝（600002），原因未确定'],
    ['interrupted', '基础信息更新中断，可重新提交'],
  ] as const)(
    'retains %s feedback and the current pause reason',
    async (status, expected) => {
      const { wrapper, queryClient, submit } = await renderRuntime(status)
      const feedback = wrapper.get('.candidate-detail__feedback')
      expect(feedback.text()).toContain(expected)
      expect(feedback.text()).toContain('当前环境暂停更新')
      const actions = wrapper.get('.candidate-detail__actions')
      for (const label of ['更新基础信息', '采集资料']) {
        const button = wrapper
          .findAllComponents(AppButton)
          .find((button) => button.text() === label)!
        expect(button.props('disabled')).toBe(true)
        await button.trigger('click')
      }
      expect(actions.text()).not.toContain('基础信息已更新')
      expect(submit).not.toHaveBeenCalled()
      wrapper.unmount()
      queryClient.clear()
    },
  )
})
