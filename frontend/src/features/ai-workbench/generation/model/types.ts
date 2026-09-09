import {
  GENERATION_SIZE_OPTIONS as SHARED_GENERATION_SIZE_OPTIONS,
  type GenerationConfig,
  type GenerationSize,
} from '../../shared/model/generation-config'
import {
  GENERATION_OUTPUT_ROLE_META,
  type GenerationOutputRole,
} from '../../shared/model/generation-output'
import {
  type GenerationInputSlotKey,
  type GenerationMode,
  type GenerationSourceRole,
} from './generation-mode-registry'

export type {
  GenerationConfig,
  GenerationOutputFormat,
  GenerationSize,
} from '../../shared/model/generation-config'
export { GENERATION_OUTPUT_FORMAT_META } from '../../shared/model/generation-config'
export { GENERATION_MODE_META } from '../../shared/model/generation-mode'
export { GENERATION_OUTPUT_ROLE_META }
export type { GenerationOutputRole }
export type {
  GenerationInputSlotKey,
  GenerationMode,
  GenerationSourceRole,
} from './generation-mode-registry'

export type GenerationWorkMode = 'INSTANT' | 'BATCH'

export type GenerationOutputRange = 'ALL' | GenerationOutputRole

export type GenerationSourceType = 'LOCAL_UPLOAD' | 'ASSET_LIBRARY'

export type BatchProductScope = 'ALL_ENABLED' | 'SELECTED'

export type BatchTemplateSource = 'PRODUCT_CONFIGURED' | 'CURRENT_SELECTION'

export type GenerationRecordSourceType = GenerationWorkMode

export type GenerationRecordStatus =
  'QUEUED' | 'RUNNING' | 'SUCCESS' | 'PARTIAL_FAILED' | 'FAILED'

export type GenerationResultStatus = 'SUCCESS' | 'FAILED'

export type GenerationExecutionResultStatus =
  'WAITING' | 'RUNNING' | 'SUCCESS' | 'FAILED'

export type GenerationExecutionStatus =
  GenerationExecutionResultStatus | 'PARTIAL_FAILED'

export type BatchExecutionStatus = GenerationExecutionStatus

export type BatchExecutionFilter = 'ALL' | 'RUNNING' | 'FAILED'

export type BatchSkipReason =
  | 'NO_PRODUCT_SOURCE'
  | 'NO_TEMPLATE_GROUPS'
  | 'NO_STYLE_REFERENCE'
  | 'MODE_DISABLED'
  | 'GROUP_DISABLED'
  | 'NO_ENABLED_TEMPLATES'
  | 'MODEL_INPUT_LIMIT'
  | 'MODEL_SIZE_UNSUPPORTED'

export interface GenerationSourceImageView {
  id: string
  name: string
  previewUrl: string
  thumbnailUrl?: string
  role: GenerationSourceRole
  sourceType: GenerationSourceType
  productId?: string
  productName?: string
  objectUrl?: boolean
}

export interface GenerationTemplateView extends GenerationConfig {
  id: string
  groupId: string
  groupName: string
  name: string
  mode: GenerationMode
  enabled: boolean
  outputRole: Exclude<GenerationOutputRange, 'ALL'>
  sortOrder: number
}

export interface GenerationTemplateGroupView {
  id: string
  name: string
  mode: GenerationMode
  enabled: boolean
  templates: GenerationTemplateView[]
}

export interface GenerationProductView {
  id: string
  name: string
  enabled: boolean
  normalGenerationEnabled: boolean
  styleReplicationEnabled: boolean
  normalTemplateGroupIds: string[]
  styleReplicationTemplateGroupIds: string[]
  assets: GenerationSourceImageView[]
}

export interface GenerationAppliedTemplate {
  id: string
  name: string
}

export interface InstantGenerationDraft {
  mode: GenerationMode
  inputs: Record<GenerationInputSlotKey, GenerationSourceImageView[]>
  appliedTemplate: GenerationAppliedTemplate | null
  config: GenerationConfig
}

