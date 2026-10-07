import { z } from 'zod'

import type {
  CategoryNode,
  SelectionCandidate,
  StrategyInput,
} from './contracts'

const optionalPrice = z
  .number()
  .finite()
  .nonnegative('价格不能小于 0')
  .nullable()
const optionalRank = z
  .number()
  .int('排名须为整数')
  .min(1, '排名从 1 开始')
  .nullable()
export const strategySchema = z
  .object({
    name: z.string(),
    shopId: z.string().min(1).nullable().refine(Boolean, '请选择请求店铺'),
    creatorId: z.string().min(1).nullable().refine(Boolean, '请选择达人账号'),
    channel: z.enum(['short-video', 'baiying']),
    categoryId: z.string().nullable(),
    period: z.enum(['realtime', '1d', '7d', '30d']),
    brand: z.enum(['all', 'known', 'unknown']),
    priceMode: z.enum(['all', 'custom']),
    priceAbove: optionalPrice,
    priceBelow: optionalPrice,
    firstListedOnly: z.boolean(),
    rankFrom: optionalRank,
    rankTo: optionalRank,
    scheduled: z.boolean(),
    scheduleKind: z.enum(['hourly', 'daily']),
    dailyTime: z.string(),
    enabled: z.boolean(),
  })
  .superRefine((value, ctx) => {
    if (value.channel === 'short-video' && value.priceMode === 'custom') {
      if (value.priceAbove === null && value.priceBelow === null)
        ctx.addIssue({
          code: 'custom',
          path: ['priceAbove'],
          message: '请填写至少一个价格边界',
        })
      if (
        value.priceAbove !== null &&
        value.priceBelow !== null &&
        value.priceAbove >= value.priceBelow
      )
        ctx.addIssue({
          code: 'custom',
          path: ['priceBelow'],
          message: '价格小于须大于价格大于',
        })
    }
    if (
      value.rankFrom !== null &&
      value.rankTo !== null &&
      value.rankFrom > value.rankTo
    )
      ctx.addIssue({
        code: 'custom',
        path: ['rankTo'],
        message: '结束排名不能小于起始排名',
      })
    if (
      value.scheduled &&
      value.scheduleKind === 'daily' &&
      !/^([01]\d|2[0-3]):[0-5]\d$/.test(value.dailyTime)
    )
      ctx.addIssue({
        code: 'custom',
        path: ['dailyTime'],
        message: '请输入有效的每日时间',
      })
  })

export function validateStrategy(
  input: StrategyInput,
  saving: boolean,
): Record<string, string> {
  const errors: Record<string, string> = {}
  const result = strategySchema.safeParse(input)
  if (!result.success)
    result.error.issues.forEach((issue) => {
      errors[String(issue.path[0])] = issue.message
    })
  if (saving && !input.name.trim()) errors.name = '请输入策略名称'
  return errors
}

export function categoryOptions(nodes: CategoryNode[]): {
  value: string
  label: string
  children?: ReturnType<typeof categoryOptions>
}[] {
  return nodes.map((node) => ({
    value: node.id,
    label: node.name,
    children: node.children?.length
      ? [
          { value: `${node.id}/*`, label: '全部' },
          ...categoryOptions(node.children),
        ]
      : undefined,
  }))
}

export function compareCandidates(
  a: SelectionCandidate,
  b: SelectionCandidate,
  field: 'listedAt' | 'negativeReviewRate',
  direction: 'ascend' | 'descend',
): number {
  const left =
    field === 'listedAt'
      ? a.listedAt === null
        ? null
        : Date.parse(a.listedAt)
      : a.negativeReviewRate
  const right =
    field === 'listedAt'
      ? b.listedAt === null
        ? null
        : Date.parse(b.listedAt)
      : b.negativeReviewRate
  if (left === null && right !== null) return 1
  if (left !== null && right === null) return -1
  if (left !== null && right !== null && left !== right)
    return (left - right) * (direction === 'ascend' ? 1 : -1)
  return a.id.localeCompare(b.id, 'en')
}

export function conditionSummary(value: StrategyInput): string {
  if (value.channel === 'baiying') return '—'
  const periods = {
    realtime: '实时',
    '1d': '近1天',
    '7d': '近7天',
    '30d': '近30天',
  }
  const brands = { all: '不限品牌', known: '知名品牌', unknown: '非知名品牌' }
  return [
    periods[value.period],
    brands[value.brand],
    value.categoryId ? '已选类目' : '全部类目',
    value.priceMode === 'custom'
      ? `${value.priceAbove === null ? '' : `价格>${value.priceAbove}`} ${value.priceBelow === null ? '' : `价格<${value.priceBelow}`}`.trim()
      : '不限价格',
    value.firstListedOnly ? '首次上榜' : null,
    value.rankFrom !== null || value.rankTo !== null
      ? `排名 ${value.rankFrom ?? '—'}–${value.rankTo ?? '—'}`
      : null,
  ]
    .filter(Boolean)
    .join(' · ')
}
