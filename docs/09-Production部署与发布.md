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
  → exact `/health` → Backend :127.0.0.1:18001
  → Frontend :127.0.0.1:18080
      → PC `/`
      → Mobile `/mobile/`
  → /api/ reverse proxy
  → Backend :127.0.0.1:18001
  → PostgreSQL :127.0.0.1:35433 / control_center_prod

Backend → Douyin Signer :127.0.0.1:8788
Backend → existing Docker Asset volume (local mode) / verified NAS mount (mounted mode)
```

- Production Backend、Signer 与 Frontend 都只监听主机回环地址；不得直接发布 Docker 端口。
- Frontend 保持只读根文件系统；Nginx 官方入口运行时渲染的 `/etc/nginx/conf.d`、缓存、运行时和临时目录使用受限 `tmpfs`，不得因此放宽整个容器的写入权限。`NGINX_ENVSUBST_FILTER` 使用变量名正则，只允许渲染 `FRONTEND_BIND_HOST`、`FRONTEND_BIND_PORT` 与 `BACKEND_BIND_PORT`。
- 同一个 Frontend image 同时提供 PC 根入口与 Mobile `/mobile/`，不新增容器或端口。`/mobile` 以代理安全的相对 `Location: /mobile/` 重定向，禁止泄漏内部 HTTP scheme 或 `18080` 上游端口；Mobile SPA fallback 只在 `/mobile/` 内生效，缺失的 Mobile JS、CSS、Manifest 或图标必须返回 `404`，不能回退到 PC `index.html`。`/api/` 继续使用同一 Backend proxy；Host Nginx 的精确 `/health` 直接代理到 Backend，避免被 PC SPA fallback 返回 HTML，供 Worker 在不携带 Token 的第一步健康检查使用。
- 公网入口仅由现有 BaoTa Nginx vhost 管理。本部署的明确决策是直接使用 VPS 公网 IPv4，而非 DNS 域名。Let’s Encrypt 的 IP 证书必须使用 `shortlived` profile，约 160 小时有效；因此 `control-center-production-ip-acme-renew.timer` 每日运行两次，续期后由 host Nginx reload 读取新证书。明文 HTTP 只用于 ACME HTTP-01 challenge 和 HTTPS 重定向，不能作为应用入口。
- `control-center-backend-prod-assets` 是正式持久卷，独立于开发环境的 `control-center-backend-dev_backend-assets`。正常更新与回滚不删除该卷；切换 NAS 后它仍保留，作为切换前资产的回退来源。
- PDD 签名继续由 Backend 中现有的隔离 Node 子进程执行。`backend/Dockerfile` 安装 Node.js，且随 `app/platforms/pdd/vendor/anti_content.js` 一起打包；不引入第二套 PDD 服务。
- Douyin Signer 仍是独立的、只绑定回环地址的容器，生产端口为 `8788`，与开发端口 `8787` 隔离。

## PC 跨版本静态资源与参数 API 兼容

发布前仍打开的 PC/Electron 窗口可能请求旧哈希文件。`/assets/` 先读取当前镜像，再读取只读挂载
`/opt/ecommerce-control-center/production/pc-static-assets/public → /var/lib/control-center-static`；
缺失 JS/CSS 返回真实 404，不回退首页。PC 首页使用 no-store，存在的哈希资源使用 immutable 缓存。
Mobile 的 `/mobile/` 规则不变。Compose 的共享路径禁止自动创建；部署脚本在启动容器前准备资源。

`deploy/production/pc-static-assets.sh` 只保留 Vite 带哈希的 JS/MJS、CSS、字体与图片，支持含 `.vue_...`
的依赖名称；不导出历史 index.html、sourcemap、API 数据、环境文件、日志或 symlink。
相同路径但字节不同必须中止发布，不能覆盖旧窗口依赖。新文件完成复制后才原子移入公开目录。
helper 放在现有 `deploy/production` 归档范围内，远程必需文件预检和 CI 真实归档解包都检查它。

保留策略为退出 active 后至少 7 天（604800 秒），当前和最近一份回滚 release 始终保护。
成功切换才记录旧 active 的 `retired-at`；后续部署不会刷新已经 retired 的时钟。首次安装没有可证明的
历史退出时间，因此将仍有本地镜像的历史 release 导入，并从首次成功启用给予 7 天宽限。
已被回收的旧镜像无法凭空恢复：发布前必须核对已确认受影响的 f625 资产实际导入清单，缺少则暂停发布。
当前旧镜像与新镜像的提取必须成功后才替换服务。每次提取用未启动的临时容器，结束时仅删除该容器。

同 SHA 跳过在资源处理之前完成，不续期。失败候选不触发 pruning，原 current/历史文件保持；失败期间
已导入的哈希文件可保留，到下次成功激活再计时。只有不再被任何保留 release 使用的文件才删除。
激活/健康校验已经成功之后若 retention/pruning 失败，命令仍失败并要求 Main 核对现场，但不会撤销健康
current 或删除共享历史目录；此时不得把“工作流失败”直接等同于服务已回滚，也不得盲目重建同 SHA。

回滚到支持此机制的版本时保留共享目录/只读挂载，旧静态引用继续可用。回滚到本修复之前的 Frontend
镜像/Compose 会失去 archive fallback 和更新提示；Main 必须同时保留本修复的 Nginx 模板及只读挂载
（以受审查的 rollback Compose override 挂载模板），或把该限制作为回滚阻塞，不能宣称任意旧镜像
天然具备跨版本支持。不能删除共享目录来“修复”回滚。API 回滚也不得重新破坏旧数组响应。

参数管理 API 无分页参数继续返回数组；显式任一分页参数返回 Page，权限/筛选/排序共用同一查询。
新版 PC 的资源加载失败提示保留当前页面并中止失败导航，不自动刷新。用户点击重新加载后须再次明确确认，
也可“继续编辑”保存草稿，再从同一提示重开确认。它不复制草稿/凭据到通用本地缓存。
旧发布 bundle 不含这一新提示、初始入口本身无法加载时也无法运行提示逻辑；这部分窗口依靠历史资源保留，
超出保留期需要用户主动重新加载客户端，不能声称提示可以追溯注入已发布 bundle。

验收必须使用生产 build + 同款 Nginx，并由 ca97 保持旧 Electron 窗口进行切换/菜单/配置读取与刷新后
分页验收。`scripts/test-pc-static-assets.sh` 验证生命周期；`scripts/test-pc-static-nginx.sh <image> [old-assets]`
验证只读临时容器中的真实字节、缓存和 404，独立随机回环端口、无数据库；它不代替 Electron 人工操作。

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

### 经营数据每日采集启用顺序

经营数据代码发布、Migration 与服务健康通过，不等于已经允许自动访问抖店平台。Release Gate 必须先以部署后的
精确 SHA 验证 Backend、Signer 和持久化 collection queue：确认当前启用且受支持的抖店数量、最近 30 日的预计
缺口数量、没有遗留的 Feature/Integration collection item，并确认不会把停用店铺或缺失 Session 当作成功。
随后才在服务器 root-only `.env` 持久化以下非秘密配置并按现有发布规范重启服务：

```text
BACKEND_OPERATING_DASHBOARD_COLLECTION_EXECUTION_ENABLED=true
BACKEND_OPERATING_DASHBOARD_DAILY_COLLECTION_ENABLED=true
BACKEND_OPERATING_DASHBOARD_DAILY_COLLECTION_LOCAL_TIME=09:00:00
```

若 Release Gate 已逐项确认旧版可选字段解析缺陷留下的终态失败，可额外配置
`BACKEND_OPERATING_DASHBOARD_LEGACY_RESPONSE_PARSE_RECOVERY_ITEM_IDS` 为精确原 item UUID 的 JSON 数组；默认必须为
`[]`。该清单只用于发布后自动恢复已审计的历史 item，不是会话、平台拒绝或一般解析失败的重试开关；用户在看板中
明确选择当前最新的 `DOUYIN_OPERATING_DATA_INVALID_RESPONSE / response_parse` item 时，不需要依赖该配置，仍由服务端
统一执行权限、活动任务去重、冷却和跨 Job 累计次数限制。部署后仅让每个已批准旧 item 通过既有补漏规划创建一次
新的尝试，保留旧失败记录，并在新 item 已入队后从清单移除已处理 UUID。

该顺序使启动恢复与每日计划在 Asia/Shanghai 09:00 生效：昨日优先，并仅补最近 30 个完整自然日的缺口；不采
今日实时数据。启用后记录下次执行时间、实际 queue 数量、暂停重新授权数和失败分类。若首次 09:00 尚未到达，只能
记录“已启用、首次定时执行待观察”，不能写成已经定时成功。回退自动采集时先将两个开关设为 false 并按规范重启；
已持久化的日事实保留，队列和失败记录不得靠删除数据清理。更早历史只由看板明确提交的手动分批补采处理。

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

## NAS Asset Storage（启用前置条件）

默认 `BACKEND_ASSET_STORAGE_MODE=local` 继续使用
`control-center-backend-prod-assets` named volume。启用 NAS 时，NAS 只保存文件；数据库仍是 VPS 上的
`control_center_prod` PostgreSQL，Asset 表、`asset_id`、`storage_key`、鉴权 API 和 Frontend Blob
读取契约均不改变。

主线发布前由 Production 运维完成以下准备，不能把 SMB/NFS 文件共享端口公开到互联网：

1. NAS 已创建独立的中控台 Asset 共享文件夹，VPS 使用专用非管理员服务账号；不复用、修改或清理其他共享目录。当前共享名为 `control_center_assets`，路径为 `/volume1/control_center_assets`，SMB 浏览隐藏；服务账号只取得该共享所需的 RW 权限。
2. VPS 与 NAS 已通过私有 Overlay 网络连通，并以 SMB3/CIFS 将该共享挂载到固定宿主路径 `/mnt/control-center-assets`。CIFS 凭据位于 VPS root-only credentials 文件，不进入仓库、Compose、shell history 或日志；445 或 2049 没有公开到互联网。
3. 已以实际 Backend image 的 `app` UID/GID 配置并验证挂载权限，确认该身份对挂载点有读、写、执行权限。不要以 root 成功的检查替代容器身份检查。
4. 在挂载根目录创建唯一标识文件；文件内容为 `control-center-asset-storage-v1` 后紧跟一个 LF（`0x0A`）：

   ```text
   .control-center-asset-storage-v1
   control-center-asset-storage-v1
   ```

   先用独立测试目录验证写入、读取、SHA-256 内容校验与删除；不得用已有业务图片作探针。
5. 复核 `findmnt -T /mnt/control-center-assets`（或等价命令）确认它是真实网络挂载，而不是 VPS 本地空目录，并以容器的 `app` 身份执行一次存储预检。

如需在新的 Debian/Ubuntu VPS 重建该挂载，Main 按如下顺序准备；`<nas-overlay-ip>`、服务账号密码和 credentials 文件内容只存在 VPS，不写入本仓库：

```sh
sudo apt-get install -y cifs-utils
sudo install -d -m 0750 /etc/samba/credentials /mnt/control-center-assets
sudoedit /etc/samba/credentials/control-center-assets
# username=control_center_vps_assets
# password=<NAS service-account password>
sudo chmod 0600 /etc/samba/credentials/control-center-assets
```

写入 root 管理的 `/etc/fstab` 前，先用一次临时 mount 和 `findmnt` 验证 overlay 来源。正式条目应使用 SMB3 加密、容器 `app` 身份和 systemd automount，例如：

```fstab
//<nas-overlay-ip>/control_center_assets /mnt/control-center-assets cifs credentials=/etc/samba/credentials/control-center-assets,vers=3.1.1,seal,uid=999,gid=999,file_mode=0660,dir_mode=0770,rw,nosuid,nodev,noexec,_netdev,x-systemd.automount 0 0
```

已完成隔离 Candidate 容器的标识、读写、SHA-256、容器重建后读取，以及持久 fstab 卸载/重新挂载后的再次读取验证。实际 VPS 重启后的 automount 验证尚未覆盖；在该验证与 Release Gate 前，生产保持 `local` 模式，不设置 NAS 环境变量。

满足前置条件后，VPS root-only `.env` 增加以下非秘密部署配置，再发布包含该配置的精确 main SHA：

```text
BACKEND_ASSET_STORAGE_MODE=mounted
BACKEND_ASSET_STORAGE_VOLUME_SOURCE=/mnt/control-center-assets
```

`BACKEND_ASSET_STORAGE_DIR` 在容器内仍固定为 `/app/data/assets`。Compose 将上述宿主挂载路径绑定到该
容器路径；发布预检分为两个独立层次，缺一不可：

1. **宿主机挂载检查**：`mounted` 模式要求 `BACKEND_ASSET_STORAGE_VOLUME_SOURCE` 是绝对路径，并由
   `findmnt` 返回至少一个真实的 `cifs`、`nfs` 或 `nfs4` 文件系统条目。这发生在 Docker build/run
   之前；普通 VPS 本地目录即使含有正确标识文件也会被拒绝。systemd automount 可能同时返回 `autofs`
   占位项和已触发的 CIFS/NFS 项；仅存在 `autofs` 不能通过预检。
2. **应用目录检查**：随后一次性 Backend 容器以实际 `app` UID/GID 读取绑定后的
   `/app/data/assets`，验证标识文件精确字节和读、写、执行权限。

两项检查都在 Alembic 前完成。标识缺失、挂载消失或权限不足会使预检失败；即使运行期发生该类故障，Asset
API 也会返回明确的 `ASSET_STORAGE_UNAVAILABLE`（503），不会自动退回本地卷。

切换前必须对现有 named volume 和 NAS 目标分别建立文件清单（原图以相对 `storage_key`、大小、SHA-256
核对；已存在的派生缩略图以 `<asset_id-hex>.thumbnail.webp` 单独清单核对）。在停写窗口内复制旧 Asset
到 NAS，并复核数量、大小、散列和代表性历史 Asset 的正式读取。缺失的旧缩略图可以在后续受权限访问时
按原图重新生成，不能把它当作 Asset 丢失。旧 named volume 必须保留。切换后新增文件只在 NAS；因此不能
仅将环境变量改回 `local` 作为回退。若必须回退，先将切换后新增的 NAS 文件按 `storage_key` 及已存在的
派生缩略图复制并校验到旧 volume，或继续保持 NAS 挂载可读，再恢复
先前 release。没有完成该数据步骤不得宣称回退安全。

## GitHub Actions

CI：`.github/workflows/ci.yml`

- Backend pytest；
- Frontend Real typecheck/build；
- Mobile lint、unit、typecheck 与 `/mobile/` production build；
- Production Backend Docker build，并在容器内验证 Node、PDD `anti_content.js` 与签名调用；
- Production Frontend Docker build，在只读根文件系统下验证 PC `/`、Mobile `/mobile/`、Manifest、安装图标、hash 静态资源与缺失资源 `404`，并校验 Compose 契约。

生产部署：`.github/workflows/production-deploy.yml`

手动 `workflow_dispatch` 需要输入当前已发布的 main SHA；自动入口仅接收本仓库 `main` 的成功 `CI` push 事件。两种入口都使用以下 GitHub Actions Secrets（只记录名称）：

- `PRODUCTION_DEPLOY_HOST`
- `PRODUCTION_DEPLOY_USER`
- `PRODUCTION_DEPLOY_SSH_PRIVATE_KEY`
- `PRODUCTION_SSH_KNOWN_HOSTS`

Workflow 使用部署专用 SSH key 上传 source archive；archive 必须包含完整 `mobile/` build context，不能只包含 package manifest。远程脚本构建镜像、执行向前 Alembic Migration、验证 Signer/Backend/PC Frontend 与 Mobile `/mobile/` 的 HTML、Manifest、图标和实际 hash JS/CSS，并在健康后原子切换 Nginx vhost。随后 GitHub Runner 从公网验证 `https://<production-host>/health` 的 `application/json` 与精确 Backend `{ "status": "ok" }` 契约，防止 Worker 被 SPA HTML 误导。容器启动后，Backend 与 Frontend HTTP 就绪检查最多等待 45 秒，避免将正常的异步启动误判为失败。远程 archive 和脚本名以 GitHub run ID / attempt 隔离，避免相同 SHA 的不同尝试覆盖或清理彼此的临时材料。应用环境变量保留在服务器 `.env`，不复制到 GitHub Secrets。

