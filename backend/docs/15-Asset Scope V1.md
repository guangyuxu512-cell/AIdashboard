# Asset Scope V1

## 1. 素材归属（Asset Ownership）

Asset 是 Team Scoped Business Entity：

```text
team_id             所属团队，NOT NULL，FK → teams，RESTRICT
created_by_user_id  创建者，NULLABLE，FK → users，RESTRICT
```

两列语义不能合并。`team_id` 是数据范围边界；`created_by_user_id` 用于 SELF Scope。历史素材无法可靠
还原创作者，因此迁移只把它们回填到唯一“默认团队”，Creator 保持 NULL，绝不伪造为管理员。

## 2. Human 创建与可信内部创建

Human Upload 的正式链路：

```text
Human Session → HumanPrincipal → ActorContext → AssetService.upload
                                              ↓
                 team_id = actor.team_id
                 created_by_user_id = actor.user_id
```

公开 DTO 不接受 Ownership 字段。即使用户拥有 ALL，创建仍属于当前 Active Team。

`AssetService.create` 是可信 Backend 内部入口，不依赖 FastAPI Request 或 UploadFile，但调用方必须
显式提供 `AssetOwnership(team_id, created_by_user_id)`。未来 AI Job 应把 Job 自身的 Ownership 原样
传入；该内部入口不能直接暴露为允许客户端提交 Team/User 的 HTTP API。

## 3. 数据范围（Data Scope）

AssetRepository 复用 Access Foundation 的 `DataScopePolicy`：

- SELF：`asset.team_id = actor.team_id AND asset.created_by_user_id = actor.user_id`
- TEAM：`asset.team_id = actor.team_id`
- ALL：不追加 Ownership 读取条件
- 未知 Scope：Fail Closed，抛出 `INVALID_DATA_SCOPE`

Scope 先于 Search、Count、Order 与 Pagination 应用，所以 `total` 只表示当前 Actor 真正可访问的
记录数。Creator 为 NULL 的历史/系统素材对 SELF 不可见，对同 Team 的 TEAM 可见，对 ALL 可见。

## 4. Human Asset 操作

当前真实操作及边界：

- List：Scoped Query → Search → Scoped Count → Order → Pagination。
- Content/Preview：同一次 SQL 使用 `asset_id + scope predicate`；越权 UUID 与不存在统一返回
  `ASSET_NOT_FOUND`。
- Delete：先执行带 Scope 的行锁查询，再执行既有 Task 引用保护和 Storage 删除规则。
- Reference Lookup：`list_accessible_by_ids` 在 SQL 中应用相同 Scope，供未来可信业务 Service 使用。
- Detail、Rename、Update：当前不存在，因此 V1 不新增虚构 API。

Content 不签发公开 URL，也不返回 `storage_key`。PC 通过统一 Axios Client 获取 Blob，确保多 Team
请求携带 HttpOnly Cookie 与 `X-Team-ID`；不能让普通 `<img src>` 绕过 Active Team Context。

## 5. Worker 边界

Worker 不是 Human ActorContext。既有执行链保持：

```text
Device Token + X-Device-ID
↓
RUNNING Task + target_device_id + task_assets
↓
Worker Task Asset Download
```

Worker 不需要 TeamMembership，也不重新判断 SELF/TEAM/ALL。Human/Task 合法性必须在管理平面创建
Task 前完成。当前 Task 尚未拥有 Ownership，Task 创建链的 Data Scope 属于后续独立阶段；本阶段只
保留既有 Task + Device 下载授权，不把它误写成 Human Asset 授权已经完成。本阶段不修改 Worker
Claim DTO、Download Path、SHA-256 或 Worker 版本。

## 6. 数据库与索引

Migration `20260901_0024_asset_scope_v1` 基于 `20260831_0023`：先添加可空列，唯一解析默认团队并
回填历史 `team_id`，验证无 NULL 后收紧为 NOT NULL；`created_by_user_id` 保持 NULLABLE。默认团队
不存在或不唯一时迁移直接失败，禁止取第一行或硬编码 UUID。

查询索引：

- `ix_assets_team_created_asset`：TEAM 列表与稳定时间排序。
- `ix_assets_team_creator_created_asset`：SELF 列表与稳定时间排序。
- 既有 `ix_assets_created_asset`：保留 ALL 列表排序。

## 7. AI Ready边界

未来 AI Image Job 可以保存自己的 `team_id / created_by_user_id`，生成成功后调用
`AssetService.create(..., ownership=AssetOwnership(...))`，无需新建第二套文件系统。Reference Asset
可使用现有 Scoped Lookup。V1 不实现 AI Job、AI Scope、Asset ACL、跨 Team 转移或 Task Scope。
