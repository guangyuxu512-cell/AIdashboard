import type {
  CandidateCollectionDraft,
  CollectionTask,
  CollectionTaskPage,
  CollectionTaskService,
  CreateCollectionTasksInput,
  CreateCollectionTasksReceipt,
} from '../model/contracts'

const now = '2026-10-20T10:20:00+08:00'
let sequence = 40

const initialTasks: CollectionTask[] = [
  {
    id: 'collection-demo-1',
    platform: 'douyin',
    inputMode: 'product',
    inputValue: '3832497447662387684',
    productId: '3832497447662387684',
    title: '家用不锈钢滤网储油罐',
    status: 'succeeded',
    progress: 100,
    receiptId: 'demo-receipt-001',
    ingestionState: 'ingested',
    errorMessage: null,
    itemCount: 1,
    pendingCount: 0,
    runningCount: 0,
    succeededCount: 1,
    failedCount: 0,
    canceledCount: 0,
    items: null,
    createdAt: '2026-10-20T09:12:00+08:00',
    updatedAt: '2026-10-20T09:14:18+08:00',
  },
  {
    id: 'collection-demo-2',
    platform: 'douyin',
    inputMode: 'product',
    inputValue: '3769776708757094595',
    productId: '3769776708757094595',
    title: '多规格不锈钢带滤网猪油罐',
    status: 'running',
    progress: 62,
    receiptId: 'demo-receipt-002',
    ingestionState: 'processing',
    errorMessage: null,
    itemCount: 1,
    pendingCount: 0,
    runningCount: 1,
    succeededCount: 0,
    failedCount: 0,
    canceledCount: 0,
    items: null,
    createdAt: '2026-10-20T10:18:00+08:00',
    updatedAt: now,
  },
  {
    id: 'collection-demo-3',
    platform: 'pdd',
    inputMode: 'product',
    inputValue: '992000000003',
    productId: '992000000003',
    title: null,
    status: 'failed',
    progress: null,
    receiptId: 'demo-receipt-003',
    ingestionState: 'not-started',
    errorMessage: '手机端未回传商品资料',
    itemCount: 1,
    pendingCount: 0,
    runningCount: 0,
    succeededCount: 0,
    failedCount: 1,
    canceledCount: 0,
    items: null,
    createdAt: '2026-10-19T18:30:00+08:00',
    updatedAt: '2026-10-19T18:36:00+08:00',
  },
]
const tasks: CollectionTask[] = structuredClone(initialTasks)

function createTask(
  value: string,
  input: Pick<CreateCollectionTasksInput, 'platform' | 'inputMode'>,
  title: string | null = null,
): CollectionTask {
  const normalized = value.trim()
  return {
    id: `collection-demo-${++sequence}`,
    platform: input.platform,
    inputMode: input.inputMode,
    inputValue: normalized,
    productId:
      input.inputMode === 'product'
        ? (normalized.match(/\d{8,}/)?.[0] ?? normalized)
        : null,
    title,
    status: 'pending',
    progress: 0,
    receiptId: null,
    ingestionState: 'not-started',
    errorMessage: null,
    itemCount: 1,
    pendingCount: 1,
    runningCount: 0,
    succeededCount: 0,
    failedCount: 0,
    canceledCount: 0,
    items: null,
    createdAt: now,
    updatedAt: now,
  }
}

function counts() {
  const result: NonNullable<CollectionTaskPage['counts']> = {
    all: tasks.length,
    pending: 0,
    running: 0,
    partial: 0,
    succeeded: 0,
    failed: 0,
    canceled: 0,
  }
  for (const task of tasks) result[task.status] += 1
  return result
}

export function enqueueCandidateCollectionTasks(
  rows: CandidateCollectionDraft[],
): CollectionTask[] {
  const created: CollectionTask[] = []
  for (const row of rows) {
    if (
      tasks.some(
        (task) =>
          task.platform === (row.platform ?? 'douyin') &&
          task.productId === row.productId &&
          !['failed', 'canceled'].includes(task.status),
      )
    )
      continue
    const task = createTask(
      row.productId,
      { platform: row.platform ?? 'douyin', inputMode: 'product' },
      row.title,
    )
    tasks.unshift(task)
    created.push(task)
  }
  return structuredClone(created)
}

