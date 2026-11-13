<script setup lang="ts">
import { computed, h, onMounted, reactive, ref, watch } from 'vue'
import {
  NAlert, NButton, NCard, NCheckbox, NCheckboxGroup, NCollapse, NCollapseItem,
  NDataTable, NDatePicker, NEmpty, NFormItem, NInput, NModal, NPopconfirm,
  NSelect, NSpace, NSpin, NTag, useMessage,
  type DataTableColumns,
} from 'naive-ui'

import { getErrorMessage, httpClient } from '@/shared/api/http-client'

type Permission = { id: string; module: string; name: string; team_scoped: boolean }
type Team = { team_id: string; team_name: string }
type Token = {
  token_id: string; name: string; permissions: string[]; team_ids: string[] | null
  enabled: boolean; expires_at: string | null; revoked_at: string | null
  created_at: string; updated_at: string
}
type TokenEvent = { event_id: string; actor_user_id: string; action: string; created_at: string }

const labels: Record<string, string> = {
  access: '当前身份', 'human-auth': '登录身份', 'access-management': '用户与团队', 'ai-workbench': 'AI 工作台',
  'ai-model-management': 'AI 模型', 'shop-onboarding': '店铺接入', assets: '素材',
  'automation-app-configs': '自动化应用', 'automation-parameter-presets': '自动化参数',
  users: '用户', shops: '店铺', devices: '设备', 'notification-channels': '通知',
  'operating-dashboard': '经营看板', 'product-selection': '选品',
  'product-collection': '商品采集', 'product-data': '商品数据', credentials: '店铺凭证',
  sessions: '店铺会话', tasks: '任务', schedules: '定时计划',
}
const names: Record<string, string> = {
  'Get Current Actor': '查看当前身份', 'Get Current Human User': '查看登录身份', 'List My Teams': '查看可用团队',
  'List Devices': '查看设备列表', 'Get Device': '查看设备详情', 'Create Device': '创建设备',
  'Update Device': '修改设备', 'Remove Device': '移除设备',
  'Get Device Business Skills': '查看设备业务技能', 'Get Device Provider Inventories': '查看设备运行环境',
  'Get Device Skill Capabilities': '查看设备能力', 'Get Worker Credential': '查看 Worker 凭据状态',
  'Issue Worker Credential': '签发 Worker 凭据', 'Rotate Worker Credential': '轮换 Worker 凭据',
  'Revoke Worker Credential': '撤销 Worker 凭据', 'List Tasks': '查看任务列表',
  'Get Task': '查看任务详情', 'Get Active Task': '查看设备当前任务',
  'List Task Events': '查看任务进度', 'Create Task': '创建任务',
  'Purge Expired Task Events': '清理过期任务记录', 'List Schedules': '查看定时计划',
  'Get Schedule': '查看定时计划详情', 'List Schedule Runs': '查看定时执行记录',
  'Create Schedule': '创建定时计划', 'Update Schedule': '修改定时计划',
  'Delete Schedule': '删除定时计划', 'List Shops': '查看店铺列表', 'Get Shop': '查看店铺详情',
  'Create Shop': '添加店铺', 'Update Shop': '修改店铺', 'Remove Shop': '移除店铺',
  'Get Shop Session Metadata': '查看店铺会话状态', 'Validate Shop Session': '验证店铺会话',
  'List Product Library Groups': '查看商品库分组', 'List Product Library Products': '查看商品库列表',
  'Read Product Library Product': '查看商品详情', 'List Product Collection Requests': '查看采集任务',
  'Read Product Collection Request': '查看采集任务详情', 'Read Operating Dashboard': '查看经营看板',
  'Delete Team': '删除团队', 'List Audit Logs': '查看操作日志', 'Get Current Module Access': '查看当前模块权限',
  'List Members': '查看成员列表', 'Get Member': '查看成员详情', 'List Teams': '查看团队列表',
  'Get Team Authorization': '查看团队授权', 'Update Member': '修改成员', 'Update Membership': '修改成员关系',
  'Update Team': '修改团队', 'Create Member': '创建成员', 'Create Membership': '添加成员关系',
  'Reset Member Password': '重置成员密码', 'Create Team': '创建团队', 'Archive Team': '归档团队',
  'Move Member To Team': '调整成员团队', 'Update Team Authorization': '修改团队授权',
  'List Ai Models': '查看 AI 模型列表', 'Get Ai Model': '查看 AI 模型详情', 'Update Ai Model': '修改 AI 模型',
  'Create Ai Model': '新增 AI 模型', 'Set Default Ai Model': '设置默认 AI 模型',
  'Cleanup Ai Asset': '删除 AI 素材', 'Delete Product Material Group': '删除商品素材组', 'Detach Asset': '移出组内素材',
  'Delete Template Group': '删除模板组', 'Delete Prompt Template': '删除提示词模板',
  'Read Ai Asset Content': '读取 AI 素材', 'Read Ai Asset Thumbnail': '查看 AI 素材缩略图',
  'List Generation Jobs': '查看生成任务', 'Get Generation Job': '查看生成任务详情',
  'List Available Ai Models': '查看可用 AI 模型', 'List Product Material Groups': '查看商品素材组',
  'Get Product Material Group': '查看商品素材组详情', 'List Template Groups': '查看模板组',
  'Get Template Group': '查看模板组详情', 'Update Product Material Group': '修改商品素材组',
  'Update Template Group': '修改模板组', 'Update Prompt Template': '修改提示词模板',
  'Upload Ai Asset': '上传 AI 素材', 'Submit Generation': '提交生成任务',
  'Archive Instant Generation Item': '归档生成结果', 'Retry Failed Generation Items': '重试失败的生成任务',
  'Create Product Material Group': '创建商品素材组', 'Attach Asset': '添加组内素材',
  'Create Template Group': '创建模板组', 'Create Prompt Template': '创建提示词模板',
  'Duplicate Prompt Template': '复制提示词模板', 'Replace Template Bindings': '更新模板绑定',
  'Reorder Prompt Templates': '调整提示词模板顺序', 'Delete Asset': '删除素材',
  'List Assets': '查看素材列表', 'Read Asset Content': '读取素材内容', 'Read Asset Thumbnail': '读取素材缩略图',
  'Upload Asset': '上传素材', 'List Yingdao Applications': '查看影刀应用', 'Get Config': '查看应用配置',
  'Upsert Config': '保存应用配置', 'Delete Preset': '删除参数预设', 'List Presets': '查看应用参数预设',
  'Get Preset': '查看参数预设详情', 'List All Presets': '查看全部参数预设', 'Update Preset': '修改参数预设',
  'Create Preset': '创建参数预设', 'Copy Preset': '复制参数预设',
  'Get Shop Credential Status': '查看店铺账号状态', 'Update Credential': '修改店铺账号凭证',
  'Create Credential': '添加店铺账号凭证', 'Disable Credential': '停用店铺账号凭证',
  'List Notification Channels': '查看通知渠道', 'Update Notification Channel': '修改通知渠道',
  'Create Notification Channel': '添加通知渠道', 'Test Notification Channel': '测试通知渠道',
  'Get Operating Collection': '查看经营数据采集', 'Enqueue Operating Collection': '更新经营数据',
  'Recollect Operating Collection': '重新采集经营数据', 'Retry Operating Collection': '重试经营数据采集',
  'Recapture Product Collection Item': '重新采集商品', 'Retry Product Collection Item': '重试商品采集',
  'Create Product Collection Request': '创建商品采集任务', 'Cancel Product Collection Request': '取消商品采集任务',
  'List Product Data': '查看商品数据', 'Read Product Data Collection Batch': '查看商品数据批次',
  'List Product Data Collection Shops': '查看商品数据采集店铺', 'Read Product Data Collection': '查看商品数据采集',
  'Collect Product Data Batch': '批量采集商品数据', 'Collect Product Data': '采集商品数据',
  'Read Basic Info': '查看商品基础信息', 'Read Selection Candidates': '查看选品候选',
  'Read Selection Capabilities': '查看选品能力', 'Read Selection Categories': '查看选品类目',
  'Read Selection Observation': '查看选品观察详情', 'Read Latest Basic Info': '查看最新基础信息',
  'Read Selection Runs': '查看选品执行列表', 'Read Selection Run': '查看选品执行详情',
  'List Selection Strategies': '查看选品策略', 'Read Selection Strategy': '查看选品策略详情',
  'Read Strategy Batches': '查看策略批次', 'Set Candidate Blocked': '设置候选商品屏蔽状态',
  'Toggle Selection Strategy': '启停选品策略', 'Submit Basic Info': '更新商品基础信息',
  'Submit Selection Run': '执行选品', 'Create Selection Strategy': '创建选品策略',
  'Update Selection Strategy': '修改选品策略', 'Release Shop Session Refresh Lease': '释放店铺会话更新租约',
  'Complete Shop Session Refresh': '保存店铺会话', 'Acquire Shop Session Refresh Lease': '获取店铺会话更新租约',
  'Complete Management Onboarding': '完成店铺接入', 'Verify Pdd Management Login Identity': '验证拼多多登录身份',
  'List Shop Device Bindings': '查看店铺设备绑定', 'Get Platform Shop Identity': '查看平台店铺身份',
  'Update Shop Device Binding': '修改店铺设备绑定', 'Create Shop Device Binding': '创建设备绑定',
  'List Users': '查看用户列表', 'Get User': '查看用户详情', 'Update User': '修改用户', 'Create User': '创建用户',
}
function permissionName(permission: Permission): string {
  return names[permission.name] ?? permission.name
}
const message = useMessage()
const checking = ref(true)
const loggedIn = ref(false)
const loading = ref(false)
const loginName = ref('')
const password = ref('')
const tokens = ref<Token[]>([])
const permissions = ref<Permission[]>([])
const teams = ref<Team[]>([])
const showEdit = ref(false)
const showIssued = ref(false)
const showHistory = ref(false)
const historyName = ref('')
const history = ref<TokenEvent[]>([])
const issuedValue = ref('')
const editingId = ref<string | null>(null)
const saving = ref(false)
const form = reactive({ name: '', permissions: [] as string[], teamIds: [] as string[], expiresAt: null as number | null, enabled: true })
const baseUrl = window.location.origin
const teamOptions = computed(() => teams.value.map((team) => ({ label: team.team_name, value: team.team_id })))
const groups = computed(() => {
  const result = new Map<string, Permission[]>()
  for (const permission of permissions.value) {
    const current = result.get(permission.module) ?? []
    current.push(permission)
    result.set(permission.module, current)
  }
  return Array.from(result, ([key, entries]) => ({ key, label: labels[key] ?? key, entries }))
})

