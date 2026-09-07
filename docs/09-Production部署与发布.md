# Production 部署与发布

## 定位

本文件定义首次正式生产部署的最小工程边界。它与 [08-VPS开发后端部署.md](08-VPS开发后端部署.md) 的 DEV / STAGING 后端发布完全隔离：开发环境继续使用 `control_center_dev`，生产只使用独立的 `control_center_prod`。

生产发布仍遵守：

```text
Feature Gate 1
→ Integration Gate 2 / Green dev
→ Release Gate / main
→ GitHub Actions 手动 Production Deploy
```

本轮的 `Production Deploy` 工作流只接受明确等于当前 `origin/main` 的完整 40 位提交 SHA。首次生产验收前，不启用 main push 自动部署；启用自动部署必须走新的 Feature、Gate 1、Gate 2 和 Release Gate。

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
- 公网入口仅由现有 BaoTa Nginx vhost 管理。首次部署前必须有真实域名与已签发证书，不能以 IP 或明文 HTTP 代替。
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
- `PRODUCTION_DOMAIN`、证书与私钥路径、BaoTa `PRODUCTION_NGINX_VHOST_DIR`。

部署脚本在 build、迁移或覆盖 Nginx 前验证这些条件，并拒绝将 Backend 指向 `control_center_dev`。

## 数据库与首位管理员

生产数据库与应用角色必须在当前 VPS 的 PostgreSQL 实例中创建，但不得影响 `control_center_dev`、`control_center_integration` 或任何现有卷。创建步骤只允许使用现有 PostgreSQL 管理通道，并在交互式 `psql` 中设置应用角色密码；不要把密码放到 shell history、GitHub workflow、文档或聊天中。

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

手动部署：`.github/workflows/production-deploy.yml`

仅 `workflow_dispatch`，需要输入当前已发布的 main SHA。它使用以下 GitHub Actions Secrets（只记录名称）：

- `PRODUCTION_DEPLOY_HOST`
- `PRODUCTION_DEPLOY_USER`
- `PRODUCTION_DEPLOY_SSH_PRIVATE_KEY`
- `PRODUCTION_SSH_KNOWN_HOSTS`

Workflow 使用部署专用 SSH key 上传 source archive，远程脚本构建镜像、执行向前 Alembic Migration、验证 Signer/Backend/Frontend health，并在健康后原子切换 Nginx vhost。应用环境变量保留在服务器 `.env`，不复制到 GitHub Secrets。

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

真实域名、TLS 证书和首位管理员身份目前尚未配置；在这些前置条件具备前，任何结果只能标记为“代码已发布”，不能标记为“生产已部署”。
