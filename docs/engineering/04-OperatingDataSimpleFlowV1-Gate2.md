# Operating Data Simple Flow V1 — Gate 2 / Release Gate

## 精确范围

- Candidate：`c94af8fcc6059c449300d3820c31a258fc8e787a`，分支 `feat/operating-data-simple-flow-v1`。
- Green 基线：`2e56dfe8a3a58122690193c359656afd411e1132`。
- Integration 正常 no-ff merge：`8ad7d4bcb0c7991fddc8d17bd4ae2eaea0698e51`。
- 旧 `56fc49ed4e0e2eb102ecbd1940ff28af39c6ee6e` 不在本次集成提交祖先中，不集成、不发布。
- 本轮没有 Migration、事实表/指标解析器、权限、Signer 算法、海洋历史覆盖口径或视觉 Token 改动；Head 保持单一 `20260924_0041`。

## Gate 2A：ACCEPT

复核 81a1 Gate 1 Handoff 和整个候选差异。新店接入/启用不自动创建历史补采，重新授权仅恢复原有暂停项；首次日期范围由看板手动选择；每日稳定 dedupe key 仅处理昨日。昨日的手动请求在配置边界前等待，入队/领取/请求平台前使用同一边界。显式重采只恢复明确的 response_parse 失败，共用冷却、连续失败次数上限与去重，不放开未知指标、风控或任意平台拒绝。API → Service → Repository 层级保持。

## Gate 2B：PASS

以下自动化在实际 Integration 合并代码上执行，而非仅复用 Feature 报告：

| 验证 | 结果 |
| --- | --- |
| Backend 普通完整 pytest | 502 项通过，76 项 integration 被默认配置排除 |
| PostgreSQL 经营看板集成 | 25 项通过，真实 `control_center_integration` |
| Frontend lint / typecheck / unit / Real production build | 通过，506 项单测 |
| Electron build | 通过 |
| Migration / Git | 单一 0041，无迁移文件差异，diff --check 通过 |

受控 PostgreSQL 时钟覆盖 08:59/09:00、每日仅昨日、重复/并发扫描去重，不修改电脑时间或生产配置。重新启用无历史规划、重新授权 resume-only、显式解析失败恢复、冷却与跨 Job 累计上限均覆盖。

专用固定标识夹具与旧自动测试数据隔离，退款观察状态完整且没有活动任务：

- `G2-SimpleFlow 首次与覆盖（模拟）`：2026-09-21～09-22，模拟上游、正式持久化路径。
- `G2-SimpleFlow 完整七日（模拟）`：2026-09-16～09-22，7/7，¥70.00 / 14 单 / 7 退款单。普通更新提示“所选范围数据已齐全，无需补采。”；后台配套证明零新 Job、零新 Item、零 collector / 平台请求。
- `G2-SimpleFlow 解析恢复（模拟）`：2026-09-22。普通更新阻断，显式恢复新建一个 Job/Item，重复请求复用；正式执行器调用模拟 collector 一次后成功，旧失败历史保留，活动项为零。模拟结果不冒充真实平台证据。

同一候选的真实 Integration 样本：HuanYu 2026-09-22，通过既有合法 Integration Session 和隔离本地 Signer 正式重采。Job `bab91b7c-46ba-4ff2-8947-453fea8a72c3` 成功；一次签名、两次平台 HTTP（身份核验及经营查询），入库与正式查询为 ¥659.05 / 60 单 / 8 退款单，覆盖 1/1；后续普通更新零新增工作。未复制生产 Cookie。

Integration 运行以精确 Job 的正式执行器完成，不启动全局消费者处理旧夹具队列；日计划验证使用受控 PostgreSQL 时钟，不能把该运行方式当作生产定时器观察。

2026-10-03 用户在唯一开发 Electron 正常登录后明确反馈“通过”，记录为本轮新增交互人工验收确认。环境为 Real `5180 → 8100 → control_center_integration`；浏览器准备证据与真实 Electron 人工确认分开记录。人工确认后没有业务代码改动。

## Release Gate 与回退边界

用户已授权本功能通过 Gate/精确 CI 后发布；不重复人工验收。本工程记录提交不改变已验收代码。推送 dev 后必须等待该精确 SHA 的全部 CI 成功，再由登记 Main 工作树正常 no-ff 合入 main。main CI 成功会自动触发唯一 Production Deploy，不重复手工部署。

main 推送前核对实际生产仍为 `bfe956c25bcd3ef0144d73782b839cda2efb2973`、0041、现有开关与活动队列、迁移前备份和恢复路径。没有新的 Migration，部署的 upgrade head 应为 no-op。保持每日 Asia/Shanghai 09:00、执行与每日开关；新代码不再扫描 30 日历史。首次新版本 09:00 执行须真实观察，不能提前宣称已发生。

回退可使用上一相同 0041 的兼容 release，但会恢复旧历史规划策略；回退前重新核对队列和备份配置。保留资产卷、历史事实、失败记录和生产 Session。发布完成与生产业务验收另行记录实际 SHA/工作流；当前本记录本身不代表 DEPLOYED。
