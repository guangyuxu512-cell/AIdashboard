# Backend 契约使用规范

## 1. 权威来源

Mobile 不自行定义 Backend 事实。实现 Entity API/DataSource 前必须依次检查：

1. `backend/app/modules/<domain>/api.py` 的方法与 URL。
2. `backend/app/modules/<domain>/schemas.py` 的 Pydantic DTO。
3. 对应 `enums.py`、`exceptions.py`、Service 与测试。
4. `backend/docs/05-API与数据契约.md` 及运行时 OpenAPI。
5. PC Frontend 已有 Mapper 只能帮助理解，不能覆盖 Backend Contract。

Backend Pydantic/OpenAPI 始终是最终权威。Contract 不存在时停止实现并报告 Contract Gap。

## 2. 已确认的通用契约

- 业务 API 前缀：`/api/v1`。
- 分页查询：`page` 默认 `1`、最小 `1`；`page_size` 默认 `20`、范围 `1..100`。
- 分页响应字段：`items`、`total`、`page`、`page_size`。
- 统一错误字段：`code`、`message`、`request_id`，以及可选的 `details`（对象、数组或 `null`）。
- 请求校验错误为 HTTP `422` / `VALIDATION_ERROR`。
- 数据库异常统一为 HTTP `500` / `DATABASE_OPERATION_FAILED`。
- 响应使用 `X-Request-ID` 关联请求；`GET /health` 不属于业务 API。

`src/shared/api/` 只固化以上通用边界。领域 DTO 必须在首个真实 Mobile 用例出现后，按对应 Backend Schema 建立；本轮不提前复制整份 OpenAPI。

## 3. 已存在的领域 API

以下只记录 Backend Auditor 已核对的真实范围，不代表 Mobile 当前已经接入或拥有使用权限。

| Domain   | 真实 API 范围                                                  | 主要状态/语义                                                                                       |
| -------- | -------------------------------------------------------------- | --------------------------------------------------------------------------------------------------- |
| User     | `/api/v1/users` 的列表、详情、创建、更新                       | `enabled`；不存在登录名、密码、角色、权限或 Token DTO                                               |
| Shop     | `/api/v1/shops` 的列表、详情、创建、更新、软移除及设备绑定     | `platform = douyin \| pdd`；Session 状态为 `not_configured/captured/valid/invalid/refresh_required` |
| Device   | `/api/v1/devices` 的列表、详情、创建、更新、软移除及能力查询   | Runtime 连接状态为 `online/offline`；Worker Credential 管理属于敏感能力                             |
| Task     | `/api/v1/tasks` 的列表、详情、事件、活动任务与创建             | `pending/running/success/failed/lost`；不存在 cancel/retry API                                      |
| Schedule | `/api/v1/schedules` 的列表、详情、运行记录、创建、更新、软删除 | 当前仅 `daily`；触发结果为 `task_created/blocked`                                                   |

具体字段、查询参数和错误码必须回到各 Domain 的 Router、Schema、Enum、Exception 与测试核对，禁止仅凭本表实现。

## 4. DTO 与调用边界

推荐链路：

```text
Backend DTO
    ↓
Entity API / DataSource
    ↓（结构复杂时使用 Mapper）
Mobile Entity Model
    ↓
Feature / Page
```

- Backend Raw DTO 不应无边界扩散到所有 Page。
- Contract 足够简单时无需为了形式强建 Mapper。
- Page 禁止直接导入 Axios、共享 API Client 或拼接 `/api/v1/...`。
- Task 输入必须遵守正式 Business Skill Schema；Mobile 不得把 `input` 当作任意 JSON 构造。
- Backend 的状态合法性、设备可执行性和计划启用规则不得在 Mobile 复制实现。

## 5. Auth、Permission 与 Data Scope Gap

当前 Backend 尚未实现员工登录、JWT 签发/刷新、RBAC、正式 Permission Code 或 Data Scope；现有 User 只是业务人员实体，不是登录身份 Contract。

因此本轮：

- 不调用真实业务 API。
- 不创建登录 URL、Token DTO、Current User DTO 或权限码全集。
- API Client 只保留 Authorization Header 与 HTTP `401` 处理 Hook，默认不注入任何 Header。
- Router 只保留 `requiresAuth` 与 `permission` Meta 及 Guard 注入点。
- 未来员工只能查看部分店铺时，必须由 Backend 在 API/Query 边界过滤；禁止 Mobile 拉取全量后本地过滤。
- Worker Bearer Token 是 Device Identity，Mobile User Authentication 不得复用 Worker Token。

生产 Mobile 直连 Backend 前，员工身份、401/403、Token 生命周期、权限码和各领域 Data Scope 必须先形成正式 Backend Contract 与测试。
