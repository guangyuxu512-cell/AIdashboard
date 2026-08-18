# Worker 边界

核心流程：
```text
启动
↓
注册
↓
Heartbeat
↓
等待/领取 Task
↓
选择 Executor
↓
执行 Skill
↓
上报进度
↓
结果回传
↓
继续等待
```

不直接访问 PostgreSQL。
不承载 Vue/Electron UI。
