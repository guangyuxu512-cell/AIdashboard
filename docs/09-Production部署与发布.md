# Production 部署与发布

## 定位

本文件定义首次正式生产部署的最小工程边界。它与 [08-VPS开发后端部署.md](08-VPS开发后端部署.md) 的 DEV / STAGING 后端发布完全隔离：开发环境继续使用 `control_center_dev`，生产只使用独立的 `control_center_prod`。

生产发布仍遵守：

```text
Feature Gate 1
→ Integration Gate 2 / Green dev
→ Release Gate / main
→ GitHub Actions Production Deploy
```

`Production Deploy` 同时提供手动和自动入口，二者共享同一个并发组与远程部署链路：

- 手动入口 `workflow_dispatch` 保留，仍只接受明确等于当前 `origin/main` 的完整 40 位小写 SHA。
- 自动入口只监听本仓库 `main` 的 `CI` 工作流完成事件；只有该事件是 `push`、分支是 `main`、且 CI 结论为 `success` 时才进入部署 Job。`dev`、Feature、Pull Request、失败和取消的 CI 都不会触发生产部署。
- 自动入口以 `workflow_run.head_sha` 作为唯一候选，部署前重新读取 `origin/main`。若该 SHA 在排队期间已不是当前 `origin/main`，工作流以“已跳过过期的 CI 候选”成功结束；绝不能改为部署较新的、尚未由这次 CI 验证的 HEAD。
- 若服务器 `current` 已指向同一 SHA 的 release，自动与手动入口都会明确跳过，不上传、不删除既有 release，也不重复执行 Migration 或首次管理员初始化。已存在但并非 `current` 的同 SHA release 继续被保护并拒绝覆盖，必须以新的 main SHA 发布。

## 拓扑与隔离

```text
Browser HTTPS
  → BaoTa host Nginx :443
  → Frontend :127.0.0.1:18080
  → /api/ reverse proxy
  → Backend :127.0.0.1:18001
  → PostgreSQL :127.0.0.1:35433 / control_center_prod

Backend → Douyin Signer :127.0.0.1:8788
Backend → control-center-backend-prod-assets Docker volume
```

- Production Backend、Signer 与 Frontend 都只监听主机回环地址；不得直接发布 Docker 端口。
- Frontend 保持只读根文件系统；Nginx 官方入口运行时渲染的 `/etc/nginx/conf.d`、缓存、运行时和临时目录使用受限 `tmpfs`，不得因此放宽整个容器的写入权限。`NGINX_ENVSUBST_FILTER` 使用变量名正则，只允许渲染 `FRONTEND_BIND_HOST`、`FRONTEND_BIND_PORT` 与 `BACKEND_BIND_PORT`。
- 公网入口仅由现有 BaoTa Nginx vhost 管理。本部署的明确决策是直接使用 VPS 公网 IPv4，而非 DNS 域名。Let’s Encrypt 的 IP 证书必须使用 `shortlived` profile，约 160 小时有效；因此 `control-center-production-ip-acme-renew.timer` 每日运行两次，续期后由 host Nginx reload 读取新证书。明文 HTTP 只用于 ACME HTTP-01 challenge 和 HTTPS 重定向，不能作为应用入口。
- `control-center-backend-prod-assets` 是正式持久卷，独立于开发环境的 `control-center-backend-dev_backend-assets`。正常更新与回滚不删除该卷。
- PDD 签名继续由 Backend 中现有的隔离 Node 子进程执行。`backend/Dockerfile` 安装 Node.js，且随 `app/platforms/pdd/vendor/anti_content.js` 一起打包；不引入第二套 PDD 服务。
- Douyin Signer 仍是独立的、只绑定回环地址的容器，生产端口为 `8788`，与开发端口 `8787` 隔离。

## 生产环境文件

服务器仅保存一个 root 管理、权限为 `0600` 的文件：

```text
/opt/ecommerce-control-center/production/.env
```

初始模板为 [deploy/production/.env.example](../deploy/production/.env.example)。该文件永远不进入 Git、release archive、GitHub Actions 日志或工单。

必须配置：

- `BACKEND_DATABASE_URL`：专用应用角色连接 `control_center_prod`。
- `BACKEND_ENCRYPTION_KEY`。
- `BACKEND_DOUYIN_SIGNER_API_KEY` 与回环 `BACKEND_DOUYIN_SIGNER_URL`。
- `BACKEND_TOAPIS_API_KEY` 及其已确认的 ToAPIs 配置。
- `BACKEND_HUMAN_SESSION_COOKIE_SECURE=true`。
- `PRODUCTION_DOMAIN`：真实公网 IPv4。该既有变量名被保留，因为 Nginx 可以用 IP 作为 `server_name`。
- `PRODUCTION_ACME_EMAIL`、`PRODUCTION_ACME_CERT_NAME`、Certbot image 与 ACME state/webroot 路径。
- IP 证书与私钥路径、BaoTa `PRODUCTION_NGINX_VHOST_DIR`。

部署脚本在 build、迁移或覆盖 Nginx 前验证这些条件，并拒绝将 Backend 指向 `control_center_dev`。首次应用部署前，先手动触发 `Production Provision Public-IP TLS` 工作流，输入当前 `origin/main` 的完整 SHA；它会严格 checkout 该 SHA、以 Certbot 5.8 的 `--ip-address` + `--preferred-profile shortlived` 申请证书，并启用续期 timer。证书阶段会先配置只返回 `503` 的 HTTPS bootstrap vhost，再由 GitHub Runner 直接访问公网 IP 并校验证书；正常 `Production Deploy` 成功后才替换为应用反向代理。该步骤需要公网端口 80 对外可达以及有效的 ACME 联系邮箱。

