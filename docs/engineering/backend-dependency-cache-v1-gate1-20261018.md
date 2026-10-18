# Backend Dependency Cache V1 — Gate 1

## 目标与精确范围

- 分支：`feat/backend-dependency-cache-v1`，独立工作树沿用 `local-ssh-production-deploy\中控台`。
- Green基线：`6f795620202e95cb9aecb9e1e92bb44edd604103`；旧SSH CD分支/候选/PR14证据保留。
- 仅 Backend Dockerfile 的依赖分层/cache、原container-runtime build步骤及真实构建回归与工程文档。
- 不改 `pyproject.toml`、依赖版本/源、业务/数据库/API/Electron；无DB/端口/Migration/第二Electron。
- 不连接生产，不影响正在进行的 `8f2747400ad0bfacafa4343fe27d3b186274aa99` 发布或远端缓存/配置。

## 变更

先COPY唯一权威 `pyproject.toml`，Python3.12 tomllib读取11项project.dependencies与声明的
`setuptools>=75` build-system.requires，交给原pip处理。下载使用现有BuildKit的pip cache mount，
不新增requirements、依赖、镜像源、builder或Dockerfile frontend下载。
再COPY原Alembic/migrations/app，项目自身用 `RUN --network=none` + `--no-deps --no-build-isolation`
安装。构建工具是否完整以真实冷构建与后续离线源码安装取证，不假设wheel/setuptools已在基础镜像中。
Node/vendor、权限、资产、Healthcheck、启动命令与生产SSH脚本不变。

原四CI Job保留，原container-runtime的Backend build改调一个小回归脚本：

1. 从当前提交HEAD导出Backend context，在测试机执行首次 `--no-cache` 构建并保留原CI image tag。
2. `/tmp`导入安装包并执行pip check；没有依赖下载网络的运行容器。
3. 仅在临时context新增app探针，第二构建必须依赖RUN为CACHED、离线项目RUN为实际DONE。
4. 从 `/tmp`、非root app用户导入site-packages新探针，排除cwd源码遮盖旧安装的假成功。
5. 清理只触及测试临时目录及唯一探针镜像；原CI镜像继续供既有Node/PDD验证，生产资源不在范围内。

首次测试的no-cache只用于独立CI，不进入生产入口；生产复用原PRODUCTION_BUILDX_BUILDER，源码变更
不设置cache-bust。首次下载、变更依赖/基础镜像或清缓存仍可能耗时，不能将下载根因写成已消除。

## 已执行与未执行

- 已核工作树初始干净、HEAD为精确Green6f795；当前工程文件修改范围与依赖声明零差异。
- `bash -n scripts/test-backend-dependency-cache.sh`：PASS。
- Python3.12标准库tomllib读取原manifest：11项生产依赖、build requires仅setuptools>=75。
- `git diff --check`：PASS。
- 本机未发现Docker命令；真实镜像/冷缓存/暖缓存/离线打包/容器导入：本机NOT_RUN，须以新精确PR CI取证。
- 真实服务器缓存命中/生产部署时长/平台请求/DB/Migration/原生Electron均NOT_RUN。
- 独立预审认可层顺序及证明方式；这不替代精确Linux构建、Gate2或发布。

## 风险、交接与回退

交ca97独立审核/精确CI后正常no-ff进入dev；未通过不能进入main或发布。
若声明之外的动态构建依赖在离线阶段报错，按真实日志回到正式build-system契约处理，不临时联网绕过。
更改依赖或清除builder cache会重新下载；缓存容量按既有运维规则管理，不能删运行/回滚镜像或业务数据。
工程回退可恢复旧Dockerfile，已有镜像/Schema/资产不受影响；仍按原Release Gate发布，不修改在途构建。
