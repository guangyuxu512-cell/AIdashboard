# Local Codex SSH Deploy V1 — Gate 1

## 候选与范围

- 分支：`feat/local-codex-ssh-deploy-v1`。
- 工作树：`C:\Users\Administrator\.codex\worktrees\local-ssh-production-deploy\中控台`。
- 精确基线 Green：`1cec344b72621b9e50ed3e724e939623e7d366e4`；候选 SHA 以本记录所在提交/正式 Handoff 为准。
- 仅部署工程：共享 PowerShell 入口、原远程脚本的宿主机互斥锁、GitHub 手动应急入口及工程回归/文档。
- 无数据库、端口、Migration Slot、第二 Electron、业务代码、依赖/pin、Dockerfile 缓存或服务器配置变化。
- 不连接生产服务器；当前已授权的 Verify 28 发布与服务器磁盘处理由规划/Main 继续负责。

## 最终行为

默认 Plan 只读取 GitHub 的精确 main push CI 并生成本地提交归档；不能写服务器或发起部署。
显式 Deploy 还要求登记现有 Release Gate 备份记录引用，并在 SSH 前再次核 main/最新 CI。
发布源和执行脚本都从同一 Git commit 归档提取，排除 `.env`/`.env.*`，保留完整 Mobile context。
上传后检查归档 SHA-256，复用原远程脚本的构建、前向 Migration、静态资产保护、回滚和健康检查。
严格 host key、keepalive、非零退出码和公网精确 health JSON 保留。

GitHub 应急 workflow 直接调用同一 PowerShell 入口，删除 `workflow_run` 自动触发。
原 resolver 与测试的消费者已用 `rg` 核对，仅旧 workflow/CI 测试与正式说明；统一入口后删除两个无消费者脚本。
CI 原四 Job 保持，仅在原 container-runtime 工程测试位置替换 resolver 语法/测试调用；原 Backend、PC、
Mobile、Verify 和两个生产镜像构建门槛不改。
同一服务器 `.deploy.lock` 覆盖旧 current 读取、构建、迁移、切换和 EXIT 清理；忙时退出75。
同SHA预检也持同一锁。无锁实现的旧目标 release 被新入口拒绝，避免用新入口部署旧脚本绕开互斥。

本地断线/掉电后先核服务器锁、current、容器 SHA/健康、Migration 与 Nginx/静态资产，再决定处理。
不自动重试，不删除同 SHA 未激活目录。收据可能因本地掉电未更新，不能单凭收据推断回滚。
`BackupReference` 仅引用已有备份证据，不自动创建/验证备份，原 Release Gate 责任保留。

## 已执行验证

运行环境：Windows PowerShell `7.6.5`，Git Bash `5.3.15`，既有 Git/tar/gh；没有安装工具或依赖。

1. `pwsh -NoProfile -File scripts/test-deploy-production.ps1`：PASS，50条断言。
   - 本地临时真实 bare origin/main + commit/dirty worktree + `git archive` + tar，归档保持提交字节，
     不夹带本地 `.env`/untracked；被跟踪的 `.env.example` 也按归档保护排除。
   - GitHub API 和 SSH/SCP/curl 为显式模拟；最新 CI 失败、取消、运行中或缺失，即使旧 Run 成功仍拒绝。
   - SHA 格式/过期与 option-like SSH target 拒绝，默认 Plan 零服务器/health 接触。
   - 部署完整顺序、同SHA不上传、SCP/SSH非零保留、归档校验和精确 health JSON 通过。
   - 用真实 pwsh 子进程 exit41 核验 native wrapper 保留退出码。
2. `bash -n scripts/remote-deploy-production.sh`、`bash -n scripts/test-remote-deploy-production.sh`：PASS。
3. `bash scripts/test-production-deploy-workflow.sh`：PASS；确认仅手动应急入口、复用共享脚本、TLS 原keepalive保留。
4. 指向实际失败 main 的真实只读 Plan：
   `36dbc5ff5009619fa0052f5da06f53383f223329`，正式 main push CI `39131501325` 已 completed/failure。
   入口 exit1，提示最新main CI必须 completed/success；在归档/SSH/SCP/公网health之前拒绝。
   只读取 GitHub 和 fetch main，没有联系生产。
5. 从精确旧 Green `1cec344b72621b9e50ed3e724e939623e7d366e4` 生成本地真实白名单归档，
   SHA256 `3eb3cbb58f913ace555c3657ab0f2dd214a3a0ad7a3df2a7851e09640788e906`。
   解包 `backend/Dockerfile` 的 Git blob 为 `20a06ad73d1aefd32328ed072dcc96662ea0d09d`、
   `scripts/remote-deploy-production.sh` 为 `8027bba0c82762d5e88c1ae5d3bb855ef38d9c2d`，均与旧提交一致。
   这是提交归档字节证据，不是旧版本部署或该版本使用新锁的证据。
6. `git diff --check`：PASS；临时归档/本地证据只在 ignored `.dev-runtime/` 与测试临时目录，未提交秘密。

## 未执行与 Gate 2 / Release 边界

- 本机 Git Bash 没有 `flock`/`sudo`，完整 Linux `scripts/test-remote-deploy-production.sh` 为 NOT_RUN。
  新增真实 flock 持锁/第二调用退出75/零Docker与current不变回归，沿用原受保护隔离 Linux fixture；
  必须由独立 Linux/现有 CI 完成，不能把 Windows 模拟写成真实锁通过。
- Linux pwsh、SSH/SCP实际服务器、真实镜像构建、Migration、容器/公网健康和生产部署均 NOT_RUN。
- Gate1本地适用验证通过，独立 Gate2/精确CI与实际生产接续仍待完成；当前未合 dev/main、未触发 Deploy。
- 此工程只改变发起端，服务器仍按原Dockerfile构建；不承诺修复依赖安装耗时。
- 回退工程入口须重新核对服务器无部署持锁，保留新锁/现有备份、Schema、资产、当前和回滚release。
  恢复自动CD必须是显式评审变更，不能临时把两套入口同时自动开启。
