import { mount } from '@vue/test-utils'
import { defineComponent, h } from 'vue'
import { describe, expect, it } from 'vitest'

import type { GenerationRecordView } from '../../generation/model/types'
import GenerationRecordDetailDrawer from './GenerationRecordDetailDrawer.vue'

const record: GenerationRecordView = {
  id: 'record-1',
  sourceType: 'BATCH',
  mode: 'NORMAL_GENERATION',
  status: 'PARTIAL_FAILED',
  createdAt: '2026-09-12T00:00:00Z',
  createdBy: '操作员',
  summary: '批量生成',
  resultSummary: '2 成功 / 1 失败',
  detail: {
    kind: 'BATCH',
    productCount: 1,
    templateGroupCount: 2,
    generationItemCount: 3,
    successCount: 2,
    failedCount: 1,
    results: [
      {
        productId: 'product-1',
        productName: '餐盘',
        groups: [
          {
            groupId: 'group-main',
            groupName: '日系主图',
            templates: [
              {
                templateId: 'template-main',
                templateName: '主图模板',
                outputRole: 'MAIN_IMAGE',
                results: [
                  {
                    id: 'main-1',
                    name: '主图1.png',
                    previewUrl: '/api/v1/assets/main-1/content',
                    status: 'SUCCESS',
                    outputRole: 'MAIN_IMAGE',
                    size: '1:1',
                  },
                  {
                    id: 'main-2',
                    name: '主图2.png',
                    previewUrl: '/api/v1/assets/main-2/content',
                    status: 'SUCCESS',
                    outputRole: 'MAIN_IMAGE',
                    size: '1:1',
                  },
                ],
              },
            ],
          },
          {
            groupId: 'group-detail',
            groupName: '详情图',
            templates: [
              {
                templateId: 'template-detail',
                templateName: '详情模板',
                outputRole: 'DETAIL_IMAGE',
                results: [
                  {
                    id: 'detail-failed',
                    name: '详情失败.png',
                    previewUrl: '/api/v1/assets/detail-failed/content',
                    status: 'FAILED',
                    outputRole: 'DETAIL_IMAGE',
                    size: '1:1',
                  },
                ],
              },
            ],
          },
        ],
      },
    ],
  },
}

if (record.detail.kind !== 'BATCH') {
  throw new Error('batch record fixture is required')
}

const selectedResult =
  record.detail.results[0]!.groups[0]!.templates[0]!.results[1]!

const BatchResultTreeStub = defineComponent({
  emits: ['download'],
  setup(_, { emit }) {
    return () =>
      h(
        'button',
        {
          'aria-label': '下载单张主图',
          onClick: () =>
            emit('download', {
              scope: 'SINGLE',
              results: [selectedResult],
            }),
        },
        '下载单张主图',
      )
  },
})

function mountDrawer() {
  return mount(GenerationRecordDetailDrawer, {
    props: { show: true, record },
    global: {
      stubs: {
        DetailDrawer: {
          template: '<div><slot /><slot name="footer" /></div>',
        },
        NDescriptions: { template: '<div><slot /></div>' },
        NDescriptionsItem: { template: '<div><slot /></div>' },
        StatusTag: true,
        BatchResultTree: BatchResultTreeStub,
      },
    },
  })
}

describe('GenerationRecordDetailDrawer download contract', () => {
  it('forwards a single-result selection without expanding it to the record', async () => {
    const wrapper = mountDrawer()

    await wrapper.get('[aria-label="下载单张主图"]').trigger('click')

    expect(wrapper.emitted('download')).toEqual([
      [
        {
          scope: 'SINGLE',
          results: [selectedResult],
        },
      ],
    ])
  })

  it('emits the complete record only for the explicit footer action', async () => {
    const wrapper = mountDrawer()

    await wrapper.get('[aria-label="下载全部生成结果"]').trigger('click')

    const selection = wrapper.emitted('download')?.[0]?.[0] as {
      scope: string
      results: Array<{ id: string }>
    }
    expect(selection.scope).toBe('BATCH')
    expect(selection.results.map((result) => result.id)).toEqual([
      'main-1',
      'main-2',
      'detail-failed',
    ])
  })
})
