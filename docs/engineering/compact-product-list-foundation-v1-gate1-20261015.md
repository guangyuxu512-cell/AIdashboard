# 共用紧凑列表基础 V1 — Gate 1

## 范围与依赖

- Owner：81a1；分支 `feat/compact-product-list-foundation-v1`。
- 创建基线：精确 Green `9bb64ac76bf9e0f51fb1715517cf8c18cef63e22`。
- 正常 no-ff 同步资源登记 `5a27a562ae652a774325e99ec66f3fd942e550a2`；它不是新 Green。
- 原候选池分支 `feat/product-selection-candidate-result-filters-v1` / `bfaae14d76780f031e34ef68b139a26bb19b8694` 保留。共享分支不合入该分支或 7d55 业务。
- 本阶段仅共享尺寸能力及已审核的最小前置。之后正常 no-ff 合回原候选池分支，候选池显式试点另交精确 Candidate。用户原生确认前不扩展策略列表或商品数据页面。
- 不连接数据库、不启动 Backend、不修改 Schema/Migration/API/Electron/依赖。已有 Feature 0046 保持不动；本分支代码 Head 0045 不表示降级数据库。

## 已审核前置复用（普通同路径提交，不 cherry-pick）

逐文件来源：`bfaae14d76780f031e34ef68b139a26bb19b8694`，原始商品组件来源 `b364a89a9955ffe4aae1c3fb6dbfcabfd0dedf8f`，并保留 9734809 对已安装 Naive 2.45 Ellipsis 点击问题的 NTooltip 兼容、f876f83 的长标签修复。

| 路径 | 用途／默认边界 |
| --- | --- |
| `frontend/src/shared/ui/AppSelect.vue` / `.spec.ts` | 长标签 Tooltip 显式 opt-in；默认 false，自定义 renderer/tag/关闭回调不变 |
| `frontend/src/entities/shop/ui/ShopSelector.vue` / `.spec.ts` | clearable/labelTooltip 默认 false 的透传，不改变店铺查询与授权 |
| `frontend/src/entities/product/index.ts`、`ui/ProductImage.vue` | 公共商品图片；summary 80、thumbnail 64，contain/lazy/no-referrer/preview/retry 保留 |
| `frontend/src/entities/product/ui/ProductInfoCell.vue` / `.spec.ts` | 单行标题、原始字符串 ID／缺失保护／固定复制槽；Entity 不反向依赖 Feature |
| `frontend/src/features/product-selection/ui/ExternalProductImage.vue` / `.spec.ts` | ca97 明确批准的唯二 Feature 例外：既有图片薄兼容转发，去掉重复实现；不带任何业务代码 |

前置定向实际验证：`pnpm exec vitest run src/shared/ui/AppSelect.spec.ts src/entities/shop/ui/ShopSelector.spec.ts src/entities/product/ui/ProductInfoCell.spec.ts src/features/product-selection/ui/ExternalProductImage.spec.ts` — 4 文件、20 项通过（2026-10-15）。这不是紧凑模式或 Electron 验收。

## 后续验证

显式 compact API、实际文件白名单、父主题不可变／Teleport／默认消费者／详情隔离结果在共享封存前补齐。本阶段未通过 Gate 2、未合 dev/main、未发布；唯一 Integration Electron 与真实 basic_info 验证仍由 ca97 独立负责。
