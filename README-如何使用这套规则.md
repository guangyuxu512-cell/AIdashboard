# 如何使用这套规则

推荐目录：

```text
project/
├── AGENTS.md
├── docs/
├── frontend/
│   ├── AGENTS.md
│   ├── docs/
│   └── src/
├── electron/
│   ├── AGENTS.md
│   ├── docs/
│   └── ...
├── backend/
│   ├── AGENTS.md
│   ├── docs/
│   └── app/
└── worker/
    ├── AGENTS.md
    ├── docs/
    └── app/
```

## 标准任务写法

前端示例：

> 新增设备中心第一版页面。按项目 AGENTS 分层阅读规则执行。只修改 frontend。必须先搜索现有组件和 Design Token。有可复用组件必须复用，不允许自创重复组件。API 暂时使用既有 Mock Contract，不允许猜测真实后端字段。完成后执行 lint/typecheck/build。

后端示例：

> 新增 Shop 与 Device 的绑定关系。按 AGENTS 阅读 backend 相关文档。先检查现有数据模型，不允许猜字段。使用 SQLAlchemy + Alembic Migration。现有关系能复用则不得创建第二套关系。不修改无关模块。

## 维护原则

- AGENTS：稳定硬约束和文档路由。
- DOCS：详细规范。
- 代码：实际实现。

不要把频繁变化的业务字段塞进根 AGENTS。