## 数据库与首位管理员

生产数据库与应用角色必须在当前 VPS 的 PostgreSQL 实例中创建，但不得影响 `control_center_dev`、`control_center_integration` 或任何现有卷。创建步骤只允许使用现有 PostgreSQL 管理通道，并在交互式 `psql` 中设置应用角色密码；不要把密码放到 shell history、GitHub workflow、文档或聊天中。应用角色在 `control_center_prod` 的 `public` schema 必须具备 `USAGE` 和 `CREATE`，以便 Alembic 在空生产库创建版本表和正式 Schema；保留 schema owner 与其他数据库授权不变：

```sql
GRANT USAGE, CREATE ON SCHEMA public TO control_center_prod_app;
```

部署前应以应用角色核对当前数据库、当前账号及这两项 schema 权限：

```sql
SELECT
  current_database(),
  current_user,
  has_schema_privilege(current_user, 'public', 'USAGE'),
  has_schema_privilege(current_user, 'public', 'CREATE');
```

生产 `.env` 配置完成后，运行正式 Alembic：

```text
python -m alembic upgrade head
```

首次迁移完成后，使用既有 Human Auth 初始化入口创建唯一首位人员和默认团队。该命令会交互式读取密码：

```text
python -m app.cli.human_auth bootstrap --display-name <display-name> --login-name <login-name>
```

该初始化只允许空 `users` 表执行一次；不要通过 Seed、直接 SQL 或临时账号绕开它。

## GitHub Actions

CI：`.github/workflows/ci.yml`

- Backend pytest；
- Frontend Real typecheck/build；
- Production Backend Docker build，并在容器内验证 Node、PDD `anti_content.js` 与签名调用；
- Production Frontend Docker build 与 Compose 契约校验。

生产部署：`.github/workflows/production-deploy.yml`

手动 `workflow_dispatch` 需要输入当前已发布的 main SHA；自动入口仅接收本仓库 `main` 的成功 `CI` push 事件。两种入口都使用以下 GitHub Actions Secrets（只记录名称）：

- `PRODUCTION_DEPLOY_HOST`
- `PRODUCTION_DEPLOY_USER`
- `PRODUCTION_DEPLOY_SSH_PRIVATE_KEY`
- `PRODUCTION_SSH_KNOWN_HOSTS`

Workflow 使用部署专用 SSH key 上传 source archive，远程脚本构建镜像、执行向前 Alembic Migration、验证 Signer/Backend/Frontend health，并在健康后原子切换 Nginx vhost。容器启动后，Backend 与 Frontend HTTP 就绪检查最多等待 45 秒，避免将正常的异步启动误判为失败。远程 archive 和脚本名以 GitHub run ID / attempt 隔离，避免相同 SHA 的不同尝试覆盖或清理彼此的临时材料。应用环境变量保留在服务器 `.env`，不复制到 GitHub Secrets。

自动入口的 SHA 判定在 `scripts/resolve-production-deploy-target.sh` 中执行，并有独立回归覆盖当前主线、过期 CI 候选与手动过期 SHA。此 helper 只决定是否部署，不读取生产凭据，也不连接生产服务器。

远程脚本会把 `current` 已指向的同 SHA release 视为已成功上线并无副作用跳过；除此之外仍拒绝已存在的同 SHA release，并保留该目录、历史 release 与 `current` 指向的目录。失败清理只能移除本次创建且尚未成为 `current` 的 release；不得以重试为由删除已存在目录。遇到已存在而未激活的 release 时，先保留现场并通过新的 Feature / Gate / main 发布修复后，再以新的 main SHA 重新部署。

`Production Provision Public-IP TLS` 使用同一套 SSH Secrets，但只负责公共 IP 证书、Nginx ACME challenge vhost 与续期 timer；它不创建数据库、不启动应用容器，也不替代 `Production Deploy`。

## 回滚与备份

- 新容器健康或 Nginx 配置失败时，远程脚本恢复上一个 release 目录与已知容器版本；不会删除 Asset 卷。
- Alembic 只向前执行。若新 Migration 不具备应用级向后兼容性，不能把 Git 回滚当成数据库回滚；必须按该 Migration 的明确回滚方案处理。
- 生产 PostgreSQL 必须在首次迁移前按当前服务器既有 PostgreSQL 备份方式单独备份，并记录路径、大小、SHA-256 与可读性验证。备份不进入仓库。
- 生产图片依赖 Docker named volume；PostgreSQL 备份不替代 Asset 卷备份。后续运维需按宿主机卷备份策略同时覆盖数据库和该卷。

## 首次生产验收

部署完成不等于业务闭环。首次验收至少记录：

1. GitHub Actions run 与实际部署 SHA；
2. HTTPS 访问、Frontend Real API、管理员登录；
3. `control_center_prod` 的 Alembic revision；
4. Douyin Signer health、PDD Node signer 运行；
5. Asset 上传后重启服务仍可读取；
6. 配置齐全时，一次最小 ToAPIs 生成；人工平台登录需要在真实页面完成，并如实标记未覆盖项。

公网 IP 已确定为部署入口；但首次验收仍需要 IP 证书、ACME 联系邮箱、首位管理员身份和生产 ToAPIs 配置。在这些前置条件具备前，任何结果只能标记为“代码已发布”，不能标记为“生产已部署”。
