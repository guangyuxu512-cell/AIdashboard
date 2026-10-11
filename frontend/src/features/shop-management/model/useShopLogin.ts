import {
  computed,
  onScopeDispose,
  reactive,
  watch,
  type InjectionKey,
} from 'vue'
import { useQueryClient } from '@tanstack/vue-query'
import { useMessage } from 'naive-ui'
import { useAuthStore } from '@/stores/auth'
import { getPlatformDefinition } from '@/entities/platform'
import { shopQueryKeys, type ShopListItemViewModel } from '@/entities/shop'
import {
  shopSessionDataSource,
  shopSessionQueryKeys,
} from '@/entities/shop-session'
import { ApiError } from '@/shared/api'
import { startManagementLoginPolling } from './management-login-poller'

export function supportsShopLogin(platform: string): boolean {
  const capabilities = getPlatformDefinition(platform)?.capabilities
  return (
    capabilities?.authentication === 'available' &&
    capabilities.sessionCapture === 'available'
  )
}

export function validationFailureMessage(error: unknown): string {
  return error instanceof ApiError && error.code === 'AUTH_INVALID'
    ? '登录状态已失效，请点击登录重新授权'
    : '本次验证未完成，请稍后重试或点击登录'
}

interface LoginFlow {
  shopId: string
  scopeVersion: number
  attemptId?: string
  leaseId?: string
  stop?: () => void
}
export const shopLoginKey: InjectionKey<ReturnType<typeof useShopLogin>> =
  Symbol('shop-login')

// One page-owned flow is shared by list/detail. Completed browsing windows are
// owned only by Main; no renderer lease or captured payload survives success.
export function useShopLogin() {
  const auth = useAuthStore()
  const queries = useQueryClient()
  const message = useMessage()
  const active = new Map<string, LoginFlow>()
  let scopeVersion = 0
  const feedback = reactive(
    new Map<
      string,
      { busy: boolean; error: string | null; status: string | null }
    >(),
  )
  const canLogin = computed(() => auth.isSuperAccount)
  function current(flow: LoginFlow) {
    return (
      flow.scopeVersion === scopeVersion && active.get(flow.shopId) === flow
    )
  }
  async function refresh(shopId: string) {
    await Promise.all([
      queries.invalidateQueries({
        queryKey: shopSessionQueryKeys.shop(shopId),
      }),
      queries.invalidateQueries({ queryKey: shopQueryKeys.all }),
    ])
  }
  async function cancel(shopId: string) {
    const flow = active.get(shopId)
    if (!flow) return
    active.delete(shopId)
    flow.stop?.()
    feedback.delete(shopId)
    if (flow.attemptId)
      await window.desktop?.managementLogin
        ?.close(flow.attemptId)
        .catch(() => undefined)
    if (flow.leaseId)
      await shopSessionDataSource
        .releaseRefreshLease(shopId, flow.leaseId)
        .catch(() => undefined)
  }
  async function fail(flow: LoginFlow, text: string) {
    if (!current(flow)) return
    await cancel(flow.shopId)
    if (flow.scopeVersion !== scopeVersion || active.has(flow.shopId)) return
    feedback.set(flow.shopId, { busy: false, error: text, status: null })
    message.error(text)
  }
  async function login(shop: ShopListItemViewModel) {
    if (!canLogin.value || !supportsShopLogin(shop.platform)) return
    const bridge = window.desktop?.managementLogin
    if (!bridge?.focusShop) {
      message.info('请安装支持店铺登录同步的新桌面版本')
      return
    }
    const teamId = auth.activeTeamId
    if (!teamId) {
      message.info('请先选择当前团队')
      return
    }
    if (shop.platform !== 'douyin' && shop.platform !== 'pdd') return
    if (active.has(shop.shopId)) {
      await bridge
        .focusShop({ platform: shop.platform, shopId: shop.shopId, teamId })
        .catch(() => undefined)
      return
    }
    const flow: LoginFlow = { shopId: shop.shopId, scopeVersion }
    active.set(shop.shopId, flow)
    feedback.set(shop.shopId, {
      busy: true,
      error: null,
      status: '正在打开店铺登录窗口',
    })
    try {
      const focused = await bridge.focusShop({
        platform: shop.platform,
        shopId: shop.shopId,
        teamId,
      })
      if (!current(flow)) return
      if (focused) {
        active.delete(shop.shopId)
        feedback.delete(shop.shopId)
        return
      }
      const lease = await shopSessionDataSource.acquireRefreshLease(shop.shopId)
      flow.leaseId = lease.leaseId
      if (!current(flow)) {
        await shopSessionDataSource.releaseRefreshLease(
          shop.shopId,
          lease.leaseId,
        )
        return
      }
      const opened = await bridge.open({
        platform: shop.platform,
        teamId,
        recovery: {
          shopId: shop.shopId,
          leaseId: lease.leaseId,
          expectedVersion: lease.expectedVersion,
        },
      })
      flow.attemptId = opened.attemptId
      if (!current(flow)) {
        await bridge.close(opened.attemptId)
        return
      }
      flow.stop = startManagementLoginPolling({
        attemptId: opened.attemptId,
        getStatus: bridge.getStatus,
        async onStatus(status) {
          if (!current(flow)) return
          feedback.set(shop.shopId, {
            busy: true,
            error: null,
            status: status.message,
          })
          if (status.status === 'closed') {
            await cancel(shop.shopId)
            return
          }
          if (status.status === 'failed') {
            await fail(flow, '本次验证未完成，请重新打开登录窗口')
            return
          }
          if (status.status !== 'identified') return
          const result = await bridge.refresh(status.attemptId)
          if (!current(flow)) return
          if (
            result.shopId !== shop.shopId ||
            result.status !== 'valid' ||
            result.sessionVersion !== lease.expectedVersion + 1 ||
            !result.validatedAt
          )
            throw new Error('未取得本次有效验证结果')
          await shopSessionDataSource.confirmRecovery(
            result.shopId,
            result.sessionVersion,
            result.validatedAt,
          )
          if (!current(flow)) return
          let readRefreshFailed = false
          try {
            await refresh(shop.shopId)
          } catch {
            readRefreshFailed = true
          }
          if (!current(flow)) return
          active.delete(shop.shopId)
          feedback.delete(shop.shopId)
          message.success('登录状态已更新')
          if (readRefreshFailed)
            message.warning('店铺信息刷新未完成，请刷新列表')
          if (result.profileMappingWarning)
            message.warning(result.profileMappingWarning)
        },
        onError() {
          void fail(
            flow,
            '本次验证未完成，原登录状态保留；请重新登录或稍后重试',
          )
        },
      })
    } catch {
      await fail(flow, '本次验证未完成，原登录状态保留；请重新登录或稍后重试')
    }
  }
  watch(
    () =>
      `${auth.currentUser?.userId}:${auth.activeTeamId}:${auth.isSuperAccount}`,
    () => {
      scopeVersion++
      for (const shopId of active.keys()) void cancel(shopId)
      feedback.clear()
    },
  )
  onScopeDispose(() => {
    scopeVersion++
    for (const shopId of active.keys()) void cancel(shopId)
  })
  return { canLogin, feedback, login, cancel, refresh }
}
