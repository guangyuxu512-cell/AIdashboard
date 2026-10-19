# 图片真实格式识别热修 Gate 1

2026-10-19，Owner：规划会话，后续由 ca97 独立 Gate 2、Main Release。
分支 `hotfix/asset-image-format-detection-v1`；精确基线为 Green
`9fa43fac5eb8ccf41e8d9bc669cac5866c5a26d5`，CI `39189092693` 四项成功。
Candidate 以正式交接 SHA 为准，不把本记录视为 Green 或生产发布。

## 问题与实证

生产请求 `75cd2fef-b9f6-486d-90cb-c441e871fac3` 在 AI Asset 上传入口返回
422 / `ASSET_TYPE_UNSUPPORTED`。用户提供的 `gambar utama_06.jpg` 为 1,579,583 字节；
PNG 签名与 Pillow 解码均确认其为 1200×1200 RGBA PNG，而非 JPEG。附件和随后桌面同名原文件
SHA-256 相同：`d2e5f018371022ae30d0f12d001fb7f5c81c162c120ac24a03399176a1843e20`。
旧版按 `.jpg` 推导 JPEG，并强制文件头和客户端 MIME 一致，使用这份原图可直接复现拒绝。

## 修改边界

共用 Asset 创建入口按已有 JPEG/PNG/WebP 签名决定真实 MIME；客户端 MIME 仅为上传提示，
不再覆盖实际内容。不一致的已支持文件后缀改为真实后缀，并校正下载文件名，文件原字节、透明度、
SHA-256 均不变；正确 `.jpeg` 名称保留，改后缀时继续保持 255 字符上限。

未知签名、非图片、未支持文件名仍拒绝；10 MiB、权限、Team/AI 引用、Storage 与删除保护沿用
已有边界。生成输出也复用同一 AssetService，无另一套上传规则。

不改 Frontend、Electron、API 字段/错误码、依赖、Model 或 Schema。Migration Slot：无。
继续使用原已分配 Feature DB `control_center_feat_ai_asset_upload_access`，单一 `20261017_0047`；
测试仅自己的 UUID 夹具和临时 Local Storage，无生产上传、NAS 写入、平台或付费请求。

## 已完成验证

- 最终 Backend 定向 63 项通过：真实 JPEG/PNG/WebP 错后缀、MIME 别名/缺失、255 字符边界、
  原图字节/哈希/缩略图、非图片和未支持格式拒绝，以及原权限与 Task 引用回归。
- 最终 Backend 默认全量：1075 passed、449 integration deselected，81.67 秒；
  仅原有 Starlette/httpx 弃用 warning，不因 warning 升级依赖。
- 独立已分配 Feature PG：7 passed，12.57 秒。包含真实 ASGI multipart 上传 PNG/WebP 内容
  但名为 `.jpg` 的请求，201、规范 MIME/名称、原图逐字节回读、缩略图和清理；原授权撤销、
  跨 Team/UUID 引用及 attach/cleanup 双向行锁回归保持通过。
- 用户原文件额外真实 ASGI + 同一 Feature PG 用例：1 passed，3.62 秒；仍用原 `.jpg` 名称和
  `image/jpeg` 请求，返回 201 / `image/png` / `gambar utama_06.png`，下载原字节不变且缩略图可读，
  测试结束仅清理自建资产及夹具。
- `git diff --check` 通过；私有原图用例位于被忽略的 `docs/_local/asset-image-format-20261019/`，
  原图、私有路径、测试产物不提交。长期 CI 回归只使用生成的无敏感图片。

关键命令（工作目录 backend，Python 为 Owner 既有 `.venv`）：

```text
python -m pytest tests/test_asset_service.py tests/test_asset_api.py tests/test_ai_asset_service.py tests/test_ai_asset_api.py tests/test_task_assets.py -o "addopts=-m 'not integration'" -q
python -m pytest tests -o "addopts=-m 'not integration'" -q
python -m pytest -m integration tests/integration/test_postgresql_ai_asset_access.py -o addopts='' -q
python -m pytest -c pyproject.toml -m integration ../docs/_local/asset-image-format-20261019/test_user_sample.py -o addopts='' -q
```

## 后续与回滚

精确 Candidate 推送后交 ca97 独立 Gate 2 / no-ff / dev CI，再交 Main 发布。
本次无新增 Renderer/Electron 操作或安装包；Gate 1 不宣称生产上传成功。
应用回退到既有 `c906710c5a3fc0d8f9e6f499965eaf7672799733` 可继续读取规范 MIME/后缀的新资产；
回退会重新拒绝错后缀上传，不降级数据库、不修改或迁移历史资产文件。
