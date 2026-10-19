# 图片真实格式识别热修 Gate 2

## 结论

- Candidate：`b22179ed13bd0ddfcb0f5dadb37f23704de15ce6`。
- 精确 Green 基线：`9fa43fac5eb8ccf41e8d9bc669cac5866c5a26d5`。
- 独立 Review：ACCEPT。上传继续只接受文件名后缀属于既有 JPEG/PNG/WebP 集合的图片；真实文件签名决定规范 MIME 和存储后缀，错误后缀被纠正，未知签名、非图片、GIF、视频及未支持文件名仍拒绝。
- 本候选不转码、不改变原字节/SHA/透明度，不扩大 10 MiB、Team/模块权限、引用、清理或 Storage 边界。
- 无 Frontend、Electron、依赖、Schema、Migration 或端口变化。

## 独立证据

- `git diff --check` 通过；Owner 工作树精确 Candidate 且干净，merge-base 精确为 Green 基线。
- Backend 定向：63 passed。
- Dedicated Feature PostgreSQL：7 passed，覆盖错误 `.jpg` 名称下真实 PNG/WebP 的正式 ASGI 上传、规范名称/MIME、逐字节读取、缩略图、清理，以及原权限和双向行锁回归。
- Backend 默认全量：1075 passed、449 integration deselected；仅原有 Starlette/httpx 弃用 warning。
- 代码审查确认正确 `.jpeg` 名称保持，错误后缀改写仍受 255 字符上限保护；客户端 Content-Type 不再覆盖实际图片签名。
- 私有用户原图和本地原图测试继续保持 ignored，未提交、未输出；Gate 2 未写 Integration/Main/生产数据库或 NAS，未请求平台或 Provider。

## 发布边界

- Gate 2：PASS，可正常 `--no-ff` 合入 `dev`。
- 合入后仍以精确 dev SHA 的完整 CI Green 为准，再交 Main Release Gate。
- 生产回退不涉及数据库或历史文件迁移；旧版本可读取新规范资产，但会恢复拒绝错误后缀上传。
