import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import {
  TaskListCard,
  type TaskEventReadDto,
  type TaskListItem,
  type TaskReadDto,
  type TaskStatusDto,
} from '@/entities/task'
import { TaskInfiniteList, TaskListControls } from '@/features/task-center'
import {
  RUNTIME_RETENTION_TEXT,
  TaskDetailCard,
  TaskOutcomeNotice,
  TaskRuntimeLog,
} from '@/features/task-runtime'

const task: TaskListItem = {
  taskId: 'task-1',
  targetDeviceId: 'device-1',
  deviceDisplayName: '仓库手机',
  skillId: 'sync-orders',
  skillDisplayName: '订单同步',
  executionName: '同步订单',
  status: 'running',
  progress: { current: 3, total: 10 },
  currentMessage: '正在同步',
  startedAt: '2026-08-26T00:00:00Z',
  finishedAt: null,
  createdAt: '2026-08-26T00:00:00Z',
}

const runtimeEvent: TaskEventReadDto = {
  event_id: 'event-2',
  task_id: 'task-1',
  seq: 2,
  event_type: 'log',
  level: 'info',
  message: '纯文本日志',
  event_at: '2026-08-26T00:00:00Z',
  metadata: {},
  created_at: '2026-08-26T00:00:00Z',
}

const taskDetail: TaskReadDto = {
  task_id: 'task-1',
  target_device_id: 'device-1',
  shop_ids: [],
  asset_ids: [],
  skill_id: 'sync-orders',
  execution_display_name: '同步订单',
  status: 'running',
  input: {},
  result: null,
  error_code: null,
  error_message: null,
  lease_until: null,
  started_at: '2026-08-26T00:00:00Z',
  finished_at: null,
  runtime_events_purged_at: null,
  created_at: '2026-08-25T23:59:00Z',
  updated_at: '2026-08-26T00:00:00Z',
}

const listProps = {
  tasks: [task],
  initialLoading: false,
  initialError: false,
  nextPageError: false,
  refreshing: false,
  loadingMore: false,
  hasMore: false,
}

const runtimeProps = {
  events: [runtimeEvent],
  initialized: true,
  purgedAt: null,
  loading: false,
  loadingEarlier: false,
  hasMoreBefore: false,
  initialError: false,
  backgroundError: false,
  earlierError: false,
  reachedMemoryLimit: false,
}

