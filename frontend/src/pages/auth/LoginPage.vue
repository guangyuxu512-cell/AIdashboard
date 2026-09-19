<script setup lang="ts">
import { computed, ref } from 'vue'
import { NAlert, NForm, NFormItem } from 'naive-ui'
import { useForm } from 'vee-validate'
import { useRoute, useRouter } from 'vue-router'
import { z } from 'zod'

import brandMarkUrl from '@/assets/brand/siyu-ai-mark.png'
import { resolveSafeRedirect } from '@/features/human-auth/model/navigation'
import { getErrorMessage } from '@/shared/api'
import AppButton from '@/shared/ui/AppButton.vue'
import AppInput from '@/shared/ui/AppInput.vue'
import AppSelect from '@/shared/ui/AppSelect.vue'
import type { AppOptionValue } from '@/shared/ui/types'
import { useAuthStore } from '@/stores/auth'

interface LoginForm {
  loginName: string
  password: string
}

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const serverError = ref<string | null>(null)
const submitting = ref(false)
const selectedTeamId = ref<string | null>(null)

const loginSchema = z.object({
  loginName: z.string().trim().min(1, '请输入内部登录账号').max(100),
  password: z.string().min(1, '请输入密码').max(256),
})

const { defineField, errors, handleSubmit, setErrors } = useForm<LoginForm>({
  initialValues: { loginName: '', password: '' },
})
const [loginName] = defineField('loginName')
const [password] = defineField('password')

const selectingTeam = computed(
  () => auth.isAuthenticated && auth.requiresTeamSelection,
)
const teamOptions = computed(() =>
  auth.activeTeams.map((item) => ({
    label: item.teamName,
    value: item.teamId,
  })),
)
const targetRoute = computed(() => resolveSafeRedirect(route.query.redirect))

const submitLogin = handleSubmit(async (values) => {
  const parsed = loginSchema.safeParse(values)
  if (!parsed.success) {
    const fieldErrors = parsed.error.flatten().fieldErrors
    setErrors({
      loginName: fieldErrors.loginName?.[0],
      password: fieldErrors.password?.[0],
    })
    return
  }
  submitting.value = true
  serverError.value = null
  try {
    await auth.login(parsed.data)
    if (!auth.requiresTeamSelection) await router.replace(targetRoute.value)
  } catch (error) {
    serverError.value = getErrorMessage(error)
  } finally {
    submitting.value = false
  }
})

function updateSelectedTeam(value: AppOptionValue | null): void {
  selectedTeamId.value = typeof value === 'string' ? value : null
}

async function confirmTeam(): Promise<void> {
  if (!selectedTeamId.value) return
  auth.selectTeam(selectedTeamId.value)
  await router.replace(targetRoute.value)
}
</script>

<template>
  <main class="login-page">
    <section class="login-card" aria-labelledby="login-title">
      <header class="login-card__brand">
        <img :src="brandMarkUrl" alt="" aria-hidden="true" />
        <div>
          <h1 id="login-title">思余AI中控台</h1>
          <p>企业内部人员登录</p>
        </div>
      </header>

      <template v-if="selectingTeam">
        <div class="login-card__section-heading">
          <strong>选择当前团队</strong>
          <span>{{ auth.currentUser?.displayName }}</span>
        </div>
        <NAlert
          v-if="teamOptions.length === 0"
          type="warning"
          :show-icon="false"
        >
          当前账号未分配团队，请联系超级账号管理员。
        </NAlert>
        <NForm v-else label-placement="top" @submit.prevent="confirmTeam">
          <NFormItem label="当前团队">
            <AppSelect
              :model-value="selectedTeamId"
              :options="teamOptions"
              placeholder="请选择团队"
              @update:model-value="updateSelectedTeam"
            />
          </NFormItem>
          <AppButton
            tone="primary"
            block
            attr-type="submit"
            :disabled="!selectedTeamId"
          >
            进入中控台
          </AppButton>
        </NForm>
      </template>

      <NForm v-else label-placement="top" @submit.prevent="submitLogin">
        <NAlert
          v-if="serverError || auth.restoreError"
          class="login-card__error"
          type="error"
          :show-icon="false"
        >
          {{ serverError || auth.restoreError }}
        </NAlert>
        <NFormItem
          label="内部登录账号"
          :validation-status="errors.loginName ? 'error' : undefined"
          :feedback="errors.loginName"
        >
          <AppInput
            v-model="loginName"
            name="username"
            aria-label="内部登录账号"
            autocomplete="username"
            autofocus
            :maxlength="100"
            placeholder="请输入登录账号"
          />
        </NFormItem>
        <NFormItem
          label="密码"
          :validation-status="errors.password ? 'error' : undefined"
          :feedback="errors.password"
        >
          <AppInput
            v-model="password"
            type="password"
            name="password"
            aria-label="密码"
            autocomplete="current-password"
            :maxlength="256"
            placeholder="请输入密码"
          />
        </NFormItem>
        <AppButton
          tone="primary"
          block
          attr-type="submit"
          :loading="submitting"
        >
          登录
        </AppButton>
      </NForm>
    </section>
  </main>
</template>

<style scoped>
.login-page {
  display: grid;
  width: 100%;
  height: 100%;
  min-height: 0;
  place-items: center;
  padding: var(--space-6);
  background: var(--bg-app);
}

.login-card {
  width: min(100%, var(--dialog-width-sm));
  padding: var(--space-6);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-dialog);
  background: var(--bg-surface-solid);
  box-shadow: var(--shadow-card);
}

.login-card__brand {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  margin-bottom: var(--space-6);
}

.login-card__brand img {
  width: 48px;
  height: 40px;
  object-fit: contain;
}

.login-card__brand h1,
.login-card__brand p {
  margin: 0;
}

.login-card__brand h1 {
  color: var(--text-primary);
  font-size: var(--font-size-page-title);
  line-height: var(--line-height-compact);
}

.login-card__brand p,
.login-card__section-heading span {
  color: var(--text-tertiary);
  font-size: var(--font-size-secondary);
}

.login-card__section-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--space-4);
  color: var(--text-primary);
}

.login-card__error {
  margin-bottom: var(--space-4);
}
</style>
