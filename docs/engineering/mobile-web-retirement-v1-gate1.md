# 手机网页前端清理候选

- 基线：Green dev `83e459a8ea5c4e1c9b7f646492cd9a7e72bfa3ef`；无数据库和 Migration 变更。
- 范围：删除独立 `mobile/` 手机网页及其构建、发布和校验引用；旧 `/mobile` 网页入口返回 404。桌面安装包图标保留原字节并移至 `electron/assets/`。
- 保留手机采集 `/internal/mobile-collection/v1/`、后端、Worker、NAS 与手机采集程序。没有修改这些业务代码。
- 本地检查：PC 前端 lint、typecheck、986 项测试与 Real 构建通过；Electron typecheck、108 项测试通过；契约快速校验在补齐既有 Worker 枚举来源后通过；本地发布入口模拟与 CI YAML 检查通过。
- 尚未执行容器镜像、真实 Nginx／手机采集代理回归：本机无 Docker。候选尚未经过独立 Gate 2、远端 CI 或部署，不表示生产已移除手机网页。
- 回滚：在未发布前放弃此 Feature；如已合并，按既有流程 revert 对应合并提交。不要改手机采集和 Worker 数据。
