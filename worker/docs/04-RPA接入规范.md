# RPA 接入规范

RPA 是 Skill 的一种实现方式。
RPA 不需要知道中控台完整架构。

必须支持：
- 外部启动
- 外部输入
- 明确完成
- 明确失败
- 超时退出
- 结果输出
- 日志输出

推荐运行目录：
```text
runtime/<task_id>/
├── input.json
├── output.json
├── run.log
└── artifacts/
```

若影刀已有正式参数/API 调用能力，可直接使用，但仍保持统一 Skill Contract。

禁止：
- RPA 自己轮询服务器。
- RPA 直接 PostgreSQL。
- RPA 把账号密码硬编码。
- 错误后无状态退出。
- 无限等待人工输入。

浏览器 Profile 可本地长期持久化。
Credential 由服务器统一管理，只有需要登录/恢复 Session 时按任务授权使用。