生产 release 与 Public-IP TLS provisioning 的每条 Runner SSH/SCP 调用都使用 OpenSSH `ServerAliveInterval=30` 与 `ServerAliveCountMax=3`，同时继续严格校验 `known_hosts`。这只让客户端在远端构建等无输出阶段保持连接；不会忽略 SSH/SCP 或远端脚本的非零退出码，远端脚本仍将其退出状态返回给 Workflow。曾观察到 `client_loop: send disconnect: Broken pipe` 时，只能将其视为连接断开的证据；未取得网络空闲超时的直接证据前，不得将其记录为已确认根因。

自动入口的 SHA 判定在 `scripts/resolve-production-deploy-target.sh` 中执行，并有独立回归覆盖当前主线、过期 CI 候选与手动过期 SHA。此 helper 只决定是否部署，不读取生产凭据，也不连接生产服务器。

远程脚本会把 `current` 已指向的同 SHA release 视为已成功上线并无副作用跳过；除此之外仍拒绝已存在的同 SHA release，并保留该目录、历史 release 与 `current` 指向的目录。失败清理只能移除本次创建且尚未成为 `current` 的 release；不得以重试为由删除已存在目录。遇到已存在而未激活的 release 时，先保留现场并通过新的 Feature / Gate / main 发布修复后，再以新的 main SHA 重新部署。

