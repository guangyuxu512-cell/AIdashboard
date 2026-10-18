# Production 部署与发布

## 定位

本文件定义首次正式生产部署的最小工程边界。它与 [08-VPS开发后端部署.md](08-VPS开发后端部署.md) 的 DEV / STAGING 后端发布完全隔离：开发环境继续使用 `control_center_dev`，生产只使用独立的 `control_center_prod`。

生产发布仍遵守：

```text
Feature Gate 1
→ Integration Gate 2 / Green dev
→ Release Gate / main
→ 本地 Codex / PowerShell 经 SSH 调用现有生产部署脚本
```

正式应用 CD 由 `scripts/deploy-production.ps1` 发起；代码推送与四个 CI Job 仍在 GitHub。
`.github/workflows/production-deploy.yml` 只保留明确触发的 `workflow_dispatch` 应急入口，
调用同一个 PowerShell 脚本，不再监听 `workflow_run`。本工程候选尚未通过 Gate/Release 时，
这些描述是待发布行为，不能据此宣称生产执行入口已切换。

- 仅接受等于最新 `origin/main` 的完整 40 位小写 SHA；用该仓库正式 `ci.yml` 的 main push 运行核对
  精确 SHA，以最新 Run 的结果为准，必须 completed/success。无运行、失败、取消及运行中都拒绝；
  同 SHA 的旧成功记录不能覆盖新的失败。Deploy 在第一次 SSH 前再次读取 main/CI，Plan 不构成发布批准。
- 归档只由 `git archive --format=tar.gz --output=... <sha>` 从提交生成。完整 Backend、PC、Mobile、
  Compose 与原远程脚本沿用原白名单；上传的脚本也从同一归档提取，不读取本地未提交源码或 `.env`。
- 本地与应急入口在服务器同一 `.deploy.lock` 上互斥；`flock` 不可用或已有部署持锁时失败，不并行迁移、
  切换 `current` 或回滚。锁覆盖读取旧 current 到 EXIT 清理，退出码 75 表示有部署正在进行。
- current 已为目标 SHA 时，在相同锁下调用 `deploy/production/verify-active-release.sh`，核三个容器的
  实际 image tag 等于目标 SHA、均 running/未暂停、Backend/Signer 均 healthy；Frontend 沿用仅 running
  标准。全部匹配才跳过上传/迁移，再核公网 health。混版、缺失或不健康会失败并保留现场，不能仅凭
  current 与通用 health 判为已部署。已存在但并非 current 的同 SHA release 仍拒绝覆盖。
  新入口还拒绝缺少共享锁的旧 release 脚本。

本地使用 PowerShell 7.4+、Git、GitHub CLI、OpenSSH、tar 和 curl 的已有安装；使用既有 GitHub 认证与
受保护 SSH config/key/known_hosts。部署主机参数是已核实的 SSH 别名或 user@host，不能关闭主机校验。
应用秘密始终留在服务器 `.env`。默认 `Plan` 会读取 GitHub CI 并生成本地归档/收据，不联系生产服务器：

```powershell
pwsh -NoProfile -File scripts/deploy-production.ps1 -DeploySha <完整main-SHA> `
  -SshHost <已核实生产SSH别名> -PublicHost 119.29.188.118
