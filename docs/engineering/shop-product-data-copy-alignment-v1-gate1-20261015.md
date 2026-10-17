# 商品数据 ID 复制按钮对齐 — Gate 1 / Handoff

2026-10-15，Owner 7d55；沿用 feat/shop-product-data-frontend-v1，在
7954c434edcfd8dd14ad15d7a8a2ee67899087e8 后追加正常提交，不改写旧候选。
功能 Green 基线仍为 9bb64ac76bf9e0f51fb1715517cf8c18cef63e22。
新候选为包含本记录的 Feature HEAD，完整 SHA 由回执与本地 preview manifest 记录。

本轮只处理用户追加的“每行复制按钮横向对齐，不随 ID 长度漂移”。用户此前对当前视觉的认可
不代表该改动、原05f候选或整个商品数据模块已经人工验收通过。

## 原因与最小修改

- 原 ID 行使用 flex，文本取自身内容宽度，按钮紧跟文本末尾；短 ID 与长 ID 的按钮位置不同。
  在未改展示组件的7954源码上，混合长度的三视口新断言全部失败，已保留复现材料。
- 复用 ProductInfoCell，将 ID 行改为紧凑两槽 grid：文字槽最多 --field-width-sm（160px），
  间距 --space-1（4px），复制按钮独立使用 --control-height-compact（30px），总宽最多194px。
  容器更窄时仅文字槽收缩，按钮不缩小；没有撑到整个商品信息列的最右端。
- ID 仍独立一行、保留 ID：前缀和原辅助字体；复用 NEllipsis 省略与溢出悬浮全文，
  contentStyle 仅限定全文提示宽度并允许长字符串折行。复制调用链不变，只写入原始字符串。
- 商品标题继续单行省略与悬浮全文，图片64px、行高、列配置、字体/Design Token定义均不变。
- 为可复验增加显式开发 Mock 场景 mixed-ids：前3条为2位、18位、98位字符串。
  默认样本不变；仅 DEV + Mock 入口允许启用，Real 仍明确未接入、无Mock回退。

无新增依赖或基础控件；不改候选池布局、共享ShopSelector、Backend/DB/Signer/Migration、
Worker/Electron，不启动第二套服务或Electron。测试只复用7d55已登记的4177 strictPort。

## 实际验证

以下坐标来自真实 Chromium 页面测量，不是 jsdom 或CSS推断；每个视口同时展示三种长度。
坐标以各视口页面左边缘为0；同一视口三行差值均为0px，跨视口页面本身位置可以变化。

| 视口 | 短 / 18位 / 98位按钮左坐标(px) | 文字槽 / 按钮(px) | 行高 / 图像(px) |
| --- | --- | --- | --- |
| 1024×768 | 557 / 557 / 557 | 160 / 30 | 81 / 64×64 |
| 1440×900 | 561 / 561 / 561 | 160 / 30 | 81 / 64×64 |
| 1920×1080 | 568.40625 / 568.40625 / 568.40625 | 160 / 30 | 81 / 64×64 |

三处均验证18位字符串完整显示、98位省略并悬浮显示全文，提示层不越出视口；
分别实际点击三行复制按钮，再调用浏览器剪贴板回读，与2/18/98位原字符串完整一致，
不包含前缀、不发生Number转换。标题仍为1行，页面无横向溢出。
列配置360px不变；1920视口的既有表格剩余空间分配仍使实际商品列约420.61px。

额外压力用例只在测试DOM中将三行ID容器约束为140px，不改变产品表格列配置：
文字槽缩至106px，按钮仍30px且全部可见/对齐，页面无溢出。
此项是隔离的容器压力测试，不冒充用户实际窗口操作。

- 定向 Vitest：5文件 / 25项 PASS（展示组件2、数据源5、商品页8、候选池7、候选详情3）。
- Mock Playwright：9项 PASS（混合ID三视口3、标题三视口3、既有流程/图片/错误恢复3）。
  另重跑混合ID三视口3项 PASS，等待提示动画完成并保存清晰截图。
- lint PASS；build内vue-tsc typecheck PASS；production Real build PASS，既有大chunk警告保留。
- Real产物86个JS资产扫描：商品Mock、演示ID/分组及mixed-ids场景标记命中0。
- 本轮未重跑最初05f阶段的692项全量测试；也未重跑Real浏览器或真实Integration Electron，
  不把历史05f的Real边界浏览器1项当作本候选新证据。
- 中途首次typecheck发现tooltip对象的style不属于PopoverProps，按已安装库声明改用
  contentStyle后上述检查通过；未使用类型断言绕过。截图等待提示动画完成，避免截图时序遗漏。

命令：

    pnpm --filter @control-center/frontend exec vitest run src/entities/product/ui/ProductInfoCell.spec.ts src/features/product-data/api/product-data-source.spec.ts src/features/product-data/ui/ProductDataView.spec.ts src/features/product-selection/ui/CandidatePool.spec.ts src/features/product-selection/ui/CandidateDetailDrawer.spec.ts
    pnpm --filter @control-center/frontend lint
    pnpm --filter @control-center/frontend build
    pnpm --filter @control-center/frontend exec cross-env PRODUCT_DATA_REUSE_PREVIEW=1 playwright test --config playwright.product-data.config.ts --output=test-results/product-data-id-alignment-v1-final
    pnpm --filter @control-center/frontend exec cross-env PRODUCT_DATA_REUSE_PREVIEW=1 playwright test --config playwright.product-data.config.ts e2e/product-data-copy-alignment.spec.ts --output=test-results/product-data-id-alignment-v1-display

## 预览与证据

- 日常Mock预览：http://127.0.0.1:4177/#/product-data
- 混合ID预览：http://127.0.0.1:4177/#/product-data?productDataPreview=mixed-ids
- 同一既有Vite进程、同一工作树，Profile与其他工作树环境未动。
- 最终清晰截图在 frontend/test-results/product-data-id-alignment-v1-display/（本地忽略）：
  - product-data-copy-alignmen-df85c-uct-ID-copy-buttons-at-1024/copy-alignment-1024.png
  - product-data-copy-alignmen-64f05-uct-ID-copy-buttons-at-1440/copy-alignment-1440.png
  - product-data-copy-alignmen-376f4-uct-ID-copy-buttons-at-1920/copy-alignment-1920.png
  - 同目录有 copy-alignment-full-id-<视口宽度>.png，显示完整超长虚构ID。
- 原复现 product-data-id-alignment-before/、中间回归及此前标题证据均保留，不提交截图/build。
  样本均虚构，无Token/Cookie/真实凭据。

## Gate与停止点

Gate 1：PASS，仅上述前端追加范围。ca97新候选Gate 2、真实Electron与本改动用户人工验收：未覆盖。
ca97应核对精确候选、当前Mock预览及三视口证据，保留之前视觉，不混81a1选品功能。
本Owner只提供版本化交接材料与本会话回执，由规划协调ca97；不据其他任务消息自行跨会话发送。
无合dev/main、部署、安装包或生产改动。保持“待用户验收，禁止发布”。