watch(() => form.teamIds.slice(), (selected) => {
  if (selected.length) {
    const allowed = new Set(permissions.value.filter((item) => item.team_scoped).map((item) => item.id))
    form.permissions = form.permissions.filter((id) => allowed.has(id))
  }
})
watch(showIssued, (open) => { if (!open) issuedValue.value = '' })

function stateOf(token: Token): string {
  if (token.revoked_at) return '已撤销'
  if (!token.enabled) return '已停用'
  if (token.expires_at && Date.parse(token.expires_at) <= Date.now()) return '已过期'
  return '有效'
}
function showTime(value: string | null): string {
  return value ? new Date(value).toLocaleString('zh-CN', { hour12: false }) : '不过期'
}
function edit(token?: Token) {
  editingId.value = token?.token_id ?? null
  form.name = token?.name ?? ''
  form.teamIds = token?.team_ids?.slice() ?? []
  form.permissions = token?.permissions.slice() ?? []
  form.expiresAt = token?.expires_at ? Date.parse(token.expires_at) : null
  form.enabled = token?.enabled ?? true
  showEdit.value = true
}
function selectPermissions(readOnly: boolean) {
  form.permissions = permissions.value
    .filter((entry) => (!form.teamIds.length || entry.team_scoped) && (!readOnly || entry.id.startsWith('GET ')))
    .map((entry) => entry.id)
}
function selectGroup(entries: Permission[]) {
  const selected = new Set(form.permissions)
  for (const entry of entries) {
    if (!form.teamIds.length || entry.team_scoped) selected.add(entry.id)
  }
  form.permissions = Array.from(selected)
}
function payload() {
  return { name: form.name.trim(), permissions: form.permissions, team_ids: form.teamIds.length ? form.teamIds : null,
    enabled: form.enabled, expires_at: form.expiresAt === null ? null : new Date(form.expiresAt).toISOString() }
}
async function load() {
  loading.value = true
  try {
    const [tokenResponse, permissionResponse, teamResponse] = await Promise.all([
      httpClient.get<Token[]>('/api/v1/api-tokens'),
      httpClient.get<Permission[]>('/api/v1/api-tokens/permissions'),
      httpClient.get<Team[]>('/api/v1/access/me/teams'),
    ])
    tokens.value = tokenResponse.data
    permissions.value = permissionResponse.data
    teams.value = teamResponse.data
  } catch (error) {
    message.error(getErrorMessage(error))
  } finally { loading.value = false }
}
async function login() {
  loading.value = true
  try {
    await httpClient.post('/api/v1/auth/login', { login_name: loginName.value, password: password.value })
    password.value = ''
    loggedIn.value = true
    await load()
  } catch (error) { message.error(getErrorMessage(error)) }
  finally { loading.value = false }
}
async function save() {
  if (!form.name.trim() || !form.permissions.length) { message.warning('请填写名称并选择至少一项权限'); return }
  saving.value = true
  try {
    if (editingId.value) {
      await httpClient.put(`/api/v1/api-tokens/${editingId.value}`, payload())
      message.success('已保存')
    } else {
      const result = await httpClient.post<{ value: string }>('/api/v1/api-tokens', payload())
      issuedValue.value = result.data.value
      showIssued.value = true
    }
    showEdit.value = false
    await load()
  } catch (error) { message.error(getErrorMessage(error)) }
  finally { saving.value = false }
}
async function toggle(token: Token) {
  try {
    await httpClient.patch(`/api/v1/api-tokens/${token.token_id}/enabled`, { enabled: !token.enabled })
    message.success(token.enabled ? '已停用' : '已启用')
    await load()
  } catch (error) { message.error(getErrorMessage(error)) }
}
async function revoke(token: Token) {
  try {
    await httpClient.delete(`/api/v1/api-tokens/${token.token_id}`)
    message.success('已撤销')
    await load()
  } catch (error) { message.error(getErrorMessage(error)) }
}
async function showEvents(token: Token) {
  try {
    const result = await httpClient.get<TokenEvent[]>(`/api/v1/api-tokens/${token.token_id}/events`)
    history.value = result.data
    historyName.value = token.name
    showHistory.value = true
  } catch (error) { message.error(getErrorMessage(error)) }
}
async function copy(value: string) {
  try { await navigator.clipboard.writeText(value); message.success('已复制') }
  catch { message.error('复制失败，请手动选择并复制') }
}

