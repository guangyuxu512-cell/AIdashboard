import type { SelectionExecutionSummary } from './contracts'

export function runWindow(run: SelectionExecutionSummary): string {
  const request = run.request_conditions
  if (!request) return '—'
  const state = request.date_outcome?.state
  const scope =
    state === 'backup' || state === 'backup_empty'
      ? request.date_plan?.backup_scope
      : request.scope
  if (!scope) return '—'
  const range = `${scope.begin_date.slice(0, 10).replaceAll('/', '-')}～${scope.end_date.slice(0, 10).replaceAll('/', '-')}`
  const primary =
    request.date_outcome?.fallback_reason === 'primary_business_rejection_probe'
      ? `首查被平台拒绝（${request.date_outcome.primary_error?.platform_business_code ?? '—'}）`
      : '首查为空'
  const label =
    state === 'backup'
      ? '已回退一天'
      : state === 'backup_empty'
        ? '已回退一天 · 备用窗口为空'
        : state === 'both_empty'
          ? '两个窗口均已检查为空'
          : state === 'fallback_checking'
            ? `${primary}，${run.status === 'interrupted' ? '补查中断' : '正在补查'}`
            : state === 'fallback_failed'
              ? `${primary}、回退失败`
              : ''
  return `${range}${label ? ` · ${label}` : ''}`
}

export function runResult(run: SelectionExecutionSummary): string {
  if (run.status === 'pending') return '等待获取'
  if (run.status === 'running') return `获取中 · 已保存 ${run.saved_count} 项`
  if (run.status === 'interrupted')
    return '执行中断，请核对已保存结果后重新提交'
  if (
    run.status === 'failed' &&
    run.error_code === 'DOUYIN_SELECTION_BUSINESS_REJECTED' &&
    run.platform_business_code != null
  )
    return `获取失败 · 平台业务拒绝（${run.platform_business_code}），原因未确定`
  if (run.status === 'failed')
    if (
      ['AUTH_INVALID', 'SHOP_SESSION_AUTHENTICATION_INVALID'].includes(
        run.error_code ?? '',
      )
    )
      return '获取失败 · 店铺登录已失效，请重新登录'
  if (
    run.status === 'failed' &&
    run.error_code === 'SHOP_SESSION_NOT_CONFIGURED'
  )
    return '获取失败 · 请先登录请求店铺'
  if (run.status === 'failed')
    return `获取失败 · ${run.error_stage ?? run.error_code ?? '原因未确定'}`
  if (run.status === 'partial')
    return `已保存 ${run.saved_count} 项 · 补充未完成 ${run.supplement_failed_count} 项${run.error_code ? ` · ${run.error_stage ?? run.error_code}` : ''}`
  return run.result_count === 0
    ? '获取成功，该范围没有结果'
    : `获取完成 · 已保存 ${run.saved_count} 项`
}

export function triggerFailure(
  code: string | null,
  stage: string | null,
): string {
  if (
    ['AUTH_INVALID', 'SHOP_SESSION_AUTHENTICATION_INVALID'].includes(code ?? '')
  )
    return '触发失败 · 店铺登录已失效，请重新登录'
  if (code === 'SHOP_SESSION_NOT_CONFIGURED')
    return '触发失败 · 请先登录请求店铺'
  const labels: Record<string, string> = {
    session: '店铺会话不可用，请核验登录',
    authorization: '权限已变更，请核验团队与店铺授权',
    signer: '签名未完成，请稍后核验',
    http: '平台请求未完成',
    response_parse: '平台响应结构无效',
    conditions: '请核验已保存的条件',
  }
  return `触发失败 · ${labels[stage ?? ''] ?? '执行未完成，请核验运行记录'}`
}
