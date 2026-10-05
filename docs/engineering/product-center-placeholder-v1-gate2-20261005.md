# Product Center Placeholder V1 — Gate 2

日期：2026-10-05。Integrator：ca97。状态：Gate 2 PASS；精确 dev CI / Main Release Gate 后才能发布，尚未标记 DEPLOYED。

## 版本与范围

- Green 基线：`afec237435dabc3e086b9b515f28986876f6fcbd`；审查时 local dev = origin/dev，工作树 clean。
- 最终 Candidate：`99e7711693b99d6128b05fe6952cc1f81f2996f9`，Feature `feat/product-center-placeholder-v1`，origin 与 Feature HEAD 一致。
- 正常 `--no-ff` Merge：`c5ddd54d89961f5a99e15601438a2ccdac18e0c6`。无冲突，合并业务树与 Candidate 完全相同；本收尾仅增加工程记录。
- 发布范围：商品中心页面骨架、三个 framed 切换项；共享禁用 primary 按钮配色；隐藏独立资料库导航。UI_ONLY，商品业务未接入。
- Backend 仅现有 ModuleCode 登记 `product-selection` / `product-library`，复用现有授权服务；无新增 API、权限框架、Schema、Migration、Worker 或 Electron 壳修改。
- 字段、选品策略执行、采集回流和其他功能不进入本轮；不把字段核对作为本轮发布等待条件。

## 人工证据

用户针对最终 Candidate 明确确认：商品中心及三个切换项正常，独立资料库入口已隐藏，无其他问题；保留此前 `8645d5a738474de58130cfc5f2d21ddb64ecd2d5` 的 A/B 有效验收。

唯一开发 Electron 标题“电商 AI 中控台”，原有 Integration 超级测试账号会话，`http://127.0.0.1:5180/#/product-selection`。Frontend 来自 81a1 最终 clean Candidate，Backend app-dir 为同一候选；运行树与合并树业务源码相同。Real 同源链路 `5180 → 8100 → control_center_integration`，Vite strictPort。原生截图/坐标输入捕获限制单独记录；用户实际操作确认不是浏览器 Mock 截图替代。

## 合并后复验

| 验证 | 结果 | 证据边界 |
| --- | --- | --- |
| Backend 完整默认 pytest | 504 passed / 76 integration deselected | 合并后的 ca97 源码；不把 deselected 记为通过 |
| Frontend lint | PASS | 合并源码 |
| Frontend 完整 unit | 128 文件全部 PASS | 合并源码；原有 jsdom stderr 非失败，退出 0 |
| Frontend typecheck + production Real build | PASS | `pnpm build` 内含 typecheck；原有大 chunk 警告保留 |
| Registry、Guard、Asset、Human Auth、授权弹窗定向 | 11 文件 / 42 passed | Integrator 在最终 Candidate 预审执行，业务树等同合并树 |
| Product / Assets / AI Assets Playwright | Owner 8/8 PASS | Mock/Visual，复用精确 Candidate Gate 1 证据，不冒充 Real 权限 |
| Disabled primary / product framed Playwright | Owner 四主题 10/10 PASS | 本地 Mock 与 HTTP 完整拦截，零真实生成；保留 A/B 记录 |
| `git diff --check` / 范围 / 本地材料 | PASS | 无新增 Migration/依赖/桌面/Worker；已跟踪本地 env/runtime 0，新增敏感模式匹配 0 |
| Alembic heads / Integration revision | 单一 `20260924_0041` | 只读核验，不执行 Migration |

### 真实 PostgreSQL + API 定向验证

真实 Integration 数据库、local 隔离存储。使用既有正式 Service 初始化固定标识 `stage-2a1-product-center-20261005` 的专用 Team / 普通成员；该成员随机测试凭据仅留内存，通过真实 `/auth/login`、HttpOnly Cookie 和 5180 同源代理调用 API，不注入 Token，不改现有用户或 Team 权限。管理 Service 按真实已启用 Integration 超级账号 Actor 记录审计；不将 Service fixture 冒充管理员 HTTP 登录。

1. 数据库真实超级账号启用且 `is_super_account=true`；既有模块与两个新登记值均可解析。
2. 普通成员未授权：module-access 返回空，Asset API 403。
3. 为专用 Team 授权 asset 与两个新模块：PostgreSQL 读回一致；旧会话失效 401；正常重新登录后 module-access 返回精确授权集合，Asset 列表 200。
4. 正式上传最小合成 PNG，原图 API 字节与 SHA-256 一致，thumbnail 返回真实 WebP；DTO 无 storage_key/provider_url。
5. 移除 asset / product-library，仅保留 product-selection：旧会话再次失效，重新登录读回唯一授权值；原图 API 与普通成员管理 API 均 403。
6. 按稳定 ID 删除本次图片，通过正式 Service 将专用成员移出并停用、清空 Team 授权并归档；审计及历史成员记录保留，无活动测试资源。既有人工验收夹具不动。

独立管理员 API 登录探针发现受保护的旧本机凭据返回 401，未重置超级账号或影响 Electron 当前会话；改用上述明确标注的正式 Service 测试夹具。此环境证据不被描述为管理员 HTTP 登录成功。

## 发布交接与恢复

- 用户已授权本轮集成收尾、推送精确 Green dev、CI 后交原“主分支”会话按 Release Gate 发布，并要求实际 main SHA、部署与生产核验结果。
- 必须前后端同版本交付（或 Backend 先），再按需要分配普通团队两个新模块；不自动扩大生产团队权限。
- 隐藏导航不撤销 asset 授权，不删除 `/assets`、内容/缩略图 API、AI 素材库、业务素材选择与存储。
- 无迁移，生产应保持单一 0041 Head。Electron 未改，无需新增安装包。
- 共享历史恢复使用 revert；若回退到不识别新模块值的 Backend，先经正式授权入口撤回已分配的新值，避免旧枚举读取失败。不得直接改生产表。
- 发布后只由正式 Main/Release 环境核验实际运行 SHA、健康、Real 模式、商品骨架和隐藏导航；不能以 CI 或 Main 合并单独认定 DEPLOYED。
