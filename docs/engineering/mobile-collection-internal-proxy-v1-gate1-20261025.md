# 手机商品采集内部路由代理修复

## 范围与基线

Owner 为 81a1，下一责任人为 ca97。本分支 `hotfix/mobile-collection-internal-proxy-v1` 从精确 Green
`df55852c8f1ea15989dbb30025d6c034942ef1e5` 创建；已独立核对该 SHA 的
[CI 39939167945](https://github.com/guangyuxu512-cell/AIdashboard/actions/runs/39939167945) 为 success。
原手机采集分支、提交及用户未提交的 `AGENTS.md`、`docs/engineering/history/` 保留。

本次仅修复 Frontend Nginx 未转发内部手机路由、导致请求命中 SPA 的问题。没有业务代码、依赖、
Migration、配置值、手机/APK、NAS 或其他代理规则变化，不重复采集或执行生产任务。

## 修改文件

- `frontend/deploy/default.conf.template`：增加 `location ^~ /internal/mobile-collection/v1/`。
  `proxy_pass` 与原 `/api/` 一致且不带 URI 后缀，保留完整路径、原编码和查询参数；HTTP 版本及
  Host/Real-IP/Forwarded headers 与原 API 代理一致。没有新增鉴权豁免、重写或凭据注入，Authorization
  继续按原代理机制透传，最终认证由 Backend 负责。未修改主机 Nginx 模板或其他 location。
- `scripts/test-asset-upload-proxy.sh`：复用现有生产 Nginx 传输夹具及现有 container-runtime CI 入口。
  增加注册/续发两条路径的 JSON、完整 URI/查询/请求体及缺失/错误/合成凭据回归；检查相邻 v2 和
  非手机内部路径仍返回前端文档，不扩大为整个 `/internal/` 的转发。原资产上传检查保留。
- 本 Gate 1 记录。

## 实际验证

| 检查 | 结果 |
|---|---|
| 修前同一生产模板 | 注册 POST 返回 405、`text/html`，定向断言失败；与已报告阻塞一致 |
| 修后本地真实 Nginx | 16 项传输检查 PASS：直连 Frontend 及主机 TLS→Frontend 两条路径，各覆盖两端点×三鉴权状态、两项范围外路径 |
| 提交脚本中的新增 Bash 回归段 | 在上述两条真实 Nginx 路径均 PASS；使用脚本原 receiver 和原断言，非另一套近似 fixture |
| Shell 语法 | `bash -n scripts/test-asset-upload-proxy.sh` PASS |
| 部署工作流静态契约 | `bash scripts/test-production-deploy-workflow.sh` PASS |
| 既有部署运行回归 | `bash scripts/test-remote-deploy-production.sh` 的前置 active-release 19 项 PASS；随后缺少 `sudo`，exit 127，整项未完成，不计全绿 |
| Whitespace | `git diff --check` PASS |

本地运行命令为 `backend/.venv/Scripts/python.exe .codex/mobile-collection-internal-proxy-20261025/probe.py
after`。探针只读取两个现有模板和提交脚本的原 receiver/新增回归段；使用随机 loopback 端口及临时
自签名测试证书，HTTPS 客户端显式信任该证书而非跳过校验。原始完整 path（含 `%2F` 查询）、JSON body
和合成 Authorization 到达传输接收器；缺失/错误凭据得到 401 JSON，合成正确凭据得到 200 JSON。
这只验证代理透传与不吞 Backend 状态，不把夹具的认证规则冒称正式业务认证验收。

运行时为官方 Windows Nginx 1.27.5，与项目既有镜像同属 1.27 系列；未修改镜像或项目依赖。
[官方发行包](https://nginx.org/download/nginx-1.27.5.zip) SHA-256 为
`7ca07528f52c02df33735fedbb9cf822d38079f26c3d9f2774ed512af4fdafd4`。本机没有 Docker，Linux
生产镜像的完整 `test-asset-upload-proxy.sh`（含原上传回归）尚未运行，需由 ca97/精确 CI 核验。
本地探针初次准备遇到 Windows 短路径及临时目录问题，仅调整 ignored helper 的路径和清理顺序，
不作为线上根因。最终修前/修后记录在 ignored `.codex/mobile-collection-internal-proxy-20261025/`
的 `before.json`、`after.json`，所有自建进程结束后关闭，未占用共享端口。

Renderer、Backend 业务和数据库均未修改；未重跑无关页面、平台或数据库套件，也不把基线 CI 写成
本轮新验证。没有读取真实 Token、ShopSession、原始商品包或生产配置。

## 交接与未覆盖项

精确 Candidate 及远端核对以正式 Handoff 为准。ca97 独立 Gate 2 后，按原流程正常 no-ff 合入 dev，
检查同一 SHA 的 GitHub CI，再交 Main 发布。本 Owner 不合 dev/main、不部署、不连接生产/NAS、
不启用消费者或创建采集任务。

生产真实路由及认证状态尚未由本候选验收；路由发布后，Main 仍需确认返回 Backend JSON、认证
fail-closed，再按人类既有授权衔接 NAS 地址、设备在线和持久化消费者启用。不得用本地夹具成功宣称
生产采集已启用或生产闭环已通过。回滚仅正常 revert 该新增 location 及测试，无数据迁移或清理。
