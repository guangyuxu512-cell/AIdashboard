# 账号凭证与 Session 规范

## 1. 领域关系

```text
PlatformCredential ──< ShopCredentialBinding >── Shop ── ShopSession
```

`PlatformCredential` 表达平台登录账号，保存平台、统一登录标识、加密 Secret、首选验证码渠道和启用状态。账号不能直接写入 `shops`：同一平台账号未来可能发现并管理多家店铺，凭证生命周期也独立于店铺主档。

`ShopCredentialBinding` 负责关联。一个 Credential 可绑定多家同平台 Shop；当前一个 Shop 最多有一个启用 Binding，不提前引入多角色凭证策略。

## 2. Credential 安全

- `login_identifier` 统一承载手机号、邮箱、用户名或账号 ID。
- `secret_encrypted` 使用 `cryptography.fernet.Fernet` 与服务器环境密钥 `BACKEND_ENCRYPTION_KEY` 加密。
- 数据库、日志、错误、审计和 Read API 均不得出现明文密码。
- 更新请求中账号或密码空字符串表示不修改；只有非空新密码才替换密文。
- Read API 只返回脱敏标识、`configured`、`enabled`、验证码渠道和更新时间。由于 Create 时 Secret 必填，Frontend 可由 `configured` 派生“密码已配置”，API 不增加任何 password read 字段。

密钥不进入 Git。无有效密钥时 Credential/Session 敏感写入必须显式失败。

## 3. ShopSession

`ShopSession` 每店铺一条当前快照，持有 `version`、必要状态、来源设备、采集/验证/可选过期时间，以及 `payload_encrypted`。Payload 可以承载 Cookie 和必要认证快照，但不是任意业务 JSON 容器。

状态包含：`not_configured`、`captured`、`valid`、`invalid`、`refresh_required`。`captured` 表示真实登录身份已经识别且 payload 已加密保存，但尚未通过服务器只读平台接口验证；不得把它展示成 `valid`。没有记录时 Metadata 返回版本 `0`。已有店铺首次登录可用数据库唯一 Shop 行建立 `not_configured` 版本 `1` 的租约保留记录（加密空载荷及内部保留时间），不是可用 Session；API 的 `configured=false`、采集/验证时间为 `null`，Accessor 在解密或平台请求前拒绝。失败、取消和超时保留未配置状态；匹配的真实验证成功后才 CAS 为 `valid` 版本 `2`。不改变新增店铺 Onboarding 的首次版本 `1`。

管理端首次登录不是 Worker，使用 `source_device_id = NULL`。未来 Worker 重采集才写入真实 Device ID，禁止为管理电脑伪造 Device。

Session payload 与密码共用成熟的加密基础设施，但在领域上互相独立。普通 API 只返回元数据，绝不返回 Cookie、payload 或密文。

Shop List 只投影 ShopSession 的状态机器值，不返回 version、Cookie、Token 或 Profile。Shop 被软移除时 Credential、ShopCredentialBinding 与 ShopSession 全部保留；普通业务入口因 Shop 已移除而返回 `SHOP_NOT_FOUND`，内部审计与恢复数据仍可追溯。

## 4. 并发版本

首次写入必须携带 `expected_version=0`，生成版本 `1`。后续更新以数据库条件更新 `WHERE shop_id = ... AND version = expected_version` 并原子递增。版本不匹配返回冲突，旧设备不能覆盖新 Session。

## 5. Worker 下发边界

不提供 Secret 或 Session payload 的普通管理端读取 Route。Multi-Shop Task Account Payload 只在
Worker 使用现有 Device Token 与 `X-Device-ID` 成功认证并原子领取一个带 `shop_ids` 的 Task 后，
通过 Claim 的 `accounts` 数组临时下发。每项固定为：`shop_id / platform_code /
login_identifier / secret / preferred_verification_channel`。字段全部来自现有 Shop/Credential，
不猜 username/password/cookie 别名；Session/Cookie 与验证码挑战不在此 Payload 内。禁止
`GET /all-credentials` 和设备批量下载。

