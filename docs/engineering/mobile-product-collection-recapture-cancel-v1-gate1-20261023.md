# 手机商品采集显式重采取消语义返修

## 候选范围与根因

Owner 为 81a1，下一责任人为 ca97 独立 Gate 2。原分支
`feat/mobile-product-collection-integration-v1` 从精确父提交
`2c0a9d6d20bf2bab112b9daa7821f2eb614f18d1` 正常追加；完整 Candidate 及远端核验结果以正式 Handoff 为准。

ca97 最新真实失败停在中控内部、尚未投递网关：人员显式重采创建新 Dispatch 后，取消消费者仍读取
Request 上旧的 `cancel_requested_at`，把新派发立即取消。该次 `delivery_attempts=0`，无 Gateway Job；
不是手机/NAS失效或此前的网关认证失败。复现和本次修复不触发真实设备任务。

只修改两个运行路径：

- `human_service.py`：显式重采在原事务中锁定 Request 后读取数据库 `clock_timestamp()`，将其作为
  新 Dispatch 的创建/更新时间。事务起始时间可能早于等待锁期间已提交的取消，不能作为新代次时间。
- `dispatch_service.py`：取消扫描只领取创建时间不晚于取消时间的当前 Dispatch。Request 的取消人和
  时间审计不清空，其他旧 Item 继续受原取消约束；新取消仍能作用于新重采。

未改变 API/DTO、权限、有限重试预算、媒体规则、网关协议、清洗器、UI、配置或 Schema。
原 current-dispatch/Gateway-job 迟到保护不变，普通 retry 继续复用旧 Dispatch，不获得显式重采豁免。

## 本轮实际验证

| 检查 | 结果及范围 |
|---|---|
| 修前隔离 PostgreSQL | 3 FAIL / 2 PASS：旧取消误伤新重采、事务起始时间不具备代次排序含义均已复现 |
| 修后最终隔离 PostgreSQL | 9 PASS，48.511s，0 skip；覆盖旧取消隔离、新取消、同请求旧 Item、成员权限、重复重采、事务回滚及跨连接行锁 |
| 两份保留真实 V2 包 | 均经正式 attempt 注册 HTTP 201、ingest HTTP 202/Receipt、既有真实 cleaner、PG Persist Receipt/Version/Product、结算 outbox；每份 7 SKU / 12 主图 / 18 详情图 |
| 同包重放 | HTTP 202 duplicate，Receipt 不变，未重复处理或新增版本；原包字节/hash和源字段保持不变 |
| Product Collection 非 PG 回归 | 隔离 launcher，160 PASS，5.75s；不加载本机 `.env` 或启动后台消费者 |
| strict Verify | `pnpm verify --strict --report=.codex/product-collection-recapture-cancel-20261023/verify-strict.json`，exit 0，23.29s；known/new/stale 全 0，10 Node / 2 AST / 9 Frontend 契约通过 |
| 编译与 whitespace | 两个运行路径及新增 PG 测试 `compileall -q`、`git diff --check` 均 PASS |

最终 PG 命令为：

```text
backend/.venv/Scripts/python.exe -m pytest tests/integration/test_postgresql_collection_recapture_cancel.py -o addopts= -q --tb=short -o junit_family=legacy --junitxml=../.codex/product-collection-recapture-cancel-20261023/pg.xml
```

运行时用两个受保护环境变量指定本机保留包目录和既有 cleaner 模块，不提交原始包。Node 使用现有
24.22.1、pnpm 11.25.0；项目依赖和 package-manager pin 未变。仅有既有 Starlette/httpx 弃用 warning。
父候选的完整 Backend 1241 项和完整 strict Verify 只属历史证据，本轮没有将其记为新执行。

真实包用例第一次有 2 项测试断言失败：原文件 hash 与模型补默认值后的规范化 hash 被混用。
已分别核对文件 hash、规范化 hash 和原始 detail/sku/hash 字段；未改包、运行解析器或接受规则。
最终 JUnit 的安全属性记录两次 Register/Ingest HTTP 状态、Receipt/Version/Product ID、数量和结算状态。

## 隔离与数据保留

本轮只连接 ca97 已分配的 Feature DB `control_center_feat_mobile_product_collection_integration`，角色
`control_center_dev_user`，精确 Head `20261020_0049`。三消费者实际配置始终 false；测试应用不执行
lifespan。服务提交只释放测试外层事务的 savepoint，结束整体 rollback，外部消费者看不到活动夹具。

跨连接锁测试单独提交的仅为随机身份的终态夹具；新重采始终不提交到外部连接。第二连接对重采及取消
均得到预期 PostgreSQL 55P03，观察连接只能读到原终态。结束仅删除这些精确随机身份，未扫描清理业务队列。
测试前后九张 Product Collection/Product Library 表的数量及整表摘要完全一致，既有两条 Request/Item/
Dispatch、三条 Attempt 保留；活动 Dispatch/Pending Item 均为 0。

安全证据位于被忽略的 `.codex/product-collection-recapture-cancel-20261023/`（`pg.xml`、`unit.xml`、
`verify-strict.json`），前后只读摘要在 `.codex/mobile-media-budget-20261021/pg-recapture-{before,after}.json`。
不在文档、日志或 Git 保存原包、Token、签名及完整媒体 URL。

## 交回 ca97

ca97 在人工已批准的本次最小返修范围内接收精确新 Candidate，再独立 Gate 2。Real UI 继续固定
`a28bbe8d07163c52fbcb8d05f4fe65d076bd1646`，接口依赖不变，需与新 Backend 组合验收。
手机/NAS 侧按最新冻结版本固定 Collector 0.4.12、Automation 0.3.14、Candidate
`31fe93fa2c35af0e540cd515b5f09e8ad94a73a0`，不要求其规避中控问题或改包。

Migration 0049 不改写、不新增、不升降级；Feature 既有应用保留。Integration 的已应用 Head0049
来自 ca97 已有核查，本 Owner 本轮没有连接 Integration/生产库。用户独立维护的 `AGENTS.md` 和
`docs/engineering/history/` 完整保留，不纳入提交。

两份真实包经过的是正式 ASGI 接口、真实 PostgreSQL 和真实 cleaner；Gateway 投递/状态回调接收端为
合成替身，不是新手机实测。整体 Gate 2 和最后一次真实单机单商品闭环仍待 ca97，不把本轮隔离成功写成
实机闭环成功。未操作手机/NAS、Electron、平台、运行开关或生产，也未合并 dev/main、执行 CI 或部署。

回退使用正常 revert 本次新增代码/测试/文档，保留所有历史取消、派发、失败与 Receipt，不删除业务数据。
