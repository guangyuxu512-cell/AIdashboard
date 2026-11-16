<script setup lang="ts">
import {
  Button as VanButton,
  Cell as VanCell,
  CellGroup as VanCellGroup,
  Field as VanField,
  Form as VanForm,
  Radio as VanRadio,
  RadioGroup as VanRadioGroup,
} from 'vant'
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { useAuthStore } from '@/app/stores/auth'
import {
  getLoginErrorMessage,
  resolvePostAuthRoute,
} from '@/features/human-auth'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const loginName = ref('')
const password = ref('')
const selectedTeamId = ref<string | null>(null)
const submitting = ref(false)
const serverError = ref<string | null>(null)

const selectingTeam = computed(
  () => auth.isAuthenticated && auth.requiresTeamSelection,
)

async function enterApplication(): Promise<void> {
  await router.replace(
    resolvePostAuthRoute(route.query.redirect, auth.allowedModuleCodes),
  )
}

async function submitLogin(): Promise<void> {
  if (!loginName.value.trim() || !password.value) return

  submitting.value = true
  serverError.value = null
  try {
    await auth.login({
      loginName: loginName.value.trim(),
      password: password.value,
    })
    password.value = ''
    if (!auth.requiresTeamSelection) await enterApplication()
  } catch (error) {
    password.value = ''
    serverError.value = getLoginErrorMessage(error)
  } finally {
    submitting.value = false
  }
}

async function confirmTeam(): Promise<void> {
  if (!selectedTeamId.value) return

  submitting.value = true
  serverError.value = null
  try {
    await auth.selectTeam(selectedTeamId.value)
    await enterApplication()
  } catch {
    serverError.value = '暂时无法进入，请重试'
  } finally {
    submitting.value = false
  }
}

async function logout(): Promise<void> {
  try {
    await auth.logout()
    selectedTeamId.value = null
  } catch {
    serverError.value = '退出失败，请重试'
  }
}
</script>

<template>
  <main class="mobile-login-page">
    <section class="mobile-login-card" aria-labelledby="mobile-login-title">
      <header class="mobile-login-card__header">
        <h1 id="mobile-login-title">思余AI中控台</h1>
        <p>{{ selectingTeam ? '选择当前团队' : '登录' }}</p>
      </header>

      <p
        v-if="serverError || auth.restoreError"
        class="mobile-login-card__error"
        role="alert"
      >
        {{ serverError || auth.restoreError }}
      </p>

      <template v-if="selectingTeam">
        <p
          v-if="auth.activeTeams.length === 0"
          class="mobile-login-card__empty"
        >
          当前账号没有可用团队
        </p>
        <VanForm v-else @submit="confirmTeam">
          <VanRadioGroup v-model="selectedTeamId">
            <VanCellGroup inset>
              <VanCell
                v-for="team in auth.activeTeams"
                :key="team.teamId"
                :title="team.teamName"
                clickable
                @click="selectedTeamId = team.teamId"
              >
                <template #right-icon>
                  <VanRadio :name="team.teamId" />
                </template>
              </VanCell>
            </VanCellGroup>
          </VanRadioGroup>
          <VanButton
            class="mobile-login-card__submit"
            block
            native-type="submit"
            type="primary"
            :disabled="!selectedTeamId"
            :loading="submitting"
          >
            进入中控台
          </VanButton>
        </VanForm>
        <VanButton
          class="mobile-login-card__secondary"
          block
          plain
          type="default"
          :disabled="submitting"
          @click="logout"
        >
          退出登录
        </VanButton>
      </template>

      <VanForm v-else @submit="submitLogin">
        <VanCellGroup inset>
          <VanField
            v-model="loginName"
            name="username"
            label="登录账号"
            autocomplete="username"
            :maxlength="100"
            placeholder="请输入登录账号"
            :rules="[{ required: true, message: '请输入登录账号' }]"
          />
          <VanField
            v-model="password"
            type="password"
            name="password"
            label="密码"
            autocomplete="current-password"
            :maxlength="256"
            placeholder="请输入密码"
            :rules="[{ required: true, message: '请输入密码' }]"
          />
        </VanCellGroup>
        <VanButton
          class="mobile-login-card__submit"
          block
          native-type="submit"
          type="primary"
          :loading="submitting"
        >
          登录
        </VanButton>
      </VanForm>
    </section>
  </main>
</template>

<style scoped>
.mobile-login-page {
  display: grid;
  width: 100%;
  min-width: 0;
  min-height: 100dvh;
  padding: max(var(--space-6), var(--safe-area-top))
    max(var(--layout-page-padding-x), var(--safe-area-right))
    max(var(--space-6), var(--safe-area-bottom))
    max(var(--layout-page-padding-x), var(--safe-area-left));
  overflow-x: hidden;
  overflow-y: auto;
  background: var(--visual-v2-page-background);
  place-items: center;
}

.mobile-login-card {
  width: min(100%, calc(var(--layout-content-max-width) - var(--space-8)));
  padding: var(--space-6) var(--space-4);
  color: var(--text-primary);
  background: var(--bg-surface-raised);
  border: var(--border-width) solid var(--border-subtle);
  border-radius: var(--radius-panel);
  box-shadow: var(--appearance-border-surface), var(--shadow-card);
}

.mobile-login-card__header {
  margin-bottom: var(--space-6);
  text-align: center;
}

.mobile-login-card__header h1 {
  font-size: var(--typography-v2-page-title-size);
  font-weight: var(--typography-v2-page-title-weight);
  line-height: var(--typography-v2-page-title-line-height);
}

.mobile-login-card__header p,
.mobile-login-card__empty {
  margin-top: var(--space-2);
  color: var(--text-secondary);
}

.mobile-login-card__error {
  margin-bottom: var(--space-3);
  color: var(--status-danger);
  font-size: var(--font-size-secondary);
  line-height: var(--line-height-secondary);
  text-align: center;
}

.mobile-login-card__empty {
  text-align: center;
}

.mobile-login-card :deep(.van-cell-group--inset) {
  margin: 0;
}

.mobile-login-card__submit,
.mobile-login-card__secondary {
  margin-top: var(--space-4);
}

@supports not (min-height: 100dvh) {
  .mobile-login-page {
    min-height: 100vh;
  }
}
</style>