export interface BatchGenerationDraft {
  mode: GenerationMode
  productScope: BatchProductScope
  selectedProductIds: string[]
  templateSource: BatchTemplateSource
  selectedTemplateGroupIds: string[]
  outputRange: GenerationOutputRange
}

export interface GenerationResultView {
  id: string
  name: string
  previewUrl: string
  thumbnailUrl?: string
  status: GenerationResultStatus
  outputRole: Exclude<GenerationOutputRange, 'ALL'>
  size: GenerationSize
  savedToProductId?: string
}

export interface GenerationExecutionResultView {
  id: string
  slotIndex: number
  name?: string
  status: GenerationExecutionResultStatus
  previewUrl?: string
  thumbnailUrl?: string
  assetId?: string
  outputRole?: Exclude<GenerationOutputRange, 'ALL'>
  size?: GenerationSize
  savedToProductId?: string
  errorCode?: string
  errorMessage?: string
}

export interface InstantExecutionView {
  id: string
  status: GenerationExecutionStatus
  totalCount: number
  completedCount: number
  successCount: number
  runningCount: number
  waitingCount: number
  failedCount: number
  results: GenerationExecutionResultView[]
}

export interface BatchTemplateExecutionView {
  templateId: string
  templateName: string
  outputRole: Exclude<GenerationOutputRange, 'ALL'>
  status: BatchExecutionStatus
  completedCount: number
  totalCount: number
  results: GenerationExecutionResultView[]
}

export interface BatchTemplateGroupExecutionView {
  templateGroupId: string
  templateGroupName: string
  status: BatchExecutionStatus
  completedCount: number
  totalCount: number
  templates: BatchTemplateExecutionView[]
}

export interface BatchProductExecutionView {
  productId: string
  productName: string
  status: BatchExecutionStatus
  completedCount: number
  totalCount: number
  templateGroups: BatchTemplateGroupExecutionView[]
}

export interface BatchExecutionView {
  id: string
  status: BatchExecutionStatus
  totalItems: number
  successItems: number
  runningItems: number
  waitingItems: number
  failedItems: number
  products: BatchProductExecutionView[]
}

export interface BatchTemplateResultView {
  templateId: string
  templateName: string
  outputRole: Exclude<GenerationOutputRange, 'ALL'>
  results: GenerationResultView[]
}

export interface BatchTemplateGroupResultView {
  groupId: string
  groupName: string
  templates: BatchTemplateResultView[]
}

export interface BatchProductResultView {
  productId: string
  productName: string
  groups: BatchTemplateGroupResultView[]
}

export interface BatchPreflightIssueView {
  productId: string
  productName: string
  reason: BatchSkipReason
}

export interface BatchPreflightProductPlan {
  productId: string
  productName: string
  styleReferenceCount: number
  groups: Array<{
    group: GenerationTemplateGroupView
    templates: GenerationTemplateView[]
  }>
  itemCount: number
}

export interface BatchPreflightView {
  productCount: number
  executableProductCount: number
  skippedProductCount: number
  templateGroupCount: number
  generationItemCount: number
  issues: BatchPreflightIssueView[]
  plans: BatchPreflightProductPlan[]
}

export interface GenerationRecordInputSlotSnapshot {
  key: GenerationInputSlotKey
  label: string
  images: GenerationSourceImageView[]
}

export interface InstantGenerationRecordDetail {
  kind: 'INSTANT'
  executionId: string
  inputSlots: GenerationRecordInputSlotSnapshot[]
  templateId: string | null
  templateName: string | null
  effectiveConfig: GenerationConfig
  results: GenerationExecutionResultView[]
}

export interface BatchGenerationRecordDetail {
  kind: 'BATCH'
  productCount: number
  templateGroupCount: number
  generationItemCount: number
  successCount: number
  failedCount: number
  results: BatchProductResultView[]
}

