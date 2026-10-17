# API 与数据契约

Pydantic Schema / OpenAPI 为权威来源。

原则：

- 请求/响应字段明确。
- 枚举明确。
- 错误码明确。
- 不向前端泄露数据库内部模型。
- 不把 ORM 对象直接作为长期 Contract。

统一分页、时间和错误结构。
破坏性 Contract 变化必须明确处理兼容或版本升级。

## 工程健康检查

`GET /health` 是不依赖数据库的工程级健康检查，不属于业务 API。
生产 Host Nginx 必须将精确 `/health` 转发到 Backend，不能落入 Frontend SPA fallback。

成功响应：

```json
{
  "status": "ok"
}
```

## Core Domain V1 Contract

统一前缀为 `/api/v1`：

- `/users`：GET list、GET detail、POST create、PATCH update。
- `/shops`：GET list、GET detail、POST create、PATCH update、DELETE soft remove。
- `/devices`：GET list、GET detail、POST create、PATCH update。
- `/shops/{shop_id}/device-bindings`：GET list、POST create。
- `/shops/{shop_id}/device-bindings/{device_id}`：PATCH update/disable。

列表统一返回：

```json
{
  "items": [],
  "total": 0,
  "page": 1,
  "page_size": 20
}
```

错误统一返回 `code`、`message`、`request_id`、可选 `details`。V1 业务错误码包含 `USER_NOT_FOUND`、`SHOP_NOT_FOUND`、`DEVICE_NOT_FOUND`、`INVALID_DEVICE_BINDING`、`IMMUTABLE_SHOP_IDENTITY`；请求校验使用 `VALIDATION_ERROR`，数据库异常统一映射为 `DATABASE_OPERATION_FAILED`。

## Access Foundation V1 Contract

> **0037 覆盖说明：** 本节的多有效 Team / 成员级 Scope 只解释旧 Contract。自
> `20260919_0037_super_account_team_authorization_v1` 起，当前身份与授权契约以
> [23-超级账号与团队授权V1.md](23-超级账号与团队授权V1.md) 为准：超级账号无 Membership，
> 普通成员至多一个有效 Team，`X-Team-ID` 对超级账号是显式写入上下文而不是默认团队。

- `GET /api/v1/access/me`：返回当前请求解析后的 ActorContext。
- `GET /api/v1/access/me/teams`：返回当前 Human User 的 Team/Membership 摘要，供未来 Team
  Switcher 使用；该接口不要求先选定 Active Team。
- `X-Team-ID`：用户有多个 Active Membership 时的 Team Context Header。Header 只是选择请求，
  Backend 必须验证当前 User 拥有对应启用 Membership 且 Team 启用。

Actor DTO 只包含 `user_id / user_display_name / team_id / membership_id / role_code /
data_scope`。My Teams DTO 只包含 Team 名称和状态、Membership ID/状态、Role 与 Scope，不返回
ORM 或任何凭证字段。多 Team 未选择返回 `TEAM_CONTEXT_REQUIRED`；非成员、停用 Membership 或
停用 Team 返回 `TEAM_ACCESS_DENIED`；无 Active Membership 返回 `TEAM_MEMBERSHIP_REQUIRED`。

Human Auth V1 已为 `users` 增加可空 `login_name/password_hash`，并以服务端人员会话识别
`HumanPrincipal`。`POST /api/v1/auth/login` 建立 HttpOnly Cookie，`POST /api/v1/auth/logout`
撤销当前会话，`GET /api/v1/auth/me` 只返回当前人员最小摘要。现有通用 `UserRead` 不返回
`login_name/password_hash`；后续 Access Management 必须使用独立、受权限保护的管理 Contract。
`get_human_principal` 不接受可伪造的 User-ID Header；ActorContext、Team 选择与既有 Access API
Contract 保持不变。

## Access Management V1 Contract

> **0037 覆盖说明：** 下方 `access_admin`、成员级模块/Scope 和旧 Membership 编辑描述为
> 0025 的历史 API 背景。当前管理接口全部要求超级账号；普通成员的模块、设备和店铺可用范围
> 来自 Team 授权，不再来自 Membership 字段。

当前新增或变更的正式管理接口为：

- `PUT /members/{user_id}/team`：指定唯一目标 Team；`team_id: null` 表示移出团队。
- `POST /teams/{team_id}/archive`：归档 Team 及其当前成员关系，保留业务数据。
- `DELETE /teams/{team_id}`：仅无成员、授权关系和业务引用的空 Team 可删除。
- `GET/PUT /teams/{team_id}/authorization`：读取或原子更新该 Team 的模块、设备和店铺授权。
- `GET /me/module-access`：返回 `is_super_account`；为旧客户端保留
  `is_access_administrator` 同义字段。未分配普通成员返回空模块集合，不把有效会话伪装成 401。

超级账号创建 Team-owned 业务对象必须携带有效 `X-Team-ID`。所有普通成员资源查询都必须在
授权范围内先过滤、再分页；管理列表分页与资源选择器不能用前端全量结果代替服务端校验。

统一前缀为 `/api/v1/access-management`。`GET /me/module-access` 需要有效的 Human
ActorContext，返回当前选中 Membership 的 `module_codes` 和
`is_access_administrator`，不返回 User、Team、密码或会话内部字段。

以下人员、Team 与 Membership 管理接口均要求当前选中 Membership 的
`role_code=access_admin`：

- `GET/POST /members`：分页查询（可按显示名或登录账号 search）与创建人员。
- `GET/PATCH /members/{user_id}`：读取人员管理视图、启用或停用人员。
- `POST /members/{user_id}/password`：重置密码并撤销该人员全部 Human Session。
- `POST /members/{user_id}/memberships`、`PATCH /memberships/{membership_id}`：新增或更新
  Team Membership、数据范围、启用状态、角色与模块访问。
- `GET/POST /teams`、`PATCH /teams/{team_id}`：读取、创建和更新 Team；不提供 Hard Delete。

历史 `/api/v1/users` Core Domain 路由也改为 `access_admin` 才可调用，防止它成为新人员管理边界的
绕过入口；PC 管理端必须使用上列 Access Management Contract，不以旧 `UserRead` 管理登录凭据或
Membership。

