import { ApiClientError } from '@/shared/api'

export function getLoginErrorMessage(error: unknown): string {
  if (error instanceof ApiClientError) {
    if (error.code === 'HUMAN_LOGIN_FAILED') {
      return '登录账号或密码错误'
    }
    if (error.code === 'HUMAN_USER_DISABLED') return '当前账号已停用'
  }
  return '登录失败，请重试'
}