Task 只在 `task_shops` 持久化有序关系，不持久化账号明文；Claim 时由 `CredentialService` 批量
读取当前启用 Binding、校验平台并解密，返回顺序与 Task 关系一致。账号 Payload 不进入 Task
input、日志、Runtime Event、Result 或普通 Read DTO。Worker 0.4.5 仅在落地边界把英文内部字段
映射为中文 `account.json`，根对象固定为 `店铺列表`；Python Business Skill 只通过英文
`ctx.accounts` 读取。没有店铺上下文时两边均得到空列表语义。

Browser Profile 永远保留在设备侧，并按 `Device × Shop` 隔离；服务器集中管理 Credential、Session 与业务数据，不上传完整 Chrome Profile。

## 6. 管理端原子接入

阶段 3C-1 的完成命令由 Electron Main 在 Adapter 已确认身份并采集 payload 后调用。Backend 在单个数据库事务内创建 Shop、PlatformCredential、ShopCredentialBinding 与 ShopSession；失败全部回滚。Shop 使用 `(platform, platform_shop_id)` 唯一约束避免同一平台店铺重复接入。

拼多多 V1 的身份来源例外于抖店：Electron Main 只采集适用于 `mms.pinduoduo.com` 的登录 Cookie，不将店铺 ID 或名称交给 Renderer 推断。采集后先由 Backend 的无持久化预检，以独立 Node 子进程生成当次 `anti-content`，调用固定的 `POST /earth/api/merchant/queryMerchantInfoByMallId`（Body 为 `{}`），且仅接受平台成功码 `1000000` 的 `result.mallId` 与 `result.mallName`。只有预检成功 Electron 才关闭登录窗口；Cookie 存在、页面加载或 URL 跳转均不是成功条件。完成命令不得携带 PDD 的平台店铺身份字段，原子接入前仍会再次验证；无法验证时不创建部分记录。

平台接入建立后，`display_name` 与 `platform_shop_id` 共同属于外部平台真实身份，不允许普通 Shop Update 修改；本阶段不新增内部别名。抖店在 Main 身份识别完成后可关闭窗口；拼多多必须在上述 Backend 身份预检成功后才可关闭。Backend 只在用户确认完成时执行原子接入写入。

## 7. 审计与后续实现

Credential 变更、Session 版本变更及授权读取未来必须接入审计，但审计只记录主体、对象、动作和结果，不记录敏感值。阶段 3A 只建立 Domain、API 元数据和认证 Protocol，不实现 Worker、浏览器、Cookie 采集、验证码 Provider 或平台 Connector。

阶段 3C-2 起服务器请求通过 `ShopSessionAccessor` 取得认证上下文。只有 Accessor 可以解密
并校验 `management-login.session.v1`，业务 Service 与 Connector 都不得直接读取加密载荷。
`captured` 可用于首次只读验证；成功后同一 payload 标记为 `valid` 并记录
`validated_at`，只有正式 Connector 明确返回 `AUTH_INVALID` 才标记当前被验证的 Session 为 `invalid`。超时、签名、平台 5xx、原因未确定的业务拒绝与响应结构异常不改变
Session 状态，也不触发自动登录。Backend 请求不读取 Management Login Profile。

## 8. 健康检查、Cookie 更新与恢复租约

`ShopSessionHealthService` 是解密后验证、身份匹配和状态更新的唯一边界。抖店 V1 使用已验证的 `shop_info_v2`；最近验证时间仍处于 `BACKEND_SHOP_SESSION_VALIDATION_FRESHNESS_SECONDS` 窗口时，后续业务可直接使用，超出窗口才按需先验证。没有全店铺 Cron。

拼多多 V1 健康验证复用上述唯一边界与同一固定 merchant identity endpoint；每次请求仅在平台层生成并使用当次 `anti-content`，不记录 Cookie 或签名值。

Cookie 到期时间只用于预警，不阻止权威平台请求。HTTPX 响应真实提供 `Set-Cookie` 时，Accessor 按 name/domain/path 合并，保留 HttpOnly、Secure、SameSite 和 expires，随后加密并通过 `expected_version` 写入新版本；没有 Cookie 更新时只更新验证状态和时间。