人员创建请求只在写入期接收 `password`，响应的人员、Membership 与 Team DTO 永不包含密码、
Password Hash、Cookie 或 Session Token。管理角色只有 `member` 和 `access_admin`；模块代码只能
是当前 PC Module Registry 的 `shop / asset / ai-workbench / device / task / schedule / settings`，
不接受 development-only `foundation` 或未知值。模块代码重复、未知角色及空 PATCH 均由
`VALIDATION_ERROR` 拒绝。

管理边界失败使用 `HUMAN_AUTHENTICATION_REQUIRED`、
`ACCESS_ADMINISTRATION_FORBIDDEN`、`MODULE_ACCESS_DENIED`、
`LAST_ACCESS_ADMINISTRATOR_REQUIRED`、`TEAM_DISABLED`、`TEAM_MEMBERSHIP_CONFLICT` 等正式错误码。
资料库、Device、Task 与 Schedule 的全部 Human 路由分别执行 `asset`、`device`、`task`、`schedule`
模块授权，并使用 ActorContext 的 `SELF / TEAM / ALL` 读取范围。它们的 Create DTO 不接受 Team 或
创建者；这两个 Ownership 字段只从 ActorContext 或可信 Schedule 继承。Shop、Credential、Shop
Session 与 Shop Onboarding 管理路由同样要求 Human Session、ActorContext 与 `shop` 模块访问；当前
Shop 尚未建立 Ownership Scope。Automation Application Config 要求 `device` 模块访问，Notification
Channel 管理与 Webhook 测试要求 `settings` 模块访问。Worker / Device Token 路由不使用 Human Guard。

Pydantic Create、Update、Read Schema 是正式 API Contract。Shop Device Binding 只包含
`shop_id / device_id / enabled` 与时间字段，不再包含 PRIMARY/BACKUP role。Frontend 的 GMV、
Session/自动化状态、CPU/内存、Worker 版本、当前任务和展示文本不属于这些 Read Schema。

Shop List 使用 `ShopListRead`，在 `ShopRead` 基础上增加可空 `session_status`：没有 ShopSession 时为 `null`，其余值直接来自正式 ShopSession Status，不由 Frontend 猜测。普通 List 与 Detail 默认排除 `deleted_at IS NOT NULL`；对已移除 Shop 的 GET、PATCH、Binding 与 Session 业务访问返回 `SHOP_NOT_FOUND`。`DELETE /api/v1/shops/{shop_id}` 返回 204，但数据库记录及认证事实仍保留。

`GET /api/v1/shops` 的 `enabled / device_id / owner_user_id / platform / q` 与 `GET /api/v1/devices`
的 `status / search` 都在服务端授权范围内先过滤，再执行稳定排序、分页和 `count`。Device `search`
匹配名称、位置及 Yingdao Inventory 的账号显示名；它不扩大 Device Data Scope。Registry 中尚未接入数据库
枚举的平台查询返回空页，不把前端展示能力伪装为可创建平台。

带 `platform_shop_id` 的 Shop 已由平台身份识别建立。普通 `ShopUpdate` 不允许修改其 `display_name` 或 `platform`，且 Contract 本身不接受 `platform_shop_id` 更新；负责人、备注和既有 `enabled` 语义不受影响。`Shop.enabled` 不是自动化总开关。

`Shop.enabled=true/false` 分别表示店铺可/不可参与正常系统业务；当前不存在 `automation_enabled`，禁止用 `Shop.enabled` 表达自动化总开关。

`PATCH /api/v1/shops/{shop_id}` 的当前超级账号可以显式提交可空 `operating_start_date`。该日期仅用于界定经营数据
应采覆盖范围，不是店铺加入中控台、首次采集或首次出单日期；显式 `null` 表示经营起算日未确认。来源、设置人和时间由
服务端写入并只读返回，客户端不能伪造审计字段。若拟定日期之前已有任何已确认成交、订单或退款事实，服务端返回
`409 OPERATING_START_DATE_CONFLICT`，而不是隐藏既有事实。来源未知时，经营看板保留完整选择范围作为应采范围。

## Credential / Session Metadata Contract

阶段 3A 增加：

- `GET /api/v1/shops/{shop_id}/credential`：仅返回脱敏账号、配置/启用状态、验证码渠道和更新时间。
- `POST /api/v1/credentials`、`PATCH /api/v1/credentials/{credential_id}`、`POST /api/v1/credentials/{credential_id}/disable`：写入与停用凭证。
- `GET /api/v1/shops/{shop_id}/session`：仅返回 Session 状态、版本、来源设备和时间元数据。
- `POST /api/v1/shops/{shop_id}/session/health-check`：人工执行权威只读验证，只返回身份与 Session 元数据。
- `POST /api/v1/shops/{shop_id}/session/refresh-lease`：获取可过期恢复租约和当前 `expected_version`。
- `DELETE /api/v1/shops/{shop_id}/session/refresh-lease/{lease_id}`：取消并释放当前客户端持有的租约。
- `POST /api/v1/shops/{shop_id}/session/refresh`：仅供 Electron Main 提交内存中的新 Session；Renderer 不接触 payload。
- `POST /api/v1/shop-onboarding/pdd/identity`：首次接入的 Electron Main 将内存中的 PDD Cookie
  payload 交给固定平台接口预检；只返回已验证的 `platform_shop_id / shop_display_name`，不创建任何
  Shop、Credential 或 ShopSession。

Credential Read 不含密码、密文；Session Read 不含 Cookie、payload 或密文。密码只存在于 Create/Update 写请求，Update 的空字符串表示保留现有密码。Session payload 的写入目前只属于内部 Service Contract，不开放普通 Frontend Route。

Electron Main 进行店铺接入或 Session 恢复时，从其受控的应用会话读取 HttpOnly Human Cookie 并附加当前
`X-Team-ID`；Cookie 不经过 Renderer，也不接受 Renderer 传入的 Raw Session Token。

## Device Provider Inventory Contract

阶段 3B-1A 增加最新 Provider 快照：

- `POST /api/v1/worker/provider-inventory`：Worker 认证接口，请求只含
  `provider_code` 与严格校验的 `inventory`，不接受 Body `device_id`。
