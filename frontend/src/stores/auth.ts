import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import {
  humanAuthDataSource,
  type CurrentHumanUser,
  type CurrentModuleAccess,
  type HumanAuthDataSource,
  type HumanLoginInput,
  type HumanTeamMembership,
} from '@/entities/human-auth'
import { getErrorMessage, isHumanSessionError } from '@/shared/api'

export const ACTIVE_TEAM_STORAGE_PREFIX = 'control-center.active-team'

export type AuthStatus = 'idle' | 'restoring' | 'authenticated' | 'anonymous'

interface AuthEffects {
  onTeamChanged: () => void
  onAuthCleared: () => void
  onAuthRestoreRejected: () => void
}

const authEffects: AuthEffects = {
  onTeamChanged: () => undefined,
  onAuthCleared: () => undefined,
  onAuthRestoreRejected: () => undefined,
}

export function configureAuthEffects(effects: Partial<AuthEffects>): void {
  Object.assign(authEffects, effects)
}

function storageKey(userId: string): string {
  return `${ACTIVE_TEAM_STORAGE_PREFIX}.${userId}`
}

function readStoredTeamId(userId: string): string | null {
  try {
    return window.localStorage.getItem(storageKey(userId))
  } catch {
    return null
  }
}

function persistTeamId(userId: string, teamId: string): void {
  try {
    window.localStorage.setItem(storageKey(userId), teamId)
  } catch {
    // Team persistence is optional when storage is unavailable.
  }
}

function removeStoredTeamId(userId: string): void {
  try {
    window.localStorage.removeItem(storageKey(userId))
  } catch {
    // Team persistence is optional when storage is unavailable.
  }
}

