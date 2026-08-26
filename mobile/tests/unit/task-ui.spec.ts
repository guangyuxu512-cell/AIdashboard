import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import {
  TaskListCard,
  type TaskEventReadDto,
  type TaskListItem,
  type TaskStatusDto,
} from '@/entities/task'
import { TaskInfiniteList } from '@/features/task-center'
import {
  RUNTIME_RETENTION_TEXT,
  TaskOutcomeNotice,
  TaskRuntimeLog,
} from '@/features/task-runtime'

const task: TaskListItem = {
  taskId: 'task-1',
  targetDeviceId: 'device-1',
  deviceDisplayName: '仓库手机',
  skillId: 'sync-orders',
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

const listProps = {
  tasks: [task],
  initialLoading: false,
  initialError: false,
  backgroundError: false,
  nextPageError: false,
  errorMessage: '请求失败',
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
  initialError: null,
  backgroundError: null,
  earlierError: null,
  reachedMemoryLimit: false,
}

describe('task center UI', () => {
  it('renders status, safe list progress and current message on a mobile card', () => {
    const wrapper = mount(TaskListCard, { props: { task } })

    expect(wrapper.text()).toContain('同步订单')
    expect(wrapper.text()).toContain('执行中')
    expect(wrapper.text()).toContain('3 / 10')
    expect(wrapper.text()).toContain('正在同步')
    expect(wrapper.get('.van-progress').attributes('style')).toContain(
      'var(--progress-height-compact)',
    )
  })

  it('omits the whole progress section when structured progress is absent', () => {
    const wrapper = mount(TaskListCard, {
      props: {
        task: { ...task, progress: null, currentMessage: null },
      },
    })

    expect(wrapper.find('.task-list-card__progress').exists()).toBe(false)
    expect(wrapper.find('.van-progress').exists()).toBe(false)
    expect(wrapper.get('[data-testid="task-card-message"]').text()).toBe(
      '正在执行',
    )
  })

  it.each([
    ['failed', '任务执行失败'],
    ['lost', '任务状态已丢失'],
  ] as const)(
    'uses a safe short %s summary instead of spreading an error message',
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

      expect(wrapper.get('[data-testid="task-card-message"]').text()).toBe(
        expected,
      )
      expect(wrapper.text()).not.toContain('INTERNAL_STACK_TRACE')
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

  it('keeps a successful empty cache visible during a background error', () => {
    const wrapper = mount(TaskInfiniteList, {
      props: {
        ...listProps,
        tasks: [],
        backgroundError: true,
      },
    })

    expect(wrapper.find('[data-testid="background-error"]').exists()).toBe(true)
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
      { loading: true, initialError: null },
      { loading: false, initialError: '初始日志失败' },
    ]) {
      const wrapper = mount(TaskRuntimeLog, {
        props: {
          ...runtimeProps,
          ...props,
          events: [],
          initialized: false,
        },
      })
      for (const text of Object.values(RUNTIME_RETENTION_TEXT)) {
        expect(wrapper.text()).not.toContain(text)
      }
    }
  })

  it.each([
    [null, [] as TaskEventReadDto[], '当前任务尚未产生运行日志'],
    [null, [runtimeEvent], '当前展示任务保留的运行日志'],
    ['2026-08-26T01:00:00Z', [], '运行日志已按保留策略清理'],
    [
      '2026-08-26T01:00:00Z',
      [runtimeEvent],
      '较早日志已清理，当前仅展示保留部分',
    ],
  ] as const)(
    'renders the confirmed retention state for marker %s',
    (purgedAt, events, expected) => {
      const wrapper = mount(TaskRuntimeLog, {
        props: { ...runtimeProps, purgedAt, events: [...events] },
      })
      expect(wrapper.text()).toContain(expected)
      if (events.length > 0) {
        expect(wrapper.find('.runtime-log__meta').exists()).toBe(true)
        expect(wrapper.get('.runtime-log__message').text()).toBe(
          runtimeEvent.message,
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
        backgroundError: '增量失败',
      },
    })

    await wrapper.get('[data-testid="load-earlier-events"]').trigger('click')
    expect(wrapper.emitted('loadEarlier')).toHaveLength(1)
    await wrapper.get('[data-testid="retry-runtime-sync"]').trigger('click')
    expect(wrapper.emitted('retryLive')).toHaveLength(1)

    await wrapper.setProps({ reachedMemoryLimit: true })
    expect(wrapper.find('[data-testid="event-limit-notice"]').exists()).toBe(
      true,
    )
    expect(
      wrapper.get('[data-testid="event-limit-notice"]').classes(),
    ).toContain('mobile-notice-bar--warning')
  })
})