- `GET /api/v1/devices/{device_id}/provider-inventories`：读取指定设备的最新 Provider
  快照。

当前正式 Provider 为 `yingdao`。影刀 Inventory 只包含状态/原因、版本、登录状态、安全账号元数据、
当前 userId、当前账号云端应用的 ID/名称/versionId/updateTime/appType/groupId 与发现时间；禁止密码、
Token、Cookie 和完整认证响应。应用数组作为外部 Provider 最新快照存入专用 JSONB，
不是通用业务 JSON，也不是中控台 Skill 注册表。

Inventory 状态使用 `not_installed / version_unsupported / starting / need_login /
interface_unreachable / ready`。`available` 与执行能力由
`execution_available / execution_version / execution_unavailable_reason` 独立表达。
本地 Discovery 无法从可验证数据得到账号类型或企业标记时，`account_type`
与 `enterprise_account` 允许为空；Worker 不得猜测或伪造这两个字段。

## Device Skill Capability Contract

- `PUT /api/v1/worker/skill-capabilities`：认证 Worker 上报本机 Skill Registry 完整快照；
  Body 只含 Descriptor 数组，不接受 `device_id`。
- `GET /api/v1/devices/{device_id}/skill-capabilities`：查询设备最后一次已知 Skill 能力。

Descriptor 固定包含
`skill_id / display_name / runtime / provider / version / classification`；分类只有
`internal | business`。Skill Capability
不等于 Provider Capability，也不等于影刀 Application。`yingdao.app.run` 是通用 Skill，
具体影刀应用由 Task `input.app_id` 选择；影刀的 9 个 Application 不注册成 9 个 Skill。

`device_skill_capabilities.classification` 是独立、可查询列。新 Worker 必须随完整快照上报；
兼容旧 Worker 时，Backend 只对现有五个已知内置 Skill 回填 `internal`，无法可靠判断的旧记录
保留 null，不能猜为 `business`。设备能力读取仍返回完整快照；普通 UI 只展示明确为
`business` 的记录。

## Automation Application Config API

- `GET /api/v1/automation-app-configs/{provider_code}/{app_id}`：读取应用参数配置，未配置返回 null。
- `PUT /api/v1/automation-app-configs/{provider_code}/{app_id}`：保存手工参数 Schema。
- `GET /api/v1/automation-app-configs/yingdao/applications`：返回当前 ActorContext Team 已可见 Device 的
  Provider Inventory 中去重后的 `{app_id, app_name}` 选项；不返回 Device、影刀账号、店铺或 Credential
  事实。可选 `device_id` 时先按正式 Device DataScope 查找该设备，再只返回它已上报的应用；不可见设备按
  `DEVICE_NOT_FOUND` 处理。

当前 provider 仅允许 `yingdao`。字段类型为 text/number/boolean/select；Backend 校验字段名、
重复项、选择项、默认值和类型。该 API 不读取或保存影刀 Credential。
所有读取与保存均要求 Human Session、ActorContext 与 `device` 模块访问。

`input_schema.fields[]` 的 `name` 是 Task `input.params` 与 Worker `params.json` 的正式 JSON 键。
它允许 Unicode 字母或数字及 `_ . -`，包括 `商品列表`；会拒绝空白、空格、控制字符、重复项与超过
100 字符的键，且不得翻译、拼音化或改写。`label` 是用户界面显示名，可留空；保存和 Read 时空值固定
回退为对应 `name`，所有必填和类型错误使用该最终显示名。`text` 的 `default_value` 始终是字符串，
即使内容形如 JSON；它不会被解析成新的参数类型。选择参数必须有不重复选项，所有默认值必须匹配其
text/number/boolean/select 类型。

配置保存的请求校验使用 `422 / VALIDATION_ERROR`；`details` 保留 Pydantic 的字段定位，PC 弹窗必须
映射到对应参数行/字段并保留未保存草稿，而不是关闭弹窗或只显示泛化错误。

### 影刀参数预设

`yingdao` 应用的参数预设使用
`/api/v1/automation-app-configs/yingdao/{app_id}/parameter-presets` 的 list/create/read/update/copy/delete
路由。预设只归属于创建时的 ActorContext Team；服务端在列表、详情、修改、复制和运行取快照时均再次
确认该 Team，不能由前端传 Team、User 或预设 ID 获得另一 Team 的记录。

参数配置库使用 `GET /api/v1/automation-parameter-presets` 查询当前 Team 预设；可选 `device_id`、`app_id` 与
`q`（名称）过滤在服务端的 ActorContext / DataScope 查询边界完成。`device_id` 只把 SQL 分页集合限制到
该可见设备上报的应用 ID，不改变预设的 Team + app_id 归属，也不建立设备副本。未携带 `page` 和 `page_size` 时，
为旧客户端返回完整 DTO 数组；携带任一分页参数时返回 `{items,total,page,page_size}`，另一个参数
沿用默认 `1 / 20`（page_size 最大 100）。显式空值、非法数字或越界值返回 `422 / VALIDATION_ERROR`，
不能降级为数组模式。OpenAPI 响应为 Page 或数组的联合类型；新版管理 UI 始终显式发送分页参数。
当前 Team 限制、过滤、`total`、`updated_at DESC,
preset_id ASC` 排序和分页必须来自同一 SQL 集合；即使 Actor 在其他资源具备 `ALL` scope 也不返回其他
Team 的预设。按应用读取、供运行／计划选择器使用的
`GET /api/v1/automation-app-configs/yingdao/{app_id}/parameter-presets` 保持完整列表，不能因管理页分页遗漏
可选预设。上述两类读取路由继续使用
既有 `device` 模块 Guard；预设路由还保留现有 `shop` 模块 Guard。它们不建立 Shop Team Ownership，
也不改变 Task/Schedule 创建时对目标 Device、Binding、启用状态和 Credential 的正式校验。