const columns: DataTableColumns<Token> = [
  { title: '名称', key: 'name', minWidth: 140 },
  { title: '状态', key: 'status', width: 96, render: (row) => h(NTag, { type: stateOf(row) === '有效' ? 'success' : 'default', size: 'small' }, { default: () => stateOf(row) }) },
  { title: '权限', key: 'permissions', width: 95, render: (row) => `${row.permissions.length} 项` },
  { title: '团队', key: 'team_ids', minWidth: 110, render: (row) => row.team_ids ? `${row.team_ids.length} 个团队` : '全部团队' },
  { title: '有效期', key: 'expires_at', minWidth: 160, render: (row) => showTime(row.expires_at) },
  { title: '操作', key: 'actions', minWidth: 270, render: (row) => h(NSpace, { size: 'small' }, { default: () => [
    h(NButton, { size: 'small', onClick: () => showEvents(row) }, { default: () => '记录' }),
    ...(row.revoked_at ? [] : [
    h(NButton, { size: 'small', onClick: () => edit(row) }, { default: () => '配置' }),
    h(NButton, { size: 'small', onClick: () => toggle(row) }, { default: () => row.enabled ? '停用' : '启用' }),
    h(NPopconfirm, { onPositiveClick: () => revoke(row) }, { default: () => '撤销后无法恢复，确定撤销？', trigger: () => h(NButton, { size: 'small', type: 'error', tertiary: true }, { default: () => '撤销' }) }),
    ]),
  ] }) },
]
const eventActionLabels: Record<string, string> = { create: '创建', update: '更新', revoke: '撤销' }
const eventColumns: DataTableColumns<TokenEvent> = [
  { title: '时间', key: 'created_at', minWidth: 160, render: (row) => showTime(row.created_at) },
  { title: '操作', key: 'action', width: 100, render: (row) => eventActionLabels[row.action] ?? row.action },
  { title: '操作人 ID', key: 'actor_user_id', minWidth: 240 },
]

