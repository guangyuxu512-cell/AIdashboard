import type {
  SelectionBasicRunDto,
  SelectionBasicStatusDto,
} from '../api/selection-read-api'
import { formatCandidateTime } from './candidate-display'

export function basicFieldHint(
  status: SelectionBasicStatusDto | null | undefined,
  name: 'category_path' | 'first_on_shelf_date' | 'bad_comment_rate',
): string {
  if (!status) return ''
  const field = status[name]
  const state = {
    available: '已取得',
    missing: '未返回',
    null: '空值',
    invalid: '响应异常',
    unknown: '尚未取得',
  }[field.last_attempt_state]
  return `本次${state} · 尝试 ${formatCandidateTime(status.attempted_at)} · 已保存值获取时间 ${formatCandidateTime(field.last_success_at)}${field.last_attempt_state !== 'available' && field.last_success_at ? '；保留此前有效值' : ''}`
}

export function basicFailure(
  code?: string | null,
  stage?: string | null,
  business?: string | number | null,
): string {
  if (code === 'AUTH_INVALID' || code === 'SHOP_SESSION_AUTHENTICATION_INVALID')
    return '店铺登录已失效，请重新登录'
  if (code === 'SHOP_SESSION_NOT_CONFIGURED') return '请先登录请求店铺'
  if (code === 'PLATFORM_SIGNER_FAILED') return '签名失败，可重试'
  if (code === 'PLATFORM_TIMEOUT' || code === 'PLATFORM_REQUEST_FAILED')
    return '网络请求失败，可重试'
  if (code === 'DOUYIN_SELECTION_BUSINESS_REJECTED')
    return `平台业务拒绝${business == null ? '' : `（${business}）`}，原因未确定`
  if (
    code === 'PLATFORM_RESPONSE_INVALID' ||
    code === 'DOUYIN_SELECTION_PRODUCT_ID_MISMATCH'
  )
    return '平台响应异常，请重试或核验商品'
  if (stage === 'authorization') return '当前店铺或权限不可执行，请核验授权'
  if (stage === 'session') return '店铺会话不可用，请核验登录'
  return '基础信息尚未补齐，可重试'
}
export function basicStatus(
  status?: SelectionBasicStatusDto | null,
): string | null {
  if (!status) return null
  if (status.state === 'succeeded') return '基础信息已更新'
  return basicFailure(
    status.error_code,
    status.error_stage,
    status.platform_business_code,
  )
}
export function basicRunStatus(run: SelectionBasicRunDto): string {
  if (run.status === 'pending') return '基础信息等待更新'
  if (run.status === 'running') return '基础信息更新中'
  if (run.status === 'succeeded') return '基础信息已更新'
  if (run.status === 'partial') return '基础信息部分更新，未取得字段保留原值'
  if (run.status === 'interrupted') return '基础信息更新中断，可重新提交'
  return basicFailure(
    run.error_code,
    run.error_stage,
    run.platform_business_code,
  )
}