每个预设保存 `name`、`input_schema`（持久化为 `input_schema_snapshot`）、`common_parameters`、以 `shop_id`
为键的 `shop_overrides` 和递增 `version`。应用 Schema 只为新预设提供初始模板；预设保存后，字段名称、类型、
必填、默认值和选项只以该预设 snapshot 为准，应用共用 Schema 后续变化不重解释已有预设、Task 或 Schedule。
Read DTO 额外返回 `invalid_parameter_names`，它只标记该预设 snapshot 中不存在的历史键，绝不自动删除旧值。0036
迁移只将历史已存公共/店铺键中能在当时应用 Schema 识别的字段写入 snapshot；未知键和值原样保留并以该诊断
要求修正，绝不猜测字段定义。回退 0036 会移除独立 snapshot；再次升级只能按仍持久化的参数键和当时应用模板
确定性重建，不能恢复已删除的 snapshot-only 字段，因此发布回退前须确认这一数据语义。更新必须
携带当前 Read DTO 的 `expected_version`；版本不一致返回 `409 / AUTOMATION_PARAMETER_PRESET_VERSION_CONFLICT`，
客户端保留草稿并刷新后由用户决定如何处理。公共参数只保存当前预设显式选择的字段和值，不能因保存或回读
自动把同一应用的默认值写回预设；应用字段定义只在新建时提供初始模板，已有预设的独立 snapshot 才是唯一
契约。店铺覆盖只保存
与公共参数不同的字段。预设的已保存键是明确启用字段集合：Task/Schedule 快照只合并、校验并下发这组字段，
不会为未启用的可选字段补入 Schema 默认值；若当前 Schema 的必填字段不在该集合，保存、Task 创建或计划触发
必须以参数预设契约错误失败，不能静默补值。旧预设已有键继续按其已有集合兼容；无预设的手工参数模式维持原有
全 Schema/default 物化语义。合并/字段校验只使用该应用已保存的 Schema，必须保留合法的 `0`、
`false` 和空字符串。预设服务通过既有 Shop 查询和 `shop` 模块授权核验每个 `shop_id`。当前 Shop 尚未
建立 Team Ownership Scope，因此这复用的是现行正式 Shop 可见范围；Target Device Binding 仅是本次执行资格
检查，不能被表述或实现为新的 Shop 人员归属授权。Credential、Cookie 和账号明文永不保存进预设。

`DELETE /api/v1/automation-app-configs/yingdao/{app_id}/parameter-presets/{preset_id}` 也执行相同的
ActorContext、`device` 和 `shop` Guard。删除是逻辑删除：日常列表、详情、选择器、复制与新 Task/Schedule
引用只读取 `deleted_at IS NULL` 的预设；历史 Task 和已归档 Schedule 保留原 `parameter_preset_id`、版本及
参数快照，不改写应用字段、Shop 或历史输入。未归档 Schedule（包括已停用 Schedule）仍可再次启用或触发，
因此会返回 `409 / AUTOMATION_PARAMETER_PRESET_IN_USE`，`details.schedules` 精确列出关联计划 ID 与名称，
用户必须先更换预设或归档计划。Task/Schedule 创建解析预设时与删除使用同一行锁，避免删除后的预设并发进入
新的引用；已删除预设按 `404 / AUTOMATION_PARAMETER_PRESET_NOT_FOUND` 拒绝新引用。

新建运行／计划的 UI 在应用存在输入字段时必须先明确选择参数预设或“本次手动参数”；未选择不是手动模式，
不得由客户端隐式提交或展示应用模板字段。该 UI 规则不改变 Backend 的旧手动调用兼容：无预设的正式旧调用
继续按应用 Schema/default 物化。应用没有 Schema 字段时，`params={}` 是唯一无参数运行语义，Backend 不得
凭空补入其他应用的模板默认值。历史无预设 Task/Schedule 继续按其已保存的平铺参数读取。

`POST /api/v1/tasks` 选择预设时只提交 `parameter_preset_id`；Backend 在既有 Device、Shop 启用状态、
Binding 与 Credential 校验成功后，才物化本次选中 Shop 的合并结果。Task `input.params` 保存不可变快照：
`{"格式版本":1,"公共参数":{...},"店铺参数":{"<shop_id>":{...}}}`，并在 Task 行保存
`parameter_preset_id` 与 `parameter_preset_version`。手工参数模式继续保存原平铺对象且两个 Task 字段均为
`NULL`。Worker 不做继承、合并或授权判断。

`POST /api/v1/tasks` 创建 `yingdao.app.run` 时，input 固定为
`{"app_id":"...","params":{...}}`。店铺上下文通过独立有序 `shop_ids` 提交，不进入 input。
Backend 必须验证目标 Device 启用、全部 Shop 有效并与该 Device 存在启用 Binding、账号可用、
最新影刀 Inventory 为 ready、执行可用、已登录、App 对当前账号可见，并按已保存 Schema校验/补齐 params。
`shop_ids` 允许为空；只有非空集合才执行 Shop、Binding 与 Credential 校验，空集合在认证 Claim 中
返回 `accounts=[]`。

## Device Lifecycle API

- 全部 `/api/v1/devices` Human 路由要求 Human Session、`device` 模块访问与 ActorContext Scope；创建
  Device 固定归属当前 Team 与当前人员。详情、辅助 Device 查询和写入都不能用直接 ID 绕过 Scope，ALL
  也不允许跨 Team 写入。
- `PATCH /api/v1/devices/{device_id}` 的 `enabled` 是执行资格，不是在线状态。
- `DELETE /api/v1/devices/{device_id}` 返回 204，但实现为软移除；有活动任务时返回 `409 / DEVICE_HAS_ACTIVE_TASKS`。
- 已移除 Device 的列表与详情行为和 Shop 软删除一致：普通读取视为不存在。

## Worker Credential / Provisioning API

- `GET /api/v1/devices/{device_id}/worker-credential`：只返回
  `not_issued / issued / revoked` 与真实签发时间，不返回 Token、Hash、尾号或虚构使用时间。
- `POST /api/v1/devices/{device_id}/worker-credential/issue`：仅在没有有效凭证时签发；
  `token` 明文只在该次 `Cache-Control: no-store` 响应返回一次。
- `POST /api/v1/devices/{device_id}/worker-credential/rotate`：要求当前存在有效凭证，原 Hash
  立即被新 Hash 替换，旧 Token 不再通过认证；新 Token 同样只返回一次。
