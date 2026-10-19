# 超级账号业务团队上下文热修 Gate 1

2026-10-19，Owner：规划会话。分支 `hotfix/super-account-team-context-v1`，独立工作树
`C:\Users\Administrator\.codex\worktrees\super-account-team-context\中控台`。
从精确 Green `9fa43fac5eb8ccf41e8d9bc669cac5866c5a26d5` 创建，正常 no-ff 合入图片格式
Green `5110a613c0d24818daf4918803aff1be887cbb06`。精确 Candidate 以交接 SHA 为准；本记录不是 Green 或生产发布。

## 根因与范围

用户在默认团队能列出 shopee 的“70收纳柜”，上传成功后关联却返回
`PRODUCT_MATERIAL_GROUP_NOT_FOUND`。共用 `DataScopePolicy` 对带具体 Team 的超级账号仍跳过过滤，
而素材组写入要求相同 Team；读写范围不一致。菜单还缺少返回无 Team 全局上下文的入口。

仅共用 Team-owned SQL 规则、现有人员菜单/上下文及 AI 只读交互修补；不新增角色、DTO、错误码、
API、Model、Schema、Migration、依赖或 Electron 代码。不迁移历史素材，不给默认团队额外权限。

- 超级身份与公司公共店铺、设备、人员/授权管理权保留，不把业务 Team 选择伪装成普通成员身份。
- 无 Team 为“全部团队”，可跨团队浏览；具体 Team（包括默认团队）按同一 SQL 谓词限制素材、
  模板、生成记录、通用 Asset、参数预设、Task、Schedule 的列表/计数/详情。普通成员隔离不变。
- 已保存选品策略/Run 的明确资源 Team 例外保持，不改选品和经营平台取数。
- 用户菜单可从任一团队返回“全部团队”，即使只有一个团队；清除该用户 Team 偏好，HTTP 移除旧 Header。
- AI 全局浏览禁止新建/上传/编辑/启停/删除/生成/重试，保留预览下载；明确提示先选团队。
- 切换清除旧 Query/草稿及素材、模板编辑弹窗/选择态、记录详情；重试迟到不回填新上下文缓存，上传迟到不关联新组、不在新 Team 清理原文件，明确告知原 Team 文件保留。

## 已完成自动验证

- Backend 默认全量 1076 项通过；454 integration 按原默认选择排除。原 Starlette/httpx 弃用 warning 保留，不借机改依赖。
- Frontend 最终全量 170 文件/946 项通过（122.06 秒）；新增只读组件定向 7 文件/18 项通过，
  Auth/HTTP 定向 2 文件/17 项通过。新增设置控件测试的联合类型 `props` 调用曾被 typecheck 拒绝，已改为共同属性访问并重验。
- 最终 lint、typecheck 与 Real production build 通过；保留原大 chunk 提醒。
- 最终 Real 生产产物受控浏览器 19 项通过（58.9 秒，与单元全量并行）：新增四项团队场景及原15项图片/上传回归。
  验证 default/global/shopee 往返、实际上传 Header 与组路径、单团队刷新全局偏好、全局模板/生成/重试只读、切换关闭记录详情、上传迟到无关联/删除请求。
- 独立 Feature PostgreSQL 共7项通过：新增5项真实 ASGI/授权/SQL/LocalStorage，原 Asset scope 1项，
  参数预设全局/具体 Team 1项。列表/搜索/分页总数/直接详情、上传归属、同组关联、跨组拒绝、
  原图字节回读及普通成员伪造 Team 拒绝均覆盖。
- `pnpm verify --strict` quick profile exit0，known-not-fixed=0；不是 full profile、PG 或原生证据。
- `git diff --check` 通过。首次浏览器新增模板场景发现遗漏的顶栏新建按钮未禁用，已修正，最终19项通过；
  首次本树 Verify 因尚未准备 mobile 既有 axios 链接失败，离线 frozen-lockfile 补齐缓存安装后通过，未改版本/lockfile。

关键命令（`python` 指 Owner 既有解释器；Backend 命令从本树 `backend` 执行，并以该目录为 `PYTHONPATH`）：

```text
python -m pytest tests -q
python -m pytest -o addopts= -m integration -q tests/integration/test_postgresql_super_account_team_context.py tests/integration/test_postgresql_asset_scope.py
python -m pytest -o addopts= -m integration -q tests/integration/test_postgresql_automation_parameter_presets.py::test_postgresql_super_without_team_reads_all_presets_but_cannot_write
pnpm --filter @control-center/frontend exec vitest run
pnpm --filter @control-center/frontend lint
pnpm --filter @control-center/frontend build
pnpm --dir frontend exec playwright test --config playwright.ai-images.config.ts
pnpm verify --strict
```

## 隔离与发布边界

ca97 已正式分配并独立审计 `control_center_feat_super_account_team_context`；应用角色
`control_center_dev_user`、单一 `20261017_0047`、53表、五项高权 false；受保护 ignored `.env`
及严格35433隧道就绪。新增 PG 夹具必须先拒绝其他数据库，只清理自建 UUID，并断言八表原计数保持；
旧定向夹具按自身 UUID 清理。无生产数据/会话、NAS、平台请求、付费生成、新监听服务或第二 Electron。

下一步 ca97 独立 Gate2/精确集成与 CI；真实 Integration Electron 范围按 Backend 权限契约执行，
Owner 的受控浏览器不冒充原生验收。图片格式热修单独发布，不等待本候选。
应用回退保留数据库、全部业务历史与文件；回退将恢复旧菜单/读写范围问题，不降级或清理 Schema。
