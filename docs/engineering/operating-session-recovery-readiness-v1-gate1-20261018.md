# 经营会话恢复就绪规则统一 Gate 1

## 基线、资源与边界

- Owner 81a1，分支 `hotfix/operating-session-recovery-readiness-v1`，精确起点为 Green
  `34958a7ddf01ae050cc7e694820313236b645000`。最终 Candidate 以正式 Handoff 的完整 SHA 为准。
- ca97 批准沿用 Feature PostgreSQL `control_center_feat_product_selection` / 最小角色
  `control_center_dev_user` / `127.0.0.1:35433`，单一 Head 固定为 `20261015_0046`。本轮无 DDL、
  Migration 或 Slot，不升级/降级/清理数据库，不运行依赖 0047 的测试。
- 四个经营/选品自动及执行开关由 PG fixture 在连接前读取实际 Settings 并断言为 false。
  只有被动的正式 ASGI/Service/Repository/Executor 与合成外部适配器；无生产/平台请求、无 Electron、
  无新端口、无安装包、无配置变更。

## 问题与统一契约

生产形态样本的原 DAILY Item 于 `2026-10-18T01:01:36.620918Z` 失败，当前 Session v2
的服务器验证时间为 `2026-10-18T03:51:31.267851Z`，Electron 捕获时间为
`2026-10-18T03:51:40.822Z`。原经营恢复守卫把两台机器的时钟做严格先后授权条件，因
`validated_at < captured_at` 在入队前永久拒绝；公共 `collection_readiness` 已能正确将它分类为
`AUTHORITATIVE_VALIDATION_REQUIRED`，但原恢复入口没有复用该决策。

本轮固定以下最小契约：

1. `validated_at` 和原失败时间均由 Backend 写入；只有当前精确 Session 版本存在
   `validated_at > failed_at` 的服务器证据时，才可展示显式恢复入口。缺失、非 aware 或未晚于
   失败的验证仍拒绝。
2. `captured_at` 是客户端观测元数据，不再与服务器时间做授权排序，不设任意秒数容差，
   也不改写原时间。
3. 共享 `classify_collection_readiness` 统一判定当前 Session 是可直接使用还是需要权威复核。
   缺失/陈旧/未来/跨时钟乱序不直接 READY；只有用户显式提交
   `revalidate_current_session=true` 时可排入原单次队列，执行器仍先调用 HealthService 核对店铺身份。
4. 普通“更新数据”不绕过冷却、累计次数或终态保护，仍不新建 Job/Item、不调平台；
   安全文案引导到“查看缺失”的单项复核，不再只显示泛化冷却提示。
5. DAILY/FAILED/retryable/失败码与阶段、完整历史日、店铺启用、身份、团队权限、版本、
   原 Item 最新性、无成功事实、无活动项、单次去重、租约及迟到结果拒绝全部保持。

## 实现与契约覆盖

- `CollectionReadinessMetadata` 为无凭据、无载荷的最小 Protocol，让经营 Repository 的有界元数据投影复用公共就绪分类；没有构造第二套判定表。
- 经营恢复守卫仅用同服务器时钟确认“验证晚于失败”，是否需要执行前权威复核由公共分类器返回。
- 原 `OperatingSessionRecoveryRead` 和原 retry Body 不扩字段。PC 的原始恢复 DTO 改为具名接口并纳入 Verify；内存客户端探针以独立期望检查单项 retry 路径、Item、版本和权威复核开关。
- 前端仍只显示后端的 typed 投影和安全文案；普通更新不会自动转换为恢复 Mutation。

## Gate 1 证据与未执行边界

| 检查 | 结果 |
| --- | --- |
| 修前精确回归 | 6 FAIL：2 个跨时钟样本被原守卫拒绝、3 个缺少服务器后验证证据样本与新期望不同、1 个普通更新文案仍为泛化冷却。 |
| 后端 Session/Health/经营定向 | 最终 155 PASS；无 PostgreSQL/平台网络。实现前先跑的 6 项精确回归按期失败，实现后纳入该集合通过。 |
| 经营前端 typed API/Query/UI | 20 PASS；普通更新安全引导不会自动调 retry。 |
| Feature PostgreSQL 0046 | 9 PASS；包含上述精确 9.554149 秒跨时钟形态。普通更新零新 Job/Item/外部调用；显式复核后正式 Executor 仅执行 1 次合成身份检查和 1 次合成指标请求，写入 0 金额/0 订单/3 退款；原 failed/attempt_count=3 保留。 |
| `pnpm verify` | Node 24.19 / pnpm 11.25 下 exit 0；12 Enum / 5 mapping / 16 DTO / 4 enum binding，28 known / 0 new / 0 stale；前端契约探针 9 PASS。 |
| `pnpm verify --strict` | 预期 exit 1；仅原 28 failures，0 stale，无新签名。 |
| `pnpm verify --full --only=backend` | exit 0；Backend 1048 PASS / 442 按离线 profile 明确 deselected，仅既有 Starlette/httpx warning；28 known / 0 new / 0 stale。 |
| 前端静态与 Real build | lint、typecheck、Prettier 及 Real production build 通过，构建 15.82 秒；保留既有大 chunk warning。 |
| Python/差异 | 改动 Python `compileall` 、`git diff --check` 通过。 |

本轮不对生产原 Item 入队或补采，不变更生产 Session、开关或配置。Feature PG 只写入 fixture 的稳定 UUID 范围，每项清理并校验原 users/teams/shops 聚合哈希不变。

安全本机证据均在 ignored `.codex/`，不含 Cookie、Token、签名、连接串或原始平台响应：

- `operating-session-recovery-readiness-v1-20261018/cross-clock-feature-pg-proof.json` SHA256
  `53cce564ee219ac94dfaf2c794dd4f73ea709f8ce2845ad751f18eb32afba74f`。
- `operating-session-recovery-readiness-verify-node24-final.json` SHA256
  `ca948408102b3bc8e7f2dd0cc843f9dc32550ea8601975c9af96e42867571bb6`。
- `operating-session-recovery-readiness-verify-strict.json` SHA256
  `7bdf30de1e8166e47559ba2b18be86e169ac148eddfa87f0ef241f6cb52ea1be`。
- `operating-session-recovery-readiness-verify-full-backend.json` SHA256
  `ba03778be58990f10598697b4346772579ca42d03fd2b2b8d9f3c3abcb128a37`。

首次快速 Verify 误用 shell 默认 Node 20，pnpm 11 因缺少 `node:sqlite` 而无法启动 PC 探针，导致报告受阻且原 4 条运行例外显示 stale；它不是产品失败。随后使用已登记的 Node 24.19 / pnpm 11.25 原样重跑，得到上表最终结果，没有修改依赖或项目 pin。

ca97 接收精确 Candidate 后执行独立 Gate 2、精确 Green CI 及后续 Release。Owner 不合并 dev/main、不部署；生产定向恢复仍需按发布后新版本和原授权范围由指定责任人执行。