- `POST /api/v1/devices/{device_id}/worker-credential/revoke`：将当前凭证置为无效，不删除
  Device；之后 Worker Heartbeat、Poll、Capability Sync 均认证失败。
- `GET /api/v1/worker/provisioning`：首次 GUI 配置专用。只携带 Bearer Worker Token，Backend
  从 Token Hash 解析该 Token 自己的 Device ID、显示名称和启用状态；不接受客户端声明
  Device ID，也不能解析其他设备身份。其余 Worker API 仍必须同时使用 Bearer Token 与
  `X-Device-ID`。

Backend 永远只保存 Token Hash。Frontend 不提供旧 Token 读取；明文只在签发/轮换的短生命
周期 Dialog 中存在，不进入 Query Cache。

## Business Skill Catalog API

- `GET /api/v1/devices/{device_id}/business-skills`：返回指定 Device 最近一次 Worker Snapshot 中
  `classification=business` 的 Skill Catalog；Internal Skill 不进入该接口。
- Catalog 项至少包含稳定 Skill ID、显示名、版本、Runtime、Provider、分类、可用性状态和经
  Backend 规范化的 Input Schema。它不返回 Python 源码、安装包或动态执行入口。
- `input_schema` 唯一来源是 Worker Business Skill 的 Pydantic Input Model。旧 Worker 未上报
  Schema 时正常返回 `schema_unavailable`，不得 500；复杂或超出支持边界的 Schema 返回
  `schema_unsupported`。调用方不得自行猜参数。

Catalog 是 Device Scope：不同设备可以拥有不同 Business Skill 和版本。它只表达最后已知能力；
Device 是否在线、启用以及 Task 是否可创建仍由 Task Guard 在保存和触发时判断。

## Notification Channel API

- `GET/POST /api/v1/notification-channels`
- `PATCH /api/v1/notification-channels/{channel_id}`
- `POST /api/v1/notification-channels/{channel_id}/test`

Read Contract 只返回 `webhook_configured`，永不返回 Webhook URL 或密文。Update 的空 Webhook 表示保留原 Secret；测试消息由 Backend 投递。
所有读取、配置与测试均要求 Human Session、ActorContext 与 `settings` 模块访问。

## Task Runtime Event API

全部 `/api/v1/tasks` Human 路由要求 Human Session、`task` 模块访问与 ActorContext Scope；即时创建
Task 固定归属当前 Team 与当前人员，且目标 Device 与关联 Asset 必须在该 Team。`GET /events` 在读取
事件前先以相同 Scope 查询 Task。Schedule 生成的 Task 继承 Schedule 的 Team 与业务发起人。

`POST /api/v1/tasks` 的 `shop_ids` 是有序的正式店铺上下文集合，也可显式为 `[]`；需要店铺账号的
即时任务必须明确提交非空集合，但账号内容不得放进 `input`。重复 ID 被拒绝。仅非空集合中任一
Shop 无效、停用、已移除、未与目标 Device 有效绑定或缺少可用 Credential 时整次创建失败，不静默
跳过。Backend 只创建一个 Task，`TaskRead` 返回原顺序的关系 ID。认证 Worker 调用 Claim 时，Backend
才按关系顺序读取当前启用且平台匹配的 Credential，并在 Claim 响应的 `accounts` 数组中下发最小 Payload：
`shop_id / platform_code / login_identifier / secret / preferred_verification_channel`。
无店铺上下文的 Claim 返回 `accounts=[]`。普通 Task Read/List、Runtime Event 与 Result 不返回账号明文。

同一创建接口的 `asset_ids` 是可空、有序且不可重复的图片关系集合。Backend 必须一次验证全部
Asset 存在，并仍只创建一个 Task；不得按 Shop 或图片拆分任务，也不得把 Base64、服务端文件
路径或永久下载 URL 写入 `input`。`TaskRead.asset_ids` 只返回关系 ID。Worker Claim 的 `assets`
按原顺序返回 `asset_id / filename / position / content_type / size_bytes / sha256 / download_path`；
无图片时该数组为空。下载路径是短期运行信息，不写回 Task JSON。

- `GET /api/v1/tasks`：管理端 Task 分页列表，支持
  `status / device_id / search / created_from / created_to`；时间语义固定为基于
  `Task.created_at` 的 `[created_from, created_to)`，两个时间参数都必须带时区。search 只覆盖
  Task ID、创建时固化的 `execution_display_name` 与 `skill_id`。默认按
  `created_at DESC, task_id DESC` 稳定排序，不改变 Worker Claim 的升序执行规则。
- `POST /api/v1/worker/tasks/{task_id}/events`：Worker Bearer Token + `X-Device-ID`
  认证的事件批量写入；认证设备必须等于 Task target，重复 `(task_id, seq)` 幂等忽略。
- `GET /api/v1/tasks/{task_id}/events`：不传游标时读取最近的有限窗口；`before_seq` 向历史方向
  加载，`after_seq` 向实时方向增量读取，两者互斥。所有响应按 seq 升序，`limit` 服务端上限
  为 200，不允许一次返回完整历史。
- `POST /api/v1/tasks/runtime-events/purge-expired`：按当前 Backend Retention 配置立即清理已
  过期 Terminal Task 的 Runtime Event，返回 `cutoff / tasks_purged / events_deleted`；不得
  接收任意日期，也不删除 Task。
- `GET /api/v1/tasks/active/{device_id}`：返回设备当前 PENDING/RUNNING Task 摘要；没有时 204。
  摘要包含创建 Task 时固化的 `execution_display_name`，不得要求 Frontend 按 app_id 发起
  N+1 Application Detail 请求。

事件 message 和 metadata 在 Worker 与 Backend 双层脱敏。设备主列表与 Inventory 等辅助
查询保持独立，活动 Task 摘要失败不得改变 Device 主数据成功语义。

Task 列表项只返回当前页展示所需摘要：Task/设备身份、状态、执行名称、Skill 展示名、
结构化 progress、当前安全消息和时间。它不返回完整 `task_events`。最新 progress/status/log
通过单页摘要 SQL 取得，禁止每行再请求 Device、Application 或 Events；完整事件只在打开
Task Runtime Drawer 后继续通过 `after_seq` 接口读取。软删除 Device 仍保留物理记录和历史
显示名，历史 Task 查询不得因此失败。

