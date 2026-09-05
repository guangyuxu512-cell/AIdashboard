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
import { isHumanSessionError } from '@/shared/api'

export const ACTIVE_TEAM_STORAGE_PREFIX = 'control-center.active-team'

export type AuthStatus = 'idle' | 'restoring' | 'authenticated' | 'anonymous'

interface AuthEffects {
  onTeamChanged: () => void
  onAuthCleared: () => void
}

const authEffects: AuthEffects = {
  onTeamChanged: () => undefined,
  onAuthCleared: () => undefined,
}

export function configureAuthEffects(effects: Partial<AuthEffects>): void {
  Object.assign(authEffects, effects)
}

function activeTeamStorageKey(userId: string): string {
  return `${ACTIVE_TEAM_STORAGE_PREFIX}.${userId}`
}

function readStoredTeamId(userId: string): string | null {
  try {
    return window.localStorage.getItem(activeTeamStorageKey(userId))
  } catch {
    return null
  }
}

function persistTeamId(userId: string, teamId: string): void {
  try {
    window.localStorage.setItem(activeTeamStorageKey(userId), teamId)
  } catch {
    // Team preference persistence is optional when browser storage is blocked.
  }
}

function removeStoredTeamId(userId: string): void {
  try {
    window.localStorage.removeItem(activeTeamStorageKey(userId))
  } catch {
    // Team preference persistence is optional when browser storage is blocked.
  }
}

export const useAuthStore = defineStore('mobile-human-auth', () => {
  const status = ref<AuthStatus>('idle')
  const currentUser = ref<CurrentHumanUser | null>(null)
  const teams = ref<HumanTeamMembership[]>([])
  const activeTeamId = ref<string | null>(null)
  const currentModuleAccess = ref<CurrentModuleAccess | null>(null)
  const restoreError = ref<string | null>(null)
  let initialization: Promise<void> | null = null
  let dataSource: HumanAuthDataSource = humanAuthDataSource

  const isAuthenticated = computed(
    () => status.value === 'authenticated' && currentUser.value !== null,
  )
  const activeTeams = computed(() =>
    teams.value.filter((team) => team.teamEnabled && team.membershipEnabled),
  )
  const currentTeam = computed(
    () =>
      activeTeams.value.find((team) => team.teamId === activeTeamId.value) ??
      null,
  )
  const requiresTeamSelection = computed(
    () => isAuthenticated.value && currentTeam.value === null,
  )
  const allowedModuleCodes = computed(
    () => new Set(currentModuleAccess.value?.moduleCodes ?? []),
  )

  function applyAuthenticatedSession(
    user: CurrentHumanUser,
    memberships: HumanTeamMembership[],
  ): void {
    currentUser.value = user
    teams.value = memberships
    const availableTeams = memberships.filter(
      (team) => team.teamEnabled && team.membershipEnabled,
    )
    const storedTeamId = readStoredTeamId(user.userId)
    activeTeamId.value =
      availableTeams.find((team) => team.teamId === storedTeamId)?.teamId ??
      (availableTeams.length === 1 ? (availableTeams[0]?.teamId ?? null) : null)
    currentModuleAccess.value = null
    restoreError.value = null
    status.value = 'authenticated'

    if (activeTeamId.value) {
      persistTeamId(user.userId, activeTeamId.value)
    }
  }

  function clearAuthState(clearPersistedTeam: boolean): void {
    if (clearPersistedTeam && currentUser.value) {
      removeStoredTeamId(currentUser.value.userId)
    }
    currentUser.value = null
    teams.value = []
    activeTeamId.value = null
    currentModuleAccess.value = null
    status.value = 'anonymous'
    authEffects.onAuthCleared()
  }

  async function refreshModuleAccess(): Promise<void> {
    if (!isAuthenticated.value || !activeTeamId.value) {
      currentModuleAccess.value = null
      return
    }
    currentModuleAccess.value = await dataSource.getCurrentModuleAccess()
  }

  async function initialize(): Promise<void> {
    if (initialization) return initialization
    if (status.value !== 'idle') return

    status.value = 'restoring'
    initialization = (async () => {
      try {
        const user = await dataSource.getCurrentUser()
        const memberships = await dataSource.listMyTeams()
        applyAuthenticatedSession(user, memberships)
        await refreshModuleAccess()
      } catch (error) {
        clearAuthState(false)
        restoreError.value = isHumanSessionError(error)
          ? null
          : '暂时无法连接，请重试'
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

  async function selectTeam(teamId: string): Promise<void> {
    const team = activeTeams.value.find((item) => item.teamId === teamId)
    if (!team || !currentUser.value) return
    if (activeTeamId.value === teamId && currentModuleAccess.value !== null) {
      return
    }

    activeTeamId.value = teamId
    currentModuleAccess.value = null
    persistTeamId(currentUser.value.userId, teamId)
    authEffects.onTeamChanged()
    await refreshModuleAccess()
  }

  async function logout(): Promise<void> {
    await dataSource.logout()
    restoreError.value = null
    clearAuthState(true)
  }

  function expireSession(): void {
    restoreError.value = null
    if (status.value === 'anonymous') return
    clearAuthState(true)
  }

  function setDataSource(source: HumanAuthDataSource): void {
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
    activeTeams,
    currentTeam,
    requiresTeamSelection,
    allowedModuleCodes,
    initialize,
    login,
    selectTeam,
    logout,
    expireSession,
    setDataSource,
  }
})
