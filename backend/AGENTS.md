# backend/AGENTS.md

## 1. 定位
Backend 是服务器业务核心。

固定：
- Python
- FastAPI
- Pydantic
- SQLAlchemy 2
- Alembic
- PostgreSQL
- HTTPX
- pytest

Redis / MinIO 按需求引入。

## 2. 文档路由
先读 `backend/docs/00-文档索引.md`。

| 任务 | 必读 |
|---|---|
| 新模块 | 01 + 02 + 03 |
| 数据库/表/字段 | 04 |
| API | 05 |
| Credential/Session/权限 | 06 + 10 |
| Task/Worker 通信 | 07 |
| 测试/验证 | 08 |
| 跨模块重构 | 01 + 02 + 03 + 08 |

## 3. 模块化单体
推荐：
```text
app/
├── core/
├── modules/
│   ├── auth/
│   ├── users/
│   ├── permissions/
│   ├── shops/
│   ├── credentials/
│   ├── sessions/
│   ├── devices/
│   ├── tasks/
│   ├── skills/
│   ├── workflows/
│   ├── audit/
│   ├── data_center/
│   └── ai_analysis/
└── shared/
```

禁止一开始拆十几个微服务。

## 4. 禁止猜想
禁止自行猜测 DB 列、API 字段、平台字段、Session 格式、状态枚举、错误码、权限码、Task 状态机。
先查 Model / Schema / Contract / DOCS。

## 5. 必须抽象
优先抽象：
- Platform Connector
- Repository
- Service
- Credential/Session Provider
- Task Dispatcher Interface
- Storage Adapter
- AI Provider

同类外部平台请求禁止散落各业务函数。

## 6. 第三方库
已有稳定库能解决的问题禁止手写替代：
- ORM → SQLAlchemy
- Migration → Alembic
- Schema → Pydantic
- HTTP → HTTPX
- API → FastAPI
- Test → pytest

禁止自制 Migration/ORM/HTTP Client 框架。

## 7. 数据库
PostgreSQL 是业务事实来源。
所有 Schema 变化必须 Migration。
RPA/Worker 不直接访问数据库。

## 8. API
API 层保持薄。
业务逻辑进入 Service。
DB 访问进入 Repository 或明确的数据访问层。
禁止 API handler 内堆数百行业务逻辑。

## 9. Credential / Session
- 敏感数据加密存储。
- 普通员工不可查看完整密码/Cookie。
- Worker 按 Task 授权获取必要凭证。
- Session 更新必须版本化/审计。
- 不允许设备批量下载全部凭证。

## 10. AI
AI 是可选分析模块。
确定性计算先由程序完成。
AI 不直接修改核心业务事实。