Task Detail 的 `runtime_events_purged_at` 为可空清理标记。Event 为空且标记为空表示从未产生
日志；Event 为空且标记非空表示历史日志已清理；标记非空但仍有 Event 表示清理后存在晚到
事件，调用方应展示“部分历史已清理”并继续显示现存 Event。

## Schedule API

全部 `/api/v1/schedules` 路由要求 Human Session、`schedule` Module Access 与 ActorContext Scope。
Create 不接收 Team 或创建者；Backend 从 ActorContext 保存 Ownership。`schedule_type` 只能为
`once / daily / weekly`：一次性规则要求 `local_date` 且 `weekdays=[]`，每日规则要求
`local_date=null` 且 `weekdays=[]`，每周规则要求 `local_date=null` 与不重复的 ISO weekday
数组（`1=周一` 至 `7=周日`）。`local_time` 不含 offset，`timezone` 是 IANA ID，`next_run_at` 是
Backend 计算的 UTC Instant。

`GET /api/v1/schedules` 在既有 `enabled / device_id / search / page / page_size` 外支持成对的
`occurrence_date=YYYY-MM-DD` 和 `view_timezone=<IANA timezone>`。缺任一参数或无效时区返回 422；
筛选范围是该本地日期转换的 UTC `[start, end)`，匹配该范围内的 `ScheduleRun.scheduled_for` 或
`Schedule.next_run_at`，然后才计算 total 和 page。详情、下载及触发状态不以此参数改变。

## 资料库 Asset API

- `POST /api/v1/assets`：单文件 multipart 上传，只接受真实 JPEG、PNG、WebP 内容，受 Backend
  配置的单文件大小限制；响应返回稳定 Asset 元数据、`media_type=image`、
  `source_type=upload` 与 SHA-256。
- `GET /api/v1/assets`：按文件名搜索并使用统一 `page/page_size` 分页。
- `GET /api/v1/assets/{asset_id}/content`：Frontend 预览与读取图片的正式接口，不暴露存储路径。
- `GET /api/v1/assets/{asset_id}/thumbnail`：同一 Human Auth、`asset` Module Access 与 Asset Scope
  下的卡片缩略图接口。响应固定为 WebP，最大边长 320px；它不是下载接口，也不替代原图
  `content`。
- `DELETE /api/v1/assets/{asset_id}`：只删除未被 Task 引用的图片；被引用时返回 `ASSET_IN_USE`。
- `GET /api/v1/worker/tasks/{task_id}/assets/{asset_id}`：仅允许持有现有 Worker 身份的目标设备在
  该 Task 处于 RUNNING 时下载其关联图片；其他设备、其他 Task 或非运行状态均不得读取。

HTTP Upload 只负责接收输入并调用 Asset Service。Asset Service 使用 Storage Adapter 原子保存
文件后提交数据库元数据；数据库提交失败会清理本次新文件。响应不包含 `storage_key`，任何
客户端都不得猜 Backend 文件系统路径。现有 URL 与 Worker Claim 的图片字段保持兼容，Claim
不会新增 `media_type / source_type / storage_key`。

`content` 保持原始 MIME、原始字节、原始 SHA-256 与下载/放大查看/AI 输入语义。`thumbnail`
只服务小尺寸 UI，使用 `Cache-Control: private` 且按 `Cookie, X-Team-ID` 变化；Frontend 必须通过
统一 Axios Client 获取 Blob，不能把受保护路径直接交给普通 `<img>`。缩略图暂不可用时返回
`ASSET_THUMBNAIL_UNAVAILABLE / 503`，不改变已经成功保存的 Asset 或 AI Generation Item 状态。

## AI Workbench Backend Foundation V1 API

统一前缀为 `/api/v1/ai-workbench`，全部为 Human API，并同时要求有效 `ActorContext` 与
`ai-workbench` Module Access：

- `GET/POST /template-groups`：按 Scope 分页查询或创建模板组。
- `GET/PATCH/DELETE /template-groups/{template_group_id}`：读取、编辑或删除模板组。
- `POST /template-groups/{template_group_id}/prompt-templates`：创建提示词模板。
- `PATCH/DELETE /template-groups/{template_group_id}/prompt-templates/{prompt_template_id}`：
  编辑或删除提示词模板。
- `POST /template-groups/{template_group_id}/prompt-templates/{prompt_template_id}/duplicate`：
  复制模板并归一序列。
- `PUT /template-groups/{template_group_id}/prompt-templates/reorder`：同角色内重排模板。
- `GET/POST /product-material-groups`：按 Scope 分页查询或创建商品素材组。
- `GET/PATCH/DELETE /product-material-groups/{material_group_id}`：读取、编辑或删除商品素材组。
- `POST /product-material-groups/{material_group_id}/assets` 与
  `DELETE /product-material-groups/{material_group_id}/assets/{asset_id}`：建立或解除 Asset 关系。
- `PUT /product-material-groups/{material_group_id}/template-bindings/{mode}`：按模式原子替换有序模板绑定。

列表复用 `Page[T]`、`page` 与 `page_size`；TemplateGroup 和 ProductMaterialGroup 的 Ownership
只从 ActorContext 写入，Create/Update DTO 不接受 Team、Creator 或 Data Scope。Asset 关系通过
现有 AssetService Scoped Lookup 校验；不存在、不可读或错误 Team 均返回
`ASSET_NOT_FOUND / 404`。模板组仍被 Binding 引用时返回
`TEMPLATE_GROUP_IN_USE / 409`。其余 AI 管理领域错误沿用统一 `AppError` Envelope，包括
`TEMPLATE_GROUP_NOT_FOUND`、`PROMPT_TEMPLATE_NOT_FOUND`、
`PRODUCT_MATERIAL_GROUP_NOT_FOUND`、`TEMPLATE_SEQUENCE_INVALID`、
`TEMPLATE_BINDING_INVALID` 与 `MATERIAL_ASSET_ROLE_INVALID`。

