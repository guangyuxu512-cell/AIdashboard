import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import type { BatchProductResultView } from '../model/types'
import BatchResultTree from './BatchResultTree.vue'

const results: BatchProductResultView[] = [
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
            templateName: '日系主图模板',
            outputRole: 'MAIN_IMAGE',
            results: [
              {
                id: 'main-1',
                name: '日系主图1.png',
                previewUrl: '/api/v1/assets/main-1/content',
                status: 'SUCCESS',
                outputRole: 'MAIN_IMAGE',
                size: '1:1',
              },
              {
                id: 'main-2',
                name: '日系主图2.png',
                previewUrl: '/api/v1/assets/main-2/content',
                status: 'SUCCESS',
                outputRole: 'MAIN_IMAGE',
                size: '1:1',
              },
              {
                id: 'main-failed',
                name: '日系主图失败.png',
                previewUrl: '/api/v1/assets/main-failed/content',
                status: 'FAILED',
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
            templateName: '详情图模板',
            outputRole: 'DETAIL_IMAGE',
            results: [
              {
                id: 'detail-1',
                name: '详情图1.png',
                previewUrl: '/api/v1/assets/detail-1/content',
                status: 'SUCCESS',
                outputRole: 'DETAIL_IMAGE',
                size: '1:1',
              },
            ],
          },
        ],
      },
    ],
  },
]

describe('BatchResultTree download selections', () => {
  it('emits only the clicked result for a single-image download', async () => {
    const wrapper = mount(BatchResultTree, { props: { results } })

    await wrapper.get('[aria-label="下载 日系主图2.png"]').trigger('click')

    expect(wrapper.emitted('download')).toEqual([
      [
        {
          scope: 'SINGLE',
          results: [results[0]!.groups[0]!.templates[0]!.results[1]],
        },
      ],
    ])
  })

  it('keeps group and batch actions scoped to their explicit result collections', async () => {
    const wrapper = mount(BatchResultTree, { props: { results } })

    await wrapper.get('[aria-label="下载 日系主图 结果"]').trigger('click')
    await wrapper.get('[aria-label="下载整个批次"]').trigger('click')

    const downloads = wrapper.emitted('download')
    expect(downloads?.[0]?.[0]).toMatchObject({ scope: 'GROUP' })
    expect(
      (downloads?.[0]?.[0] as { results: Array<{ id: string }> }).results.map(
        (result) => result.id,
      ),
    ).toEqual(['main-1', 'main-2', 'main-failed'])
    expect(downloads?.[1]?.[0]).toMatchObject({ scope: 'BATCH' })
    expect(
      (downloads?.[1]?.[0] as { results: Array<{ id: string }> }).results.map(
        (result) => result.id,
      ),
    ).toEqual(['main-1', 'main-2', 'main-failed', 'detail-1'])
  })
})