`Production Provision Public-IP TLS` 使用同一套 SSH Secrets，但只负责公共 IP 证书、Nginx ACME challenge vhost 与续期 timer；它不创建数据库、不启动应用容器，也不替代 `Production Deploy`。

## 回滚与备份

- 新容器健康或 Nginx 配置失败时，远程脚本恢复上一个 release 目录与已知容器版本；不会删除 Asset 卷。
- Alembic 只向前执行。若新 Migration 不具备应用级向后兼容性，不能把 Git 回滚当成数据库回滚；必须按该 Migration 的明确回滚方案处理。
- 生产 PostgreSQL 必须在首次迁移前按当前服务器既有 PostgreSQL 备份方式单独备份，并记录路径、大小、SHA-256 与可读性验证。备份不进入仓库。
- 生产图片依赖 Docker named volume；PostgreSQL 备份不替代 Asset 卷备份。后续运维需按宿主机卷备份策略同时覆盖数据库和该卷。
- 日期目录 Feature 之后的新 Asset `storage_key` 使用 `Asia/Shanghai` 日期目录；历史扁平 key 不迁移，
  仍由新版本读取。日期目录前的旧 Backend 不能读取新 key，因此只要生产已写入新路径文件，不能将
  应用直接回退到日期目录前的 release；必须改用包含新旧 key 读取能力的兼容 release，并保留 Asset
  volume / NAS 文件。NAS 日期目录不是浏览器按产品或模板组下载文件夹功能。

## 首次生产验收

部署完成不等于业务闭环。首次验收至少记录：

1. GitHub Actions run 与实际部署 SHA；
2. HTTPS 访问、Frontend Real API、管理员登录；
3. `control_center_prod` 的 Alembic revision；
4. Douyin Signer health、PDD Node signer 运行；
5. Asset 上传后重启服务仍可读取；
6. 配置齐全时，一次最小 ToAPIs 生成；人工平台登录需要在真实页面完成，并如实标记未覆盖项。
7. PC 根入口与 Mobile `https://119.29.188.118/mobile/` 同时可用；Mobile 正式账号登录、刷新恢复、Team/Module Access 与退出正常，Manifest 和安装图标可读取。添加至主屏幕、独立窗口启动、关闭重开与版本刷新必须由真实支持的手机浏览器验收；浏览器模拟视口不能冒充真机安装通过。

公网 IP 已确定为部署入口；但首次验收仍需要 IP 证书、ACME 联系邮箱、首位管理员身份和生产 ToAPIs 配置。在这些前置条件具备前，任何结果只能标记为“代码已发布”，不能标记为“生产已部署”。
