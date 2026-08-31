import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import {
  humanAuthDataSource,
  type CurrentHumanUser,
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
}

const authEffects: AuthEffects = {
  onTeamChanged: () => undefined,
  onAuthCleared: () => undefined,
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
  const restoreError = ref<string | null>(null)
  let initialization: Promise<void> | null = null
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
  const requiresTeamSelection = computed(
    () => isAuthenticated.value && currentTeam.value === null,
  )

  function applyAuthenticatedSession(
    user: CurrentHumanUser,
    memberships: HumanTeamMembership[],
  ): void {
    currentUser.value = user
    teams.value = memberships
    const available = memberships.filter(
      (item) => item.teamEnabled && item.membershipEnabled,
    )
    const storedTeamId = readStoredTeamId(user.userId)
    activeTeamId.value =
      available.find((item) => item.teamId === storedTeamId)?.teamId ??
      (available.length === 1 ? (available[0]?.teamId ?? null) : null)
    if (activeTeamId.value) persistTeamId(user.userId, activeTeamId.value)
    restoreError.value = null
    status.value = 'authenticated'
  }

  function clearAuthState(clearPersistedTeam = false): void {
    if (clearPersistedTeam && currentUser.value) {
      removeStoredTeamId(currentUser.value.userId)
    }
    currentUser.value = null
    teams.value = []
    activeTeamId.value = null
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
      } catch (error) {
        currentUser.value = null
        teams.value = []
        activeTeamId.value = null
        status.value = 'anonymous'
        restoreError.value = isHumanSessionError(error)
          ? null
          : getErrorMessage(error)
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
  }

  async function logout(): Promise<void> {
    await dataSource.logout()
    restoreError.value = null
    clearAuthState(true)
  }

  function selectTeam(teamId: string): void {
    const membership = activeTeams.value.find((item) => item.teamId === teamId)
    if (!membership || !currentUser.value) return
    if (activeTeamId.value === teamId) return
    activeTeamId.value = teamId
    persistTeamId(currentUser.value.userId, teamId)
    authEffects.onTeamChanged()
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
    restoreError,
    isAuthenticated,
    activeTeams,
    currentTeam,
    requiresTeamSelection,
    initialize,
    login,
    logout,
    selectTeam,
    expireSession,
    setDataSource,
  }
})