商品素材组详情中的 Asset 使用现有安全 `AssetRead` 投影，不返回 `storage_key`、bucket、绝对路径、
厂商 URL 或 Storage 凭据。本阶段没有 GenerationJob、Provider、Queue 或 Worker API。

## 罗盘手动选品数据库查询 V1

本Feature正式只读接口为 `GET /api/v1/product-selection/candidates` 和
`GET /api/v1/product-selection/observations/{observation_id}`，复用当前Human Session、ActorContext和
`product-selection`模块授权。权限及请求店铺Scope先于最新来源选择、搜索、排序和分页；详情固定读取列表来源UUID，
撤权后不可见。列表使用统一Page，支持shop_id、source_scope_hash、标题/字符串商品ID search，
以及checked_at、first_on_shelf_date、rank的原值排序；缺失末尾，同值candidate_id稳定排序。

`SelectionObservationRead`保留商品字符串ID、请求自有Shop与实际商家、明确统计区间、四项原始视频区间/单位、
差评率原值/unit及独立的榜单检查、指标获取、基础信息完整取数和尝试时间。Decimal以字符串传输，不进行未确认单位换算。
完整字段、未知映射与边界见[24-罗盘手动选品契约V1.md](24-罗盘手动选品契约V1.md)及Pydantic/OpenAPI。
这两个接口只读数据库，不证明手动执行、成功空榜单或失败运行状态已实现；执行、类目API及Real适配仍为PARTIAL。

## Operating Dashboard Data V1 API

经营看板正式 Human API 前缀为 `/api/v1/operating-dashboard`，全部要求 Human Session、当前
ActorContext 和既有 `shop` Module Access。该 Module Guard 只决定可进入看板；每个 Repository 查询和
采集任务读取还必须在 SQL 层应用当前 Actor 的 Shop Scope。超级账号按现有超管语义读取全部允许的 Shop；
普通成员只能读取/更新当前有效 Team 已授权的 Shop。前端传入的 `shop_id` 只是筛选条件，绝不是授权依据。

- `GET /api/v1/operating-dashboard`：`start_date / end_date` 必填，均为 Asia/Shanghai 完整自然日；范围最多
  60 天且不含今天。可选 `platform / shop_id`，可选且必须成对的 `sort_field / sort_direction`，以及统一
  `page / page_size`。后端先权限过滤、业务筛选、全量稳定排序、最后分页。响应包含 selected/comparison/trend
  date ranges、当前授权 Shop candidates、四卡、趋势、`table.items/total/page/page_size`、当前范围的
  `coverage` 与 `collection_available`。`coverage` 只统计当前授权、已启用、已支持采集的店铺日期；对已确认经营起算日
  的 Shop，只统计所选日期与 `[operating_start_date, end_date]` 的交集，并返回 `not_operating_shop_days`；起算日未知的
  Shop 保留完整选择范围并以 `shops_with_unknown_operating_start` 明示，绝不从首单或接入日期猜测。它返回
  已采集/总店铺日期数、有限缺失样本及 `missing / collecting / waiting_collection_time / waiting_reauthorization / failed / unknown` 状态，但读取
  不会发起平台请求。仅当前 `source_code + metric_contract` 的已确认日事实可计入覆盖、汇总和趋势；当前缺失以 `manual_backfill_required=true` 表明需要在看板主动更新，服务端不自动补历史范围。范围内已有的确认日事实必须保留在卡片、趋势和店铺行中：
  卡片汇总整个已授权筛选范围而非当前分页，趋势点只有完全缺失时才为 `null`，表格和趋势的
  `coverage_complete=false` 明确标识部分覆盖；缺失不补零。当前或对比周期有任一必要店铺日期不完整时，环比返回
  `unavailable`，不伪造涨跌。全范围都早于已确认起算日时 `coverage.no_operating_scope=true`，UI 显示“该范围尚未经营”，
  而不是伪造 0 或失败。当前已确认的抖店值为 `turnover_cents`、`order_count` 和
  `refund_order_count`。后者只表示罗盘“退款订单数（退款时间）”，单位为单，不能与同日成交订单相除推断退款率。
  退款覆盖独立由 `refund_order_coverage_complete` 表示：有有效观测时可展示已采集合计，范围不完整时不产生环比；
  `experience_score` 仍保持 `null`。
- `POST /api/v1/operating-dashboard/collections`：普通“更新数据”只按当前日期/平台/店铺范围检查并补齐当前
  核心成交缺口，以及 0040 前日事实的一次 `refund_order_count` 待观测状态，返回 `200` 的 submission（`up_to_date / collection_queued /
  attention_required / unsupported / not_operating`）而不是强行制造空 job。已完整的核心事实返回 `up_to_date`，不创建 job/item、
  不发平台请求；有缺口时只创建允许补采的店铺日期，已有 pending/running/等待重新授权 item 则复用。终态不可重试
  结果、重试冷却或尝试上限返回 `attention_required`，不会因连续点击绕过保护。它始终覆盖符合条件的所有授权 Shop，
  而非当前表格页；停用、删除、无授权或未接入平台的 Shop 不会触发平台请求。当前环境未启用执行器时返回
  `OPERATING_DASHBOARD_COLLECTION_UNAVAILABLE / 503`，不会创建永远 pending 的手动任务。全范围早于已确认经营起算日返回
  `not_operating`，不创建 Job 或 Item；所有兼容入队路径在持久化前也会再次按起算日裁剪。
- `POST /api/v1/operating-dashboard/collections/recollect`：只有用户从次级“重新采集当前筛选范围”操作明确发起时，
  才对所选、最多 60 个完整自然日的已支持范围请求重新采集。它仍复用权限、停用、范围、活动 item、终态失败、
  冷却、并发与幂等保护；失败绝不清空此前成功事实。submission 的 `queued_shop_days / active_shop_days /
  blocked_shop_days / waiting_shop_days / refund_attention_shop_days` 只表达脱敏的店铺日期计数。
  手动和 retry job 在真正发出每个请求前还会以保存的发起用户和 Team context 重新解析模块及 Shop 授权；
  调组、停用或撤销 Shop 访问后标记 `COLLECTION_REQUESTER_ACCESS_REVOKED`，不调用平台。
