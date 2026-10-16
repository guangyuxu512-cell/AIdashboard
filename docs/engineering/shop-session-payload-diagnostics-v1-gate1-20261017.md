# ShopSession 刷新拒绝安全诊断 Gate 1

2026-10-17，81a1 → ca97。只增加后端有限诊断，不宣称 MyCookLab 历史拒绝根因已解决。

## 授权与精确基线

已直接回读规划人类 turn `01a145b7-e9d3-73e2-8400-ab1f43dd8dfd` 的“确认”及紧邻完整批准范围：
最小后端诊断经 Gate/CI/Main 发布，正规排除未获本轮发布批准的 cleanup，健康后仅 MyCookLab 一次正常登录取证。
分支 `feat/shop-session-payload-diagnostics-v1` 从已发布精确 Green
`1773a97d27c56512a620337e3259cceabadca2f1` 正常创建；其应用树与生产
`21229eff5ddf9900b8f38b13c89382952f90ee7b` 一致。新精确 Candidate 以正式 Handoff 为准。
冻结原 `98c1330d8a7f518b18c9f7de40928f31090575ec` 及其 UI/1.0.7/材料，不合入新候选。

ca97 已明确登记本轮纯源码及合成验证，无数据库、端口、服务、Migration Slot、依赖或安装包需求。
不借旧 Feature 43 库，不读取 Profile/平台凭据，不动共享 stash 或当前 Integration Runtime。

## 修改与兼容边界

八个批准路径为：sessions 的 `refresh_service.py`、`health_service.py`、`api.py`；对应原
refresh/health 测试与新 `test_shop_session_refresh_diagnostics.py`；backend/docs/10 与 19。
另仅有本 Gate 1 记录。运行修改只在三处 sessions 文件，不改全局 handler/logger、公共异常类、原
`check`、Accessor、平台 HTTP/Signer、权限、Schema/Migration、Frontend、Electron 或依赖。

七固定阶段在原拒绝点产生；验证只细分 context/identity Connector/Cookie merge 三个调用边界。
进入 Connector 不保证 HTTP 已出站。schema 仅产生最多三条固定字段类别与错误类型，丢弃数组下标、
实际名称、值和任意异常文本；未知/截断仍明确未知。API 再投影一次安全 details，并通过原模块 logger
输出 WARNING JSON，不反射不合法 request ID；响应状态、错误码与原消息保持。完整白名单见原两份契约。

旧 1.0.6 refresh 命令、租约/版本/目标/权限检查及业务行为不变，不需要 1.0.7 或新包。
成功及非该码不输出新诊断。失败保留旧 Session，原 finally 释放租约；正常成功仍运行原
`collection_resume`，不伪称一次正常登录只写 Session。

## 验证

Owner 使用四个 Backend 文件的 Fake/合成测试覆盖七阶段、固定子步骤、schema 上限/未知/秘密标记、
旧 Session/CAS/lease 和权限复核。新 API 测试使用实际 FastAPI 路由、异常处理、ASGITransport 与实际
WARNING StreamHandler；依赖明确替换为 Fake，数据库依赖设置拒绝哨兵，无 app lifespan、监听端口、
数据库连接或平台请求。另回归原 request logger、Release P0 权限与 Session service。

本候选实际执行命令：

- Backend `.venv/Scripts/python.exe -X utf8 -m pytest tests/test_shop_session_refresh_service.py tests/test_shop_session_auth_context.py tests/test_shop_session_health_service.py tests/test_shop_session_refresh_diagnostics.py tests/test_request_logging.py tests/test_release_p0_api_security.py tests/test_session_service.py`：七文件104项PASS，最终10.09s。
- `python -X utf8 -m compileall -q` 限定三运行与三测试文件：PASS。
- AST 对照1773：原 `check` / `apply_response_cookie_updates`、refresh `acquire/release/complete`、保存/恢复/返回尾部均不变；`git diff --check` PASS。

实际 WARNING 流中，合成请求 `c812a4de-821d-4b08-a5be-10a858c83786` 返回原 HTTP500/原码/原消息，
domain/access/响应 UUID 一致；schema 日志仅有 schema 缺失、platform 枚举、cookies.name 最小长度三项，
`schema_issues_truncated=true`，输入秘密标记不在响应或日志。首控制台输出中文编码显示受本机终端影响，
响应消息相等断言已通过，随后 UTF-8 proof 也确认原消息“店铺 Session 无法安全读取”，不改业务响应。

本轮不执行未变前端/Electron 构建或安装验收、不跑 PG/迁移、不重复 HuanYu 登录；测试不能代替生产日志取证。

## 集成发布与恢复

ca97 负责独立 Gate 2，并在已授权 dev 正规 `revert -m 1`
`5131c61b38925cc3bf38f5cc02359aee2e1ebcf7` 排除 cleanup 后，正常 `--no-ff` 集成诊断，
复验合并树及精确 dev CI。保留 cleanup 原分支/提交/历史，不改写历史；Feature 不直接进入 main。
Main Release Gate 必须核对相对生产 21229 的运行净差异只有本诊断，无 cleanup 四路径、98 UI、
Electron、Schema 或配置变化。标准部署会重建三个服务；Frontend/Signer 源码和配置不变。
既有 Alembic upgrade 预期在单一 `20261015_0046` 无操作，不降级、不新增迁移。

健康后 ca97/Main 才按批准范围做 MyCookLab 一次正常登录。点击前重新核对精确 SHA、Session 版本/lease，
以及 paused/pending/running、边界前未执行、昨日 pending 等既有恢复副作用组均为 0；有变化即停回报。
成功可能正常保存新版本并走原 skip/resume/defer/Job 更新；不得删历史失败或手写业务事实。
失败不重试，只按 Request ID 取安全诊断；未复现或子阶段不明时保留历史根因 UNKNOWN。

回滚按正规镜像回滚或 revert 至 21229 应用代码，保留单一0046、Profile、业务历史和已经正常保存的新 Session。
不回写旧 Session、不清库、不降级。Owner 只交 Candidate 和证据，不合 dev/main、不部署或操作生产登录。
