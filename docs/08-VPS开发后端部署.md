# VPS 开发 Backend 部署

## 定位与拓扑

该部署只属于 DEV / STAGING，使用 `control_center_dev`，不是 Production，也不会创建 `control_center_prod`。

```text
Worker / Frontend
        ↓ HTTPS（域名与 TLS 就绪后）
已有 Nginx
        ↓ 127.0.0.1:18000
control-center-backend-dev
        ↓ host network / 127.0.0.1:35433
control-center-postgres-dev:5432（现有回环端口映射）
```

Backend 和 PostgreSQL 的内部端口不得绑定公网。Worker 只访问 Backend API，不访问 PostgreSQL，也不需要 SSH。

## 服务器结构

```text
/opt/ecommerce-control-center/backend/
├── .env                  # 0600，不进 Git
├── current -> releases/<release-id>
└── releases/<release-id>/
    ├── compose.yaml
    ├── Dockerfile
    ├── app/
    └── migrations/
```

Backend 容器名固定为 `control-center-backend-dev`，使用 Python 3.12、非 root 用户、只读根文件系统、`restart: unless-stopped`，Docker JSON 日志轮转为 10 MiB × 5。审计发现 PostgreSQL 的 `pg_hba.conf` 只允许宿主机来源并拒绝其他容器网段，因此采用方案 B：Backend 使用 host network，但 Uvicorn 强制只绑定 `127.0.0.1:18000`，数据库使用现有 `127.0.0.1:35433` 回环绑定。不修改 PostgreSQL 认证规则、容器或数据卷。

## 部署与更新

在项目根目录执行：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\deploy-backend-dev.ps1
```

脚本先运行 Backend 测试，再仅打包 Backend 运行内容，通过现有 SSH Config `control-center-dev` 上传，服务器构建带内容版本的 Image，执行一次 `alembic upgrade head`，启动容器并等待 `/health`。首次部署从本机受保护的开发配置初始化服务器 `.env`；以后复用服务器文件，过程中不输出 Secret。部署绝不执行 downgrade、DROP、Volume 删除或 PostgreSQL 重建。

每次发布写入新 release 目录并更新 `current` 符号链接。若新容器健康检查失败，脚本把链接和 Compose 服务恢复到上一 release；数据库 Migration 只允许向前升级，因此涉及不向后兼容的 Migration 时必须单独设计应用级回滚，不能自动 downgrade。

## 验证

部署脚本自动检查：

- VPS 内部 `GET http://127.0.0.1:18000/health`。
- Backend 容器通过 VPS 回环端口连接 `control_center_dev`。
- `alembic current` 已到当前 Head。

运维排查使用：

```bash
docker ps --filter name=control-center-backend-dev
docker logs --tail 100 control-center-backend-dev
curl --fail http://127.0.0.1:18000/health
```

## HTTPS 与停止条件

仓库提供 `backend/deploy/nginx-backend-dev.conf.template`，但模板中的域名和证书路径必须由真实 Domain / DNS / TLS 确定后才可启用。默认禁止猜域名、用公网 `http://IP:8000` 传 Worker Token，或覆盖服务器现有 Nginx 配置。在 HTTPS 未具备前，除下述负责人显式批准的可丢弃开发环境外，Backend 只允许 VPS 回环或临时 SSH 隧道验证。

### 可丢弃服务器的显式开发 HTTP 例外

只有项目负责人明确接受 Device Token 和任务流量明文传输、且服务器与数据均可丢弃时，允许执行：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\deploy-backend-dev.ps1 -AllowInsecurePublicHttp
```

该开关把 DEV Backend 改为 `0.0.0.0:8000`，不会改变 PostgreSQL 的 `127.0.0.1:35433` 绑定。它不是 Production 配置；迁移到正式服务器前必须去掉该开关、部署 HTTPS，并轮换所有曾经通过 HTTP 使用的 Device Token。