export const useAuthStore = defineStore('auth', () => {
  const status = ref<AuthStatus>('idle')
  const currentUser = ref<CurrentHumanUser | null>(null)
  const teams = ref<HumanTeamMembership[]>([])
  const activeTeamId = ref<string | null>(null)
  const currentModuleAccess = ref<CurrentModuleAccess | null>(null)
  const restoreError = ref<string | null>(null)
  let initialization: Promise<void> | null = null
  let moduleAccessRefresh: {
    context: string
    promise: Promise<void>
  } | null = null
  let moduleAccessRevision = 0
  let dataSource: HumanAuthDataSource = humanAuthDataSource

  const isAuthenticated = computed(
    () => status.value === 'authenticated' && currentUser.value !== null,
  )
  const activeTeams = computed(() =>
    teams.value.filter((item) => item.teamEnabled && item.membershipEnabled),
  )
  const currentTeam = computed(
    () =>
      activeTeams.value.find((item) => item.teamId === activeTeamId.value) ??
      null,
  )
  const isSuperAccount = computed(
    () => currentModuleAccess.value?.isSuperAccount === true,
  )
  const hasTeamContext = computed(() => currentTeam.value !== null)
  const requiresTeamSelection = computed(
    () =>
      isAuthenticated.value &&
      !isSuperAccount.value &&
      currentTeam.value === null,
  )
  const allowedModuleCodes = computed(
    () => new Set(currentModuleAccess.value?.moduleCodes ?? []),
  )
  const isAccessAdministrator = computed(() => isSuperAccount.value)

  function applyAuthenticatedSession(
    user: CurrentHumanUser,
    memberships: HumanTeamMembership[],
  ): void {
    moduleAccessRevision += 1
    moduleAccessRefresh = null
    currentUser.value = user
    teams.value = memberships
    const available = memberships.filter(
      (item) => item.teamEnabled && item.membershipEnabled,
    )
    const storedTeamId = readStoredTeamId(user.userId)
    // A stored explicit Team context may be restored.  Do not choose the
    // first Team yet: the following module-access response tells us whether
    // the user is the super account, which has no default Team by design.
    activeTeamId.value =
      available.find((item) => item.teamId === storedTeamId)?.teamId ?? null
    if (activeTeamId.value) persistTeamId(user.userId, activeTeamId.value)
    currentModuleAccess.value = null
    restoreError.value = null
    status.value = 'authenticated'
  }

  function clearAuthState(clearPersistedTeam = false): void {
    if (clearPersistedTeam && currentUser.value) {
      removeStoredTeamId(currentUser.value.userId)
    }
    moduleAccessRevision += 1
    moduleAccessRefresh = null
    currentUser.value = null
    teams.value = []
    activeTeamId.value = null
    currentModuleAccess.value = null
    status.value = 'anonymous'
    authEffects.onAuthCleared()
  }

  async function initialize(): Promise<void> {
    if (status.value !== 'idle') return
    if (initialization) return initialization
    status.value = 'restoring'
    initialization = (async () => {
      try {
        const user = await dataSource.getCurrentUser()
        const memberships = await dataSource.listMyTeams()
        applyAuthenticatedSession(user, memberships)
        await refreshModuleAccess()
      } catch (error) {
        const sessionRejected = isHumanSessionError(error)
        currentUser.value = null
        teams.value = []
        activeTeamId.value = null
        currentModuleAccess.value = null
        status.value = 'anonymous'
        restoreError.value = sessionRejected ? null : getErrorMessage(error)
        if (sessionRejected) authEffects.onAuthRestoreRejected()
      }
    })()
    try {
      await initialization
    } finally {
      initialization = null
    }
  }

  async function login(input: HumanLoginInput): Promise<void> {
    const user = await dataSource.login(input)
    const memberships = await dataSource.listMyTeams()
    applyAuthenticatedSession(user, memberships)
    await refreshModuleAccess()
  }

  async function logout(): Promise<void> {
    await dataSource.logout()
    restoreError.value = null
    clearAuthState(true)
  }

  async function selectTeam(teamId: string | null): Promise<void> {
    if (!currentUser.value) return
    if (teamId === null) {
      if (!isSuperAccount.value) return
    } else if (!activeTeams.value.some((item) => item.teamId === teamId)) {
      return
    }
    if (activeTeamId.value === teamId) return
    moduleAccessRevision += 1
    moduleAccessRefresh = null
    currentModuleAccess.value = null
    activeTeamId.value = teamId
    if (teamId === null) removeStoredTeamId(currentUser.value.userId)
    else persistTeamId(currentUser.value.userId, teamId)
    authEffects.onTeamChanged()
    await refreshModuleAccess()
  }

  async function refreshModuleAccess(): Promise<void> {
    if (!isAuthenticated.value) {
      currentModuleAccess.value = null
      return
    }
    const userId = currentUser.value?.userId
    const teamId = activeTeamId.value
    const requestedRevision = moduleAccessRevision
    const context = `${requestedRevision}:${userId ?? 'none'}:${teamId ?? 'none'}`
    if (moduleAccessRefresh?.context === context) {
      await moduleAccessRefresh.promise
      return
    }
    const refresh = (async () => {
      const access = await dataSource.getCurrentModuleAccess()
      if (
        moduleAccessRevision !== requestedRevision ||
        currentUser.value?.userId !== userId ||
        activeTeamId.value !== teamId
      )
        return
      currentModuleAccess.value = access
      if (
        !access.isSuperAccount &&
        !activeTeamId.value &&
        currentUser.value &&
        activeTeams.value.length === 1
      ) {
        const onlyTeamId = activeTeams.value[0]?.teamId
        if (onlyTeamId) {
          activeTeamId.value = onlyTeamId
          persistTeamId(currentUser.value.userId, onlyTeamId)
        }
      }
    })()
    const pending = { context, promise: refresh }
    moduleAccessRefresh = pending
    try {
      await refresh
    } finally {
      if (moduleAccessRefresh === pending) moduleAccessRefresh = null
    }
  }

  function expireSession(): void {
    restoreError.value = null
    if (status.value === 'anonymous') return
    clearAuthState(true)
  }

  function setDataSource(source: HumanAuthDataSource): void {
    moduleAccessRevision += 1
    moduleAccessRefresh = null
    dataSource = source
  }

  return {
    status,
    currentUser,
    teams,
    activeTeamId,
    currentModuleAccess,
    restoreError,
    isAuthenticated,
    isSuperAccount,
    hasTeamContext,
    activeTeams,
    currentTeam,
    requiresTeamSelection,
    allowedModuleCodes,
    isAccessAdministrator,
    initialize,
    login,
    logout,
    selectTeam,
    refreshModuleAccess,
    expireSession,
    setDataSource,
  }
})