export interface GenerationRecordView {
  id: string
  sourceType: GenerationRecordSourceType
  mode: GenerationMode
  status: GenerationRecordStatus
  createdAt: string
  createdBy: string
  summary: string
  resultSummary: string
  detail: InstantGenerationRecordDetail | BatchGenerationRecordDetail
}

export interface GenerationVisualMockFixture {
  products: GenerationProductView[]
  templateGroups: GenerationTemplateGroupView[]
  records: GenerationRecordView[]
  resultPreviewUrls: string[]
}

export const GENERATION_WORK_MODE_META: Record<
  GenerationWorkMode,
  { label: string }
> = {
  INSTANT: { label: '即时生成' },
  BATCH: { label: '批量生成' },
}

export const GENERATION_RECORD_SOURCE_TYPE_META = GENERATION_WORK_MODE_META

export const GENERATION_OUTPUT_RANGE_META: Record<
  GenerationOutputRange,
  { label: string }
> = {
  ALL: { label: '全部' },
  MAIN_IMAGE: { label: `仅${GENERATION_OUTPUT_ROLE_META.MAIN_IMAGE.label}` },
  DETAIL_IMAGE: {
    label: `仅${GENERATION_OUTPUT_ROLE_META.DETAIL_IMAGE.label}`,
  },
}

export const GENERATION_RESULT_STATUS_META: Record<
  GenerationResultStatus,
  { label: string; tone: 'success' | 'error' }
> = {
  SUCCESS: { label: '成功', tone: 'success' },
  FAILED: { label: '失败', tone: 'error' },
}

export const GENERATION_EXECUTION_RESULT_STATUS_META: Record<
  GenerationExecutionResultStatus,
  {
    label: string
    tone: 'neutral' | 'info' | 'success' | 'error'
  }
> = {
  WAITING: { label: '等待中', tone: 'neutral' },
  RUNNING: { label: '生成中', tone: 'info' },
  SUCCESS: { label: '成功', tone: 'success' },
  FAILED: { label: '失败', tone: 'error' },
}

export const GENERATION_EXECUTION_STATUS_META: Record<
  GenerationExecutionStatus,
  {
    label: string
    tone: 'neutral' | 'info' | 'success' | 'warning' | 'error'
  }
> = {
  WAITING: { label: '等待中', tone: 'neutral' },
  RUNNING: { label: '生成中', tone: 'info' },
  SUCCESS: { label: '已完成', tone: 'success' },
  PARTIAL_FAILED: { label: '部分失败', tone: 'warning' },
  FAILED: { label: '失败', tone: 'error' },
}

export const BATCH_EXECUTION_STATUS_META = GENERATION_EXECUTION_STATUS_META

export const GENERATION_RECORD_STATUS_META: Record<
  GenerationRecordStatus,
  { label: string; tone: 'neutral' | 'info' | 'success' | 'warning' | 'error' }
> = {
  QUEUED: { label: '排队中', tone: 'neutral' },
  RUNNING: { label: '运行中', tone: 'info' },
  SUCCESS: { label: '成功', tone: 'success' },
  PARTIAL_FAILED: { label: '部分失败', tone: 'warning' },
  FAILED: { label: '失败', tone: 'error' },
}

export const BATCH_SKIP_REASON_META: Record<
  BatchSkipReason,
  { label: string }
> = {
  NO_PRODUCT_SOURCE: { label: '无商品素材' },
  NO_TEMPLATE_GROUPS: { label: '未绑定模板组' },
  NO_STYLE_REFERENCE: { label: '风格复刻无参考图' },
  MODE_DISABLED: { label: '产品生成模式未启用' },
  GROUP_DISABLED: { label: '模板组停用' },
  NO_ENABLED_TEMPLATES: { label: '所有模板均停用' },
  MODEL_INPUT_LIMIT: { label: '输入图片超过当前模型上限' },
  MODEL_SIZE_UNSUPPORTED: { label: '模板比例不受当前模型支持' },
}

export const GENERATION_SIZE_OPTIONS = SHARED_GENERATION_SIZE_OPTIONS
