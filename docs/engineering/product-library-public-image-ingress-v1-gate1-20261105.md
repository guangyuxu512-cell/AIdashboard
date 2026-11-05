# 商品库公网图片入口热修 Gate 1

## 候选与范围

- 基线：精确 Green `266be2dc8722e7ac691180ed0b2578e1f6bf9f37`，CI `41209988330` 四项成功。
- 分支：`hotfix/product-library-public-image-ingress-v1`。
- 工作树：`C:\Users\Administrator\.codex\worktrees\pdc-public-ingress\中控台`。
- 仅增加生产 host Nginx 精确 `/rpa/v1/product-images/` 路由、部署渲染、隔离传输回归与受影响文档。
- 私有上游是已核实的 ProductDataCenter Tailnet 地址 `http://100.91.242.119:3612`；公网规范地址是 `https://119.29.188.118/rpa/v1/product-images/...`。
- 无 Backend/Frontend 业务代码、Schema、Migration Slot、数据库、依赖、端口、Electron 或中控 Asset Storage 变化。

## 安全与契约

- 仅商品库自有图片前缀公开；`/rpa/v1/products`、`/rpa/v1/product-images-*` 和管理入口继续落到原 Frontend，不转发 NAS。
- NAS 图片仍在 ProductDataCenter 自己的持久目录；不复制到中控 Asset Storage。
- Host Nginx 只允许 GET/HEAD 下载，固定覆盖 `X-Forwarded-Proto: https`，保留客户端链路信息，清除进入 NAS 的 `Authorization`、`Cookie` 并丢弃图片上游 `Set-Cookie`，同时设置 5 秒连接、30 秒读取超时。
- 正式部署继续使用原锁、精确 main CI、归档、`nginx -t`、reload 失败恢复旧 vhost 与运行版本核验。

## 验证计划与发布边界

- `bash -n` 检查受影响 Shell 脚本，`git diff --check` 检查补丁。
- `scripts/test-remote-deploy-production.sh` 验证正式模板包含精确路由、固定私有上游和受控 envsubst 列表。
- `scripts/test-asset-upload-proxy.sh <frontend-image> <backend-image>` 使用生产镜像、TLS host Nginx 与隔离内存接收器，验证 PNG 字节、`image/png` 及相邻路径不被转发。
- Gate 1 通过后才交独立 Gate 2；通过后正常 `--no-ff` 合入 `dev`，再走精确 dev CI、Release Gate、main CI 与正式部署。
- 在生产发布和真实异地 RPA 下载完成前，只能写“候选/CI/代码已发布”，不得写“生产已上线”。
- 回滚为发布新的兼容 main SHA 恢复上一版 host vhost；不得删除数据库、Asset 卷、NAS 图片或商品数据。

## Gate 1 本机结果

- `pwsh -NoProfile -File scripts/test-deploy-production.ps1`：PASS，57 项断言；GitHub 与服务器运输均为模拟，不连接生产。
- Git for Windows Bash 对 `remote-deploy-production.sh`、`test-remote-deploy-production.sh`、`test-asset-upload-proxy.sh` 执行 `bash -n`：PASS。
- Python `ast.parse` 检查传输夹具内嵌接收器：PASS。
- `git diff --check`：PASS。
- 本机没有 Docker daemon，因此生产镜像＋TLS Nginx 的真实容器回归留给仓库原 `container-runtime` CI；未把静态检查记为该项通过。
