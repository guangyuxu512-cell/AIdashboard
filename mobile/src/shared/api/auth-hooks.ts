export interface ApiAuthHooks {
  getAuthorizationHeader?: () => Promise<string | null> | string | null
  onUnauthorized?: () => Promise<void> | void
}

let authHooks: ApiAuthHooks = {}

export function configureApiAuthHooks(hooks: ApiAuthHooks): void {
  authHooks = hooks
}

export function getApiAuthHooks(): Readonly<ApiAuthHooks> {
  return authHooks
}