onMounted(async () => {
  try { await httpClient.get('/api/v1/auth/me'); loggedIn.value = true; await load() }
  catch { loggedIn.value = false }
  finally { checking.value = false }
})
</script>

<template>
  <main class="token-manager">
    <header class="header"><div><h1>中控 Token 管理</h1><p>为 AI 配置独立的接口权限</p></div></header>
    <NSpin :show="checking">
      <NCard v-if="!loggedIn" title="管理员登录" class="login-card">
        <NFormItem label="账号"><NInput v-model:value="loginName" autocomplete="username" /></NFormItem>
        <NFormItem label="密码"><NInput v-model:value="password" type="password" show-password-on="click" autocomplete="current-password" @keyup.enter="login" /></NFormItem>
        <NButton type="primary" :loading="loading" @click="login">登录</NButton>
      </NCard>
      <template v-else>
        <NCard title="API 地址" class="section">
          <NSpace align="center"><code>{{ baseUrl }}</code><NButton size="small" @click="copy(baseUrl)">复制地址</NButton><NButton size="small" @click="copy(`${baseUrl}/openapi.json`)">复制接口文档地址</NButton></NSpace>
        </NCard>
        <NCard title="Token" class="section">
          <template #header-extra><NSpace><NButton :disabled="loading" @click="load">刷新</NButton><NButton type="primary" :disabled="loading" @click="edit()">新建 Token</NButton></NSpace></template>
          <NDataTable v-if="tokens.length" :columns="columns" :data="tokens" :loading="loading" :scroll-x="850" :row-key="(row: Token) => row.token_id" />
          <NEmpty v-else description="暂无 Token" />
        </NCard>
      </template>
    </NSpin>
    <NModal v-model:show="showEdit" preset="card" :title="editingId ? '配置 Token' : '新建 Token'" class="edit-dialog">
      <NFormItem label="名称"><NInput v-model:value="form.name" placeholder="例如：AI 助手" maxlength="100" /></NFormItem>
      <NFormItem label="团队范围"><NSelect v-model:value="form.teamIds" :options="teamOptions" multiple clearable placeholder="不选择表示全部团队" /></NFormItem>
      <NAlert v-if="form.teamIds.length" type="info" :bordered="false">
        限定团队时，只能选择支持团队隔离的接口。调用时请在 X-Team-ID 请求头填写对应团队 ID。
        <NSpace v-for="team in teams.filter((item) => form.teamIds.includes(item.team_id))" :key="team.team_id" align="center">
          <span>{{ team.team_name }}：{{ team.team_id }}</span><NButton size="tiny" @click="copy(team.team_id)">复制</NButton>
        </NSpace>
      </NAlert>
      <NFormItem label="有效期"><NDatePicker v-model:value="form.expiresAt" type="datetime" clearable placeholder="不设置表示不过期" /></NFormItem>
      <div class="permission-heading"><strong>接口权限</strong><NSpace><NButton size="small" @click="selectPermissions(true)">全选读取</NButton><NButton size="small" @click="selectPermissions(false)">全选</NButton><NButton size="small" @click="form.permissions = []">清空</NButton></NSpace></div>
      <NCheckboxGroup v-model:value="form.permissions">
        <NCollapse>
          <NCollapseItem v-for="group in groups" :key="group.key" :name="group.key" :title="`${group.label}（${group.entries.length}）`">
            <template #header-extra><NButton size="tiny" @click.stop="selectGroup(group.entries)">全选本组</NButton></template>
            <div class="permission-list"><NCheckbox v-for="permission in group.entries" :key="permission.id" :value="permission.id" :disabled="form.teamIds.length > 0 && !permission.team_scoped"><span>{{ permissionName(permission) }}</span><small>{{ permission.id }}</small></NCheckbox></div>
          </NCollapseItem>
        </NCollapse>
      </NCheckboxGroup>
      <template #footer><NSpace justify="end"><NButton @click="showEdit = false">取消</NButton><NButton type="primary" :loading="saving" @click="save">保存</NButton></NSpace></template>
    </NModal>
    <NModal v-model:show="showIssued" preset="card" title="Token 已创建" class="issued-dialog" :mask-closable="false">
      <NAlert type="warning">完整 Token 只显示这一次，请立即复制并保存。</NAlert>
      <NInput :value="issuedValue" readonly type="textarea" :autosize="{ minRows: 3 }" class="issued-value" />
      <template #footer><NSpace justify="end"><NButton @click="copy(issuedValue)">复制 Token</NButton><NButton type="primary" @click="showIssued = false">已保存</NButton></NSpace></template>
    </NModal>
    <NModal v-model:show="showHistory" preset="card" :title="`${historyName} · 操作记录`" class="edit-dialog">
      <NDataTable :columns="eventColumns" :data="history" :scroll-x="500" :row-key="(row: TokenEvent) => row.event_id" />
    </NModal>
  </main>
</template>

<style scoped>
.token-manager { max-width: 1180px; padding: var(--space-6); margin: 0 auto; }
.header { margin-bottom: var(--space-6); }
.header h1 { margin: 0; font-size: 24px; }
.header p { margin: var(--space-2) 0 0; color: var(--text-secondary); }
.login-card { max-width: 440px; margin: var(--space-8) auto; }
.section { margin-bottom: var(--space-4); }
.edit-dialog { width: min(880px, calc(100vw - 32px)); max-height: calc(100vh - 32px); display: flex; flex-direction: column; }
.edit-dialog :deep(.n-card__content) { overflow-y: auto; min-height: 0; }
.issued-dialog { width: min(560px, calc(100vw - 32px)); }
.issued-value { margin-top: var(--space-4); }
.permission-heading { display: flex; justify-content: space-between; align-items: center; gap: var(--space-2); margin: var(--space-4) 0; }
.permission-list { display: grid; gap: var(--space-3); }
.permission-list small { display: block; color: var(--text-secondary); word-break: break-all; }
</style>