```

Gate/CI 与本次备份证据核齐后，Main 才执行同一命令并加 `-Mode Deploy -BackupReference <发布记录位置>`。
备份引用应指向包含路径、大小、SHA-256 和可读性验证的现有 Release Gate 记录；该参数只登记证据引用，
不创建或验证备份，不取代备份步骤。不能因为本地可 SSH 就跳过失败的 main CI。
本地收据/归档在 ignored `.dev-runtime/production-deploy/<sha>-<attempt>/`；支持显式指定不存在的
输出目录。`receipt.json` 记录目标 SHA、CI Run、归档 SHA-256、attempt、备份引用与最终结果。

本地断线、关机或 SSH 非零退出后，结果按 `FAILED_REQUIRES_SITE_CHECK` 处理，不能直接判定已回滚或重试。
Main 先核同一锁有无持有者、服务器 current、三个容器实际 SHA/健康、Migration Head、Nginx 和静态资产；
仍有部署时等待，已有目标 current 时先只读核实。未激活的同 SHA 目录保留，按原保护规则处理。
本地掉电可能来不及更新收据，因此收据不是服务器状态的唯一依据；本入口不引入后台任务/自动重连部署。

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

### 可选的隔离 Buildx 构建入口

正式 root-only `.env` 可选设置 `PRODUCTION_BUILDX_BUILDER=<existing-builder-name>`。
远程部署脚本只经 `production_env_read` 读取该键，不执行环境文件；名称必须以字母或数字开头，
其余只允许字母、数字、`.`、`_`、`-`。未配置、空值及带引号的空值仍使用原来的 Compose build 命令。
非空时只对本次 `docker compose build` 追加 `--builder` 和一个经过校验的名称参数，不 export
`BUILDX_BUILDER`，不执行全局 `buildx use`，不影响后续 run/up 或其他部署的 builder 选择。
无效名称在任何 Docker 调用前安全拒绝，不回显值；实际构建失败继续返回原非零状态，不自动回退默认 builder。

Main 在 Gate/CI/Release Gate 后备份并通过受保护方式更新既有持久配置，先确认宿主机 Compose 支持
`build --builder`、命名 builder 已存在且健康，以及构建结果可进入正式部署使用的本地 image store。
此配置入口不自动创建/启动/升级 builder，不重启 Docker，不清理镜像或缓存；小型隔离 smoke 不能代替
实际候选的完整构建、Migration Head、运行 SHA、服务健康及业务发布核验。部署使用上述正式SSH入口。
Compose 参数依据：[Docker 官方 `compose build` 文档](https://docs.docker.com/reference/cli/docker/compose/build/)。

回退该工程参数时，仅在 Main 已确认默认构建路径安全的情况下恢复备份中的值或移除该键；不能用移除参数
盲试已知故障 builder。应用/数据库恢复继续遵守本文件及 A 的兼容 Reader/数据保留要求，不降级清历史。
这项工程修复不包含选品定时 B/0045，也不需要更新 Electron 安装包。

### Backend 依赖缓存

`backend/Dockerfile` 先只复制 `pyproject.toml`，以 Python3.12 `tomllib` 从其中读取
`project.dependencies` 和 `build-system.requires` 安装生产依赖/构建工具；不维护第二份 requirements。
依赖安装使用 BuildKit 的 `control-center-backend-pip` cache mount，下载缓存属于既有 builder，
不会进入应用数据卷。随后才复制 Alembic、migrations 和 app；项目本身以
`RUN --network=none ... --no-deps --no-build-isolation` 打包安装，意外的构建下载会明确失败。
Node、PDD vendor、app用户、资产目录、Healthcheck及启动命令保持原样。

同一 builder/base/pyproject 下只改业务源码，应复用整个依赖层；源代码仍重新安装。
首次构建、依赖/基础镜像变化、builder迁移或缓存被清理后仍可能下载，不能承诺消除网络问题或固定耗时。
保留现有生产 `PRODUCTION_BUILDX_BUILDER`，不用每次创建builder、加no-cache或逐release cache-bust。
过期构建缓存回收会让下一次重新预热，不删除生产镜像、数据库或Asset数据。

原 container-runtime Job 的 Backend build 改由 `scripts/test-backend-dependency-cache.sh` 执行：
导出精确提交的 Backend context，测试专用首次 `--no-cache` 构建；只新增一个临时app探针，再次构建。
第二轮必须依赖步骤 `CACHED`、项目安装步骤实际执行，并从 `/tmp` 以正式非root app用户验证
site-packages里的新探针；项目安装本身始终禁网。原PDD/Node与后续真实镜像检查继续消费原CI镜像。
该脚本只对已经提交的 HEAD 有效，不把未提交Dockerfile或本机无Docker的语法检查当缓存通过。
本工程发布前保留原构建方式的生产事实，实际服务器提速须发布后另核；不得改动正在执行的发布。

### 经营数据每日采集启用顺序

经营数据代码发布、服务健康通过，不等于已经允许自动访问抖店平台。Release Gate 先按精确候选核对
启用抖店、有效 Session、昨日预计任务和既有活动/暂停队列（包含旧版已建历史任务）；不删除旧失败或事实。
此版本不新增 Migration，保留 0041 和既有审计。保留服务器 root-only 持久化配置，不重复启用：

```text
BACKEND_OPERATING_DASHBOARD_COLLECTION_EXECUTION_ENABLED=true
BACKEND_OPERATING_DASHBOARD_DAILY_COLLECTION_ENABLED=true
BACKEND_OPERATING_DASHBOARD_DAILY_COLLECTION_LOCAL_TIME=09:00:00
```

简单流程的每日计划只采昨日。启动到点后使用同一 `daily:` 标记，不新增 30 日历史；新店与启用不规划，
重新授权只恢复原来请求。首次和其他历史范围由看板手动更新（最多 60 日），完整范围不产生任务。
昨日 09:00 前的手动任务排队等待，历史日期可先处理；不能把平台任意拒绝误报为数据未就绪。

退休的 `BACKEND_OPERATING_DASHBOARD_INITIAL_BACKFILL_DAYS`、
`BACKEND_OPERATING_DASHBOARD_GAP_RECOVERY_MAX_ATTEMPTS` 和
`BACKEND_OPERATING_DASHBOARD_LEGACY_RESPONSE_PARSE_RECOVERY_ITEM_IDS` 不再参与规划。
Release Gate 可备份后移除这些未使用配置，但本 Feature 不直接改生产配置。显式解析恢复在正式看板完成，
共用冷却和失败链上限，无需再填写 UUID 清单；不放开 metrics-unavailable、风险或未知平台拒绝。
不新建 `daily-recovery:` 特殊 Job，但兼容读取和执行旧持久化任务，禁止顺手删除历史。

部署核验须覆盖：首次手动范围入库/回读、每日仅昨日、显式解析恢复、完整范围普通更新零 Job/Item/平台请求，
以及共用店铺表单无日期输入且保存不清空旧日期。既有 Signer、解析、事实 upsert、权限均不改。
首次 09:00 尚未到达只能写“首次定时执行待观察”；不能用手动测试代替。失败保留旧成功事实。
回退到上一兼容 release 会恢复旧自动历史规划和特殊恢复策略，应先核对队列/备份部署配置，不能当作纯视觉回退。
本 Feature 不重启生产或更改每日开关，生产仅在 Gate/Release Gate 后由 ca97 协调。

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

GitHub 手动应急部署：`.github/workflows/production-deploy.yml`，checkout 明确固定 `ref: main`，
即使手动触发时选择其他分支，入口仍来自受审 main。

手动 `workflow_dispatch` 需要输入当前已发布 main SHA 与已有备份记录引用，调用相同本地入口并核验
该 SHA 的最新 main push CI。日常本地入口使用既有 SSH 配置；应急 workflow 使用以下 Secrets（只记录名称）：

- `PRODUCTION_DEPLOY_HOST`
- `PRODUCTION_DEPLOY_USER`
- `PRODUCTION_DEPLOY_SSH_PRIVATE_KEY`
- `PRODUCTION_SSH_KNOWN_HOSTS`

共享入口上传提交归档，先核归档 SHA-256，再执行原远程脚本构建镜像、前向 Alembic、Signer/Backend/PC/Mobile
健康与静态资源检查，并切换 Nginx。随后在发起端验证公网 `/health` 的 application/json 与精确
`{ "status": "ok" }` 契约。Backend/Frontend HTTP 就绪仍最多等待45秒。archive/脚本名使用每次独立UUID
隔离，应用环境变量继续留在服务器。依赖构建仍在原服务器，移动SSH发起端不承诺缩短Docker构建时间。

生产 release 与 Public-IP TLS provisioning 的每条 Runner SSH/SCP 调用都使用 OpenSSH `ServerAliveInterval=30` 与 `ServerAliveCountMax=3`，同时继续严格校验 `known_hosts`。这只让客户端在远端构建等无输出阶段保持连接；不会忽略 SSH/SCP 或远端脚本的非零退出码，远端脚本仍将其退出状态返回给 Workflow。曾观察到 `client_loop: send disconnect: Broken pipe` 时，只能将其视为连接断开的证据；未取得网络空闲超时的直接证据前，不得将其记录为已确认根因。

旧的自动触发 SHA resolver 已无消费者并删除；精确 SHA/CI 门禁统一在 PowerShell 入口。
`scripts/test-deploy-production.ps1` 用本地真实 Git 仓库/归档与模拟 GitHub/运输检查门禁和字节，
`scripts/test-remote-deploy-production.sh` 在隔离 Linux fixture 验证真实 flock 并发拒绝、同SHA跳过与原失败清理。

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