describe('task center UI', () => {
  it('renders the four formal totals and shares the selected metric event', async () => {
    const wrapper = mount(TaskListControls, {
      props: {
        searchQuery: '',
        filter: 'all',
        totals: { running: 2, pending: 3, exception: 4, completed: 5 },
        metricsBusy: false,
        resultLabel: '任务',
        resultCount: '14个',
        dateLabel: '近7天',
      },
    })

    expect(
      wrapper
        .findAll('.mobile-summary-strip__metric')
        .map((metric) => metric.text()),
    ).toEqual(['2运行中', '3待运行', '4异常', '5已完成'])
    expect(wrapper.get('[data-testid="task-context-count"]').text()).toBe(
      '14个',
    )
    expect(wrapper.get('[data-testid="task-context-date"]').text()).toBe(
      '近7天',
    )

    await wrapper.get('button[aria-label="异常，点击筛选"]').trigger('click')
    expect(wrapper.emitted('selectFilter')).toEqual([['exception']])
  })

  it('keeps the current Task List card anatomy unchanged', () => {
    const wrapper = mount(TaskListCard, { props: { task } })

    expect(wrapper.find('[data-testid="task-card-leading"]').exists()).toBe(
      true,
    )
    expect(wrapper.get('[data-testid="task-card-name"]').text()).toBe(
      '同步订单',
    )
    expect(wrapper.get('[data-testid="task-card-state"]').text()).toContain(
      '执行中',
    )
    expect(
      wrapper
        .findAll('[data-testid="task-card-tags"] .van-tag')
        .map((tag) => tag.text()),
    ).toEqual(['仓库手机', '订单同步'])
    expect(wrapper.find('[data-testid="task-card-chevron"]').exists()).toBe(
      true,
    )
    expect(wrapper.find('.van-progress').exists()).toBe(false)
    expect(wrapper.text()).not.toContain('3 / 10')
    expect(wrapper.text()).not.toContain('正在同步')
    expect(wrapper.classes()).toContain('mobile-card')
  })

  it('keeps the same three rows when progress and optional skill meta are absent', () => {
    const wrapper = mount(TaskListCard, {
      props: {
        task: {
          ...task,
          skillDisplayName: null,
          progress: null,
          currentMessage: null,
        },
      },
    })

    expect(wrapper.find('.van-progress').exists()).toBe(false)
    expect(
      wrapper.findAll('[data-testid="task-card-tags"] .van-tag'),
    ).toHaveLength(1)
    expect(wrapper.get('[data-testid="task-card-tags"]').text()).toBe(
      '仓库手机',
    )
  })

  it('renders the candidate TaskCard V2 through the same business component', async () => {
    const wrapper = mount(TaskListCard, {
      props: { task, visualV2: true, buttonTestId: 'current-task-link' },
    })

    expect(wrapper.classes()).toContain('mobile-business-card-frame')
    expect(wrapper.get('[data-testid="task-card-state"]').text()).toContain(
      '执行中',
    )
    expect(wrapper.get('[data-testid="task-card-meta"]').text()).toContain(
      '开始',
    )
    expect(wrapper.get('[data-testid="task-card-meta"]').text()).toContain(
      '仓库手机',
    )
    expect(wrapper.find('.van-tag').exists()).toBe(false)
    await wrapper.get('[data-testid="current-task-link"]').trigger('click')
    expect(wrapper.emitted('select')).toEqual([['task-1']])
  })

  it('uses formal status artwork, real duration and contract-backed list tags', () => {
    const wrapper = mount(TaskListCard, {
      props: {
        visualV2: true,
        metaMode: 'tags',
        task: {
          ...task,
          status: 'success',
          startedAt: '2026-08-26T00:00:00Z',
          finishedAt: '2026-08-26T00:06:00Z',
        },
      },
    })

    expect(
      wrapper.get('[data-testid="task-card-leading"]').classes(),
    ).toContain('task-list-card-v2__artwork--done')
    expect(wrapper.get('[data-testid="task-card-state"]').text()).toContain(
      '成功·6分钟',
    )
    expect(
      wrapper
        .findAll('[data-testid="task-card-tags"] .van-tag')
        .map((tag) => tag.text()),
    ).toEqual(['订单同步'])
    expect(wrapper.text()).not.toContain('Provider')
    expect(wrapper.text()).not.toContain('仓库手机')
  })

  it.each([
    ['pending', 'task-list-card-v2__artwork--pending'],
    ['running', 'task-list-card-v2__artwork--running'],
    ['failed', 'task-list-card-v2__artwork--error'],
    ['lost', 'task-list-card-v2__artwork--error'],
    ['success', 'task-list-card-v2__artwork--done'],
  ] as const)(
    'maps %s into the confirmed artwork state',
    (status, className) => {
      const wrapper = mount(TaskListCard, {
        props: { task: { ...task, status }, visualV2: true, metaMode: 'tags' },
      })

      expect(
        wrapper.get('[data-testid="task-card-leading"]').classes(),
      ).toContain(className)
    },
  )

  it('renders a contract-backed Task Detail card without list behavior or prototype fields', () => {
    const wrapper = mount(TaskDetailCard, {
      props: {
        task: taskDetail,
        deviceName: '仓库设备',
        deviceState: 'ready',
        now: new Date('2026-08-26T00:03:00Z'),
      },
    })

    expect(wrapper.get('[data-testid="task-detail-title"]').text()).toBe(
      '同步订单',
    )
    expect(wrapper.get('[data-testid="task-detail-status"]').text()).toContain(
      '执行中·3分钟',
    )
    expect(
      wrapper.get('[data-testid="task-detail-artwork"]').classes(),
    ).toContain('task-detail-summary__artwork--running')
    expect(
      wrapper.get('[data-testid="task-detail-info-started"]').text(),
    ).toContain('开始时间')
    expect(wrapper.get('[data-testid="task-detail-info-device"]').text()).toBe(
      '执行设备仓库设备',
    )
    expect(wrapper.find('button').exists()).toBe(false)
    expect(wrapper.text()).not.toContain('触发方式')
    expect(wrapper.text()).not.toContain('执行账号')
    expect(wrapper.text()).not.toContain('sync-orders')
    expect(wrapper.text()).not.toContain('device-1')
  })

  it('keeps secondary device loading local and only renders safe outcome facts', () => {
    const loading = mount(TaskDetailCard, {
      props: {
        task: taskDetail,
        deviceState: 'loading',
        now: new Date('2026-08-26T00:03:00Z'),
      },
    })
    expect(loading.get('[data-testid="task-detail-title"]').text()).toBe(
      '同步订单',
    )
    expect(loading.get('[data-testid="task-detail-info-device"]').text()).toBe(
      '执行设备加载中',
    )

    const failed = mount(TaskDetailCard, {
      props: {
        task: {
          ...taskDetail,
          status: 'failed',
          finished_at: '2026-08-26T00:04:00Z',
          error_code: 'PRIVATE_ERROR_CODE',
          error_message: '账号会话不可用',
        },
        deviceName: '仓库设备',
        deviceState: 'ready',
      },
    })
    expect(failed.get('[data-testid="task-detail-info-error"]').text()).toBe(
      '失败原因账号会话不可用',
    )
    expect(failed.text()).not.toContain('PRIVATE_ERROR_CODE')

    const success = mount(TaskDetailCard, {
      props: {
        task: {
          ...taskDetail,
          status: 'success',
          finished_at: '2026-08-26T00:04:00Z',
          result: { summary: '已同步 24 笔订单', private_data: '不得显示' },
        },
        deviceName: '仓库设备',
        deviceState: 'ready',
      },
    })
    expect(success.get('[data-testid="task-detail-info-result"]').text()).toBe(
      '执行结果已同步 24 笔订单',
    )
    expect(success.text()).not.toContain('不得显示')
  })

  it.each([
    ['pending', '待执行'],
    ['running', '执行中'],
    ['success', '成功'],
    ['failed', '失败'],
    ['lost', '已丢失'],
  ] as const)(
    'renders the formal %s status without spreading runtime or error text',
    (status, expected) => {
      const wrapper = mount(TaskListCard, {
        props: {
          task: {
            ...task,
            status,
            progress: null,
            currentMessage: 'INTERNAL_STACK_TRACE',
          },
        },
      })

      expect(wrapper.get('[data-testid="task-card-state"]').text()).toContain(
        expected,
      )
      expect(wrapper.text()).not.toContain('INTERNAL_STACK_TRACE')
      expect(wrapper.find('.van-progress').exists()).toBe(false)
    },
  )

  it('covers loading, empty and initial error states', () => {
    const loading = mount(TaskInfiniteList, {
      props: { ...listProps, tasks: [], initialLoading: true },
    })
    expect(loading.find('[data-testid="task-loading"]').exists()).toBe(true)

    const empty = mount(TaskInfiniteList, {
      props: { ...listProps, tasks: [] },
    })
    expect(empty.find('[data-testid="task-empty"]').exists()).toBe(true)

    const error = mount(TaskInfiniteList, {
      props: { ...listProps, tasks: [], initialError: true },
    })
    expect(error.find('[data-testid="task-error"]').exists()).toBe(true)
  })

  it('uses the shared card press language for task navigation', () => {
    const wrapper = mount(TaskInfiniteList, { props: listProps })
    const card = wrapper.get('[data-testid="task-card"]')

    expect(card.classes()).toEqual(
      expect.arrayContaining([
        'mobile-business-card-surface-v2',
        'mobile-press-surface',
      ]),
    )
    expect(card.get('button').attributes('aria-label')).toBe(
      '查看任务：同步订单',
    )
  })

  it('keeps a successful empty cache visible during a background error', () => {
    const wrapper = mount(TaskInfiniteList, {
      props: {
        ...listProps,
        tasks: [],
      },
    })

    expect(wrapper.find('[data-testid="background-error"]').exists()).toBe(
      false,
    )
    expect(wrapper.find('[data-testid="task-empty"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="task-error"]').exists()).toBe(false)
  })

  it('renders a tail error for next-page failure and emits an explicit retry', async () => {
    const wrapper = mount(TaskInfiniteList, {
      props: { ...listProps, hasMore: true, nextPageError: true },
    })

    expect(wrapper.find('[data-testid="background-error"]').exists()).toBe(
      false,
    )
    await wrapper
      .get('[data-testid="task-next-page-error"] button')
      .trigger('click')
    expect(wrapper.emitted('retryLoadMore')).toHaveLength(1)
  })

  it.each([
    ['pending', false],
    ['running', false],
    ['success', true],
    ['failed', true],
    ['lost', true],
  ] as const)('renders the %s detail outcome safely', (status, visible) => {
    const wrapper = mount(TaskOutcomeNotice, {
      props: {
        status: status as TaskStatusDto,
        result: { summary: '安全摘要', private_data: '不得展示' },
        errorMessage: '已脱敏错误',
        errorCode: 'TASK_FAILED',
      },
    })

    expect(wrapper.text().length > 0).toBe(visible)
    if (status === 'success') {
      expect(wrapper.text()).toContain('安全摘要')
      expect(wrapper.text()).not.toContain('不得展示')
      expect(wrapper.get('.van-notice-bar').classes()).toContain(
        'mobile-notice-bar--success',
      )
    }
    if (status === 'failed' || status === 'lost') {
      expect(wrapper.text()).toContain('已脱敏错误')
      expect(wrapper.text()).toContain('TASK_FAILED')
      expect(wrapper.get('.van-notice-bar').classes()).toContain(
        'mobile-notice-bar--danger',
      )
    }
    if (visible) {
      expect(wrapper.get('.van-notice-bar').attributes('type')).toBeUndefined()
    }
  })

  it('keeps a 64-character error code in a wrapping content block', () => {
    const errorCode = 'E'.repeat(64)
    const wrapper = mount(TaskOutcomeNotice, {
      props: {
        status: 'failed',
        result: null,
        errorMessage: '错误',
        errorCode,
      },
    })

    expect(wrapper.get('code').text()).toBe(errorCode)
    expect(wrapper.get('code').classes()).not.toContain('van-ellipsis')
  })

  it('does not show a retention claim before the initial response is known', () => {
    for (const props of [
      { loading: true, initialError: false },
      { loading: false, initialError: true },
    ]) {
      const wrapper = mount(TaskRuntimeLog, {
        props: {
          ...runtimeProps,
          ...props,
          events: [],
          initialized: false,
        },
      })
      for (const text of Object.values(RUNTIME_RETENTION_TEXT).filter(
        Boolean,
      )) {
        expect(wrapper.text()).not.toContain(text)
      }
    }
  })

  it.each([
    [null, [] as TaskEventReadDto[], '暂无运行日志'],
    [null, [runtimeEvent], ''],
    ['2026-08-26T01:00:00Z', [], '运行日志已清理'],
    ['2026-08-26T01:00:00Z', [runtimeEvent], '较早日志已清理'],
  ] as const)(
    'renders the confirmed retention state for marker %s',
    (purgedAt, events, expected) => {
      const wrapper = mount(TaskRuntimeLog, {
        props: { ...runtimeProps, purgedAt, events: [...events] },
      })
      if (expected) expect(wrapper.text()).toContain(expected)
      else expect(wrapper.find('.runtime-log__status').exists()).toBe(false)
      if (events.length > 0) {
        expect(wrapper.find('.runtime-log__event').exists()).toBe(true)
        expect(wrapper.get('.runtime-log__message').text()).toBe(
          runtimeEvent.message,
        )
        expect(wrapper.get('time').attributes('datetime')).toBe(
          runtimeEvent.event_at,
        )
      }
    },
  )

  it('offers before_seq loading, memory notice and background retry', async () => {
    const wrapper = mount(TaskRuntimeLog, {
      props: {
        ...runtimeProps,
        purgedAt: '2026-08-26T01:00:00Z',
        hasMoreBefore: true,
        backgroundError: true,
      },
    })

    await wrapper.get('[data-testid="load-earlier-events"]').trigger('click')
    expect(wrapper.emitted('loadEarlier')).toHaveLength(1)
    await wrapper.get('[data-testid="retry-runtime-sync"]').trigger('click')
    expect(wrapper.emitted('retryLive')).toHaveLength(1)
    expect(wrapper.text()).toContain('刷新失败')

    await wrapper.setProps({ reachedMemoryLimit: true })
    expect(wrapper.find('[data-testid="event-limit-notice"]').exists()).toBe(
      true,
    )
    expect(wrapper.get('[data-testid="event-limit-notice"]').text()).toBe(
      '部分日志未显示',
    )
    expect(wrapper.find('.van-notice-bar').exists()).toBe(false)
  })

  it('keeps the log header fixed outside the only internal scroll region', () => {
    const wrapper = mount(TaskRuntimeLog, {
      props: runtimeProps,
    })

    expect(wrapper.get('.runtime-log').element.children[0]).toBe(
      wrapper.get('.runtime-log__heading').element,
    )
    expect(wrapper.get('.runtime-log').element.children[1]).toBe(
      wrapper.get('[data-testid="runtime-log-scroll"]').element,
    )
    expect(wrapper.get('[data-testid="runtime-events"]').text()).toContain(
      runtimeEvent.message,
    )
    expect(wrapper.text()).not.toContain('#2')
  })
})
