<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { NAlert, NCheckbox, NCheckboxGroup, NEmpty, NSpin } from 'naive-ui'

import {
  useAccessTeamAuthorizationQuery,
  type AccessTeamAuthorizationInput,
  type AccessTeamViewModel,
} from '@/entities/access-management'
import { getModuleAccessOptions } from '@/app/modules/registry'
import { useDeviceListQuery, type DeviceListFilters } from '@/entities/device'
import { useShopListQuery, type ShopListFilters } from '@/entities/shop'
import FormDialog from '@/shared/components/FormDialog.vue'

const props = defineProps<{
  show: boolean
  team: AccessTeamViewModel | null
  submitting?: boolean
}>()

const emit = defineEmits<{
  'update:show': [value: boolean]
  save: [input: AccessTeamAuthorizationInput]
}>()

function emptyDeviceFilters(): DeviceListFilters {
  return {
    status: null,
    tag: null,
    workerVersion: null,
    capability: null,
    keyword: '',
  }
}

function emptyShopFilters(): ShopListFilters {
  return { enabledStatus: null, ownerUserId: null, keyword: '' }
}

const teamId = computed(() => (props.show ? props.team?.teamId ?? null : null))
const authorizationQuery = useAccessTeamAuthorizationQuery(teamId)
const deviceQuery = useDeviceListQuery(
  computed(() => ({
    page: 1,
    pageSize: 100,
    filters: emptyDeviceFilters(),
  })),
  computed(() => props.show),
)
const shopQuery = useShopListQuery(
  computed(() => ({
    page: 1,
    pageSize: 100,
    filters: emptyShopFilters(),
    referenceOptions: { includeDevices: false, includeOwners: false },
  })),
  computed(() => props.show),
)

const moduleCodes = ref<string[]>([])
const deviceIds = ref<string[]>([])
const shopIds = ref<string[]>([])
const initializedForTeam = ref<string | null>(null)
const moduleOptions = getModuleAccessOptions()

watch(
  () => [teamId.value, authorizationQuery.data.value] as const,
  ([id, authorization]) => {
    if (!id || !authorization || initializedForTeam.value === id) return
    moduleCodes.value = [...authorization.moduleCodes]
    deviceIds.value = [...authorization.deviceIds]
    shopIds.value = [...authorization.shopIds]
    initializedForTeam.value = id
  },
  { immediate: true },
)

watch(
  () => props.show,
  (show) => {
    if (!show) initializedForTeam.value = null
  },
)

const deviceRows = computed(() =>
  (deviceQuery.data.value?.items ?? []).filter((device) => device.enabled),
)
const shopRows = computed(() =>
  (shopQuery.data.value?.items ?? []).filter((shop) => shop.enabled),
)

function submit(): void {
  emit('save', {
    moduleCodes: [...moduleCodes.value],
    deviceIds: [...deviceIds.value],
    shopIds: [...shopIds.value],
  })
}
</script>

<template>
  <FormDialog
    :show="show"
    :title="`团队授权${team ? ` · ${team.name}` : ''}`"
    size="lg"
    :submitting="submitting"
    :submit-disabled="authorizationQuery.isPending.value"
    submit-text="保存授权"
    @update:show="$emit('update:show', $event)"
    @submit="submit"
    @cancel="$emit('update:show', false)"
  >
    <NAlert type="info" :bordered="false">
      团队成员继承以下授权。设备和店铺仍需通过现有店铺—设备绑定及应用能力校验，保存后后续请求立即按新授权执行。
    </NAlert>
    <NSpin :show="authorizationQuery.isPending.value" class="access-team-authorization">
      <section class="access-team-authorization__section">
        <h3>可用模块</h3>
        <NCheckboxGroup v-model:value="moduleCodes">
          <div class="access-team-authorization__grid">
            <NCheckbox
              v-for="module in moduleOptions"
              :key="module.value"
              :value="module.value"
            >
              {{ module.label }}
            </NCheckbox>
          </div>
        </NCheckboxGroup>
      </section>

      <section class="access-team-authorization__section">
        <h3>可用设备</h3>
        <NEmpty
          v-if="!deviceQuery.isPending.value && !deviceRows.length"
          size="small"
          description="暂无可授权设备"
        />
        <NCheckboxGroup v-else v-model:value="deviceIds">
          <div class="access-team-authorization__resource-list">
            <NCheckbox
              v-for="device in deviceRows"
              :key="device.deviceId"
              :value="device.deviceId"
            >
              {{ device.deviceName }}
            </NCheckbox>
          </div>
        </NCheckboxGroup>
      </section>

      <section class="access-team-authorization__section">
        <h3>可访问店铺</h3>
        <NEmpty
          v-if="!shopQuery.isPending.value && !shopRows.length"
          size="small"
          description="暂无可授权店铺"
        />
        <NCheckboxGroup v-else v-model:value="shopIds">
          <div class="access-team-authorization__resource-list">
            <NCheckbox
              v-for="shop in shopRows"
              :key="shop.shopId"
              :value="shop.shopId"
            >
              {{ shop.shopName }}
            </NCheckbox>
          </div>
        </NCheckboxGroup>
      </section>
    </NSpin>
  </FormDialog>
</template>

<style scoped>
.access-team-authorization {
  display: block;
  margin-top: var(--space-4);
}

.access-team-authorization__section + .access-team-authorization__section {
  margin-top: var(--space-5);
}

.access-team-authorization__section h3 {
  margin: 0 0 var(--space-3);
  font-size: var(--font-size-section-title);
  font-weight: var(--font-weight-semibold);
}

.access-team-authorization__grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: var(--space-3);
}

.access-team-authorization__resource-list {
  display: grid;
  max-height: 180px;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--space-3);
  overflow: auto;
  padding: var(--space-3);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-control);
}

@media (max-width: 640px) {
  .access-team-authorization__grid,
  .access-team-authorization__resource-list {
    grid-template-columns: 1fr;
  }
}
</style>