- `GET /api/v1/operating-dashboard/collections/{collection_job_id}`：返回当前 Actor 可读取 Shop 对应的脱敏
  item 进度、阶段、可重试状态与耗时；不返回 Cookie、Session、签名、完整平台响应或非本 Scope 的 item。
- `POST /api/v1/operating-dashboard/collections/{collection_job_id}/retry`：只接受当前 Actor 可读取的 retryable failed item，或用户明确指定的 `DOUYIN_OPERATING_DATA_INVALID_RESPONSE / response_parse` 原失败 item；重新授权暂停、授权范围外、已跳过或成功 item 都不能藉此绕过既有 Session/Shop 校验。

`coverage.missing_samples` 可附带 `session_recovery`，只投影当前授权缺失样本的原
`collection_job_id / collection_item_id`、当前 `session_version` 和 `requires_validation`。
没有资格时返回 `recovery_block_reason` 安全文案；不返回平台凭据或原始错误。
读取仅批量查询元数据，不验证 Session、不入队、不调用平台。页面在原“查看缺失”中提供明确恢复动作，
使用上述既有 retry 接口提交单个原失败项及 `session_recovery_version`，然后复用原 Job 进度查询。
资格展示与提交复用后端同一判断，提交仍须重新校验，过期的页面回执不是授权。
`VALID` 状态不表示验证时间仍新鲜；`requires_validation=true` 明确需要服务器权威复核，不能通过
补造验证时间或重复要求用户登录跳过这一步。普通更新不因这份投影自动发起恢复。

原 retry Body 可显式传入 `revalidate_current_session=true`（默认 `false`），且必须同时提交单个原
Item 和 `session_recovery_version`。它只允许已有 DAILY/FAILED/retryable 的
`session_preparation / SHOP_SESSION_VALIDATION_FAILED`，当前 Session 仍须 VALID、精确版本、
捕获晚于原失败、时间合法、店铺启用且身份/权限有效；不扩展其它失败类型。
旧默认提交保留 300 秒等既有 freshness 配置边界。显式选择时，仅允许将需要复核的当前会话排入原
`session-restored:{原Item}` 单次队列；原 collector 必须先通过 `HealthService.check(force=False)`，
才可请求经营数据。HTTP 202 仅表示排队，不表示复核或采集成功。跨进程/版本的同一原项只恢复一次，
失败和租约超时仍终态，旧失败及累计次数不改。

日金额使用整数分，响应/存储都不使用浮点累计；`null` 表示平台字段或完整日期覆盖缺失，不是 0。HTTP 200
不能替代平台业务成功：平台 Connector 在固定路径解析、身份/Session 验证、签名、业务状态与指标结构均成功后，
才可写入日事实。查询中的更新时间只来自实际成功采集时间。

### 当前指标契约与解析恢复边界

`core_index_v3` 当前正式持久化契约为 `income_amt`（成交金额，整数分）、`pay_cnt`（成交订单数）与可选
`refund_order_cnt`（页面“退款订单数（退款时间）”，单位单）。三者均从固定路径
`data.module_data.homepage_core_index.compass_general_multi_index_card_value.data[0].<metric>.index_value.value.value`
读取；金额不使用浮点累计，订单数不从 `last_value` 读取。受控脱敏样本还确认过固定路径存在、但
`index_value.value` 只包含 `unit` 而没有标量 `value` 的结构。这一精确结构以
`DOUYIN_OPERATING_DATA_METRICS_UNAVAILABLE / response_parse` 记录为 `coverage.missing_samples[].state=unknown`；
它不写日事实、不表示 0、不表示未经营，也不自动重试。核心字段直接缺失或标量显式为 `null` 分别以
`DOUYIN_OPERATING_DATA_CORE_METRIC_MISSING` 或 `DOUYIN_OPERATING_DATA_METRICS_NOT_READY` 记录为同一安全的
`unknown` 状态。其他不符合固定嵌套结构的响应仍以
`DOUYIN_OPERATING_DATA_INVALID_RESPONSE / response_parse` 失败，不能通过递归猜测同名字段恢复数值。

`refund_order_cnt` 已由同一页面指标“退款订单数（退款时间）”确认，不表示退货件数，也不表示按支付时间统计的退款订单。
同一响应中的 `refund_order_cnt_pay_time` 是独立“退款订单数（支付时间）”指标，本期不解析、不存储、不展示，也不能
代替前者。可选退款字段缺失、`null` 或异常结构分别记录为 `unavailable / not_ready / invalid`，不使有效成交事实失败，
不转成 0，也不触发无限自动补采；已有 0039 核心事实只在 `unobserved` 状态下接受一次有界退款观测。显式“重新采集”
可以按既有范围和权限重新取得该日观测，失败不清空既有成功值。商家体验分没有已验证的服务端 Endpoint、响应路径和
时间语义，继续返回 `null`，不能由 Mock 或罗盘其它指标推断。

平台明确的数值 `0` 是有效事实；HTTP 200、业务成功、空对象、缺字段或 `null` 单独都不足以表示零值。当前仅有受控
服务端样本证明 2026-09-16 的退款字段显式为 0；2026-09-15 的核心字段在成功包装结构中缺失，仍分类为未知的
`response_parse`，不能据此推断未经营或零成交。尚未取得真实“成交金额 0、成交订单 0、退款订单大于 0”平台样本，
该组合由契约测试覆盖，不能冒充为真实平台验证；也尚未取得可信的抖店开业/经营起始日期接口语义。

旧的不可重试解析失败不会被全局改写为可重试。显式重采或指定 Item retry 可对通用 `response_parse` 发起有限恢复，
原失败 Item 保留；三个 `unknown` 码、会话、风险及未知业务拒绝不在恢复例外内。不再使用工程人员 UUID 清单。
普通更新、显式重采及 Item retry 共用冷却与同店同日失败链预算；成功结束失败链，新建 Job 不重置失败额度。
完整范围普通更新不创建 Job/Item、不请求平台。昨日未到上海 09:00 时排队等待，更早历史日期不一起等待。
首次手动范围不会写起算日，日计划仅昨日；接入、启用、启动和重新授权不创建历史补采，见后台调度规范。