export function createCollectionTaskMockService(): CollectionTaskService {
  return {
    available: true,
    mode: 'mock',
    supportsListFilters: true,
    supportsShopCode: true,
    supportsAutomaticPdd: false,
    async list(query) {
      const keyword = query.keyword.trim().toLocaleLowerCase()
      const filtered = tasks.filter(
        (task) =>
          (!query.platform || task.platform === query.platform) &&
          (!query.status || task.status === query.status) &&
          (!keyword ||
            `${task.inputValue} ${task.productId ?? ''} ${task.title ?? ''}`
              .toLocaleLowerCase()
              .includes(keyword)),
      )
      const page = Math.min(
        query.page,
        Math.max(1, Math.ceil(filtered.length / query.pageSize)),
      )
      return {
        items: structuredClone(
          filtered.slice((page - 1) * query.pageSize, page * query.pageSize),
        ),
        total: filtered.length,
        page,
        pageSize: query.pageSize,
        counts: counts(),
      }
    },
    async detail(id) {
      const task = tasks.find((item) => item.id === id)
      if (!task) throw new Error('演示采集任务不存在')
      return structuredClone(task)
    },
    async create(input): Promise<CreateCollectionTasksReceipt> {
      const created: CollectionTask[] = []
      const duplicates: CreateCollectionTasksReceipt['duplicates'] = []
      for (const value of [
        ...new Set(input.values.map((item) => item.trim())),
      ]) {
        const productId =
          input.inputMode === 'product'
            ? (value.match(/\d{8,}/)?.[0] ?? value)
            : null
        const existing = tasks.find(
          (task) =>
            task.platform === input.platform &&
            (input.inputMode === 'product'
              ? task.productId === productId
              : task.inputValue === value) &&
            !['failed', 'canceled'].includes(task.status),
        )
        if (existing) {
          duplicates.push({ value, taskId: existing.id })
          continue
        }
        const task = createTask(value, input)
        tasks.unshift(task)
        created.push(task)
      }
      return { created: structuredClone(created), duplicates }
    },
    async retry(ids) {
      let changed = 0
      for (const id of new Set(ids)) {
        const task = tasks.find((item) => item.id === id)
        if (!task || task.status !== 'failed') continue
        task.status = 'pending'
        task.progress = 0
        task.errorMessage = null
        task.pendingCount = task.itemCount
        task.failedCount = 0
        task.updatedAt = now
        changed += 1
      }
      return changed
    },
    async cancel(ids) {
      let changed = 0
      for (const id of new Set(ids)) {
        const task = tasks.find((item) => item.id === id)
        if (!task || !['pending', 'running'].includes(task.status)) continue
        task.status = 'canceled'
        task.progress = null
        task.pendingCount = 0
        task.runningCount = 0
        task.canceledCount = task.itemCount
        task.updatedAt = now
        changed += 1
      }
      return changed
    },
    async retryItem(itemId) {
      const task = tasks.find((item) =>
        item.items?.some((row) => row.id === itemId),
      )
      if (!task) throw new Error('演示采集明细不存在')
      task.status = 'pending'
      task.pendingCount = task.itemCount
      task.failedCount = 0
      return structuredClone(task)
    },
    async recaptureItem(itemId) {
      const task = tasks.find((item) =>
        item.items?.some((row) => row.id === itemId),
      )
      if (!task) throw new Error('演示采集明细不存在')
      task.status = 'running'
      task.runningCount = 1
      task.failedCount = 0
      return structuredClone(task)
    },
  }
}

export function resetCollectionTaskMockStore(): void {
  tasks.splice(0, tasks.length, ...structuredClone(initialTasks))
  sequence = 40
}