人工恢复使用 `shop_sessions.refresh_lease_id` 与 `refresh_lease_expires_at` 作为跨 Backend 进程的可过期租约，不持有长事务。租约时长由 `BACKEND_SHOP_SESSION_REFRESH_LEASE_SECONDS` 配置，默认 1800 秒。完成、取消和 Electron 超时主动释放；客户端崩溃后由到期条件允许下一次获取。恢复提交先检查租约、版本和目标身份，关闭数据库事务后使用候选载荷做一次非缓存的权威验证，Set-Cookie 仅在内存合并。平台 I/O 后重新检查当前人员权限及店铺身份，再以租约+版本+未过期条件原子保存 `valid` 新版本并清除租约。候选失败（包括 `AUTH_INVALID`）不能证明旧 Session 失效，不修改旧 payload、状态、版本或时间；取消、过期、撤权和迟到结果不能覆盖较新状态。

### 罗盘经营数据的失效处理

抖店罗盘只读采集复用上述 Session 边界，不创建第二套刷新或浏览器常驻机制：

1. 采集前使用 `ShopSessionHealthService.check(force=False)`；缓存仍新鲜时不额外访问身份接口。
2. 平台 HTTP `401/403` 或本地 Session 未配置、无效、无法安全读取时，当前店铺的本批后续日期暂停，
   结果标记 `SHOP_REAUTHORIZATION_REQUIRED`。HTTP/网络超时、Signer 失败、平台业务拒绝和响应解析失败
   分别保留各自失败阶段，不能一律触发登录。
3. 重新授权仍走现有 Electron 管理登录和
   `POST /api/v1/shops/{shop_id}/session/refresh-lease` → `POST .../session/refresh`：新 Session 写入后必须
   完成身份健康校验，版本冲突不得覆盖较新的 Session。
4. 验证成功后，`OperatingDashboardService` 仅恢复该 Shop 原有、持久化的
   `paused_reauthorization` collection item；原店铺、原统计日期和已有 retry 边界保持不变，不触发新的30日历史补采。
   Session 已提交后队列恢复异常仅记录安全告警，不能误报登录失败或诱导重复保存。
5. `operating_data_collection_items` 的可过期 lease 用于 Backend 重启恢复：未完成 running item 到期后才重新
   pending；已经成功的数据不会因恢复被清空。当前没有“自动登录”或验证码绕过：需要扫码、验证码或人工确认时，
   仍由用户走上述 Electron 管理登录入口。通知能力尚未纳入本期，不把缺少通知伪装为自动恢复。

### 显式单项每日 Session 失败恢复（Shop Login Session Sync V1）

复用 `POST /api/v1/operating-dashboard/collections/{collection_job_id}/retry`；原 Body 的
`item_ids` 不变，可选 `session_recovery_version` 为当前新采集有效版本，提供时必须恰好一个原 Item。
只接受原 DAILY、FAILED、retryable、`session_preparation / SHOP_SESSION_VALIDATION_FAILED`，不是全局放开终态。
当前人员模块/团队/店铺授权、启用抖店、已知店铺身份、完整历史日和经营边界仍受检查。
数据库 Session 必须 VALID、版本匹配，采集晚于原失败，采集/验证不在未来且验证不早于采集，验证仍在既有 freshness 窗口内。
已有完整事实（含真实0）、其他活动任务或更新的失败会拒绝；普通更新、普通重试和自动扫描的累计次数/冷却规则不变。

原失败记录保留不改。使用既有 PostgreSQL 全局领取事务锁和唯一 Job `dedupe_key=session-restored:{原ItemUUID}`
关联至一次新执行，授权重放返回原恢复 Job；多进程不会另建任务。仅有一次领取，失败、授权过期或租约超时/重启
均成为 non-retryable FAILED，不暂停、不再次 pending，也不能凭新 Session 版本重开一次。
生产具体店铺日期由 ca97/Main 按本轮授权单独执行，Feature 不扫描或操作生产。
