# 商品数据 Green 同步与前端交接

2026-10-16，Owner 7d55，交接 ca97。原分支 feat/shop-product-data-frontend-v1 正常合入
ca97核定的Green 5a18bd0390cb4b8cbed637d412f7482cefff3f36，保留03bdc0238465bcad79701af02c04b9811f96a51b
及原Gate 1、Radio失败/修补、Mock与全部截图。新完整Candidate为包含本记录的Feature HEAD，
完整SHA由回执及本地preview manifest记录。前端UI_ONLY边界不变，禁止发布。

## 合并与范围

正常no-ff提交为7afc58f4c9ffad4e6952fa03c1d097143a24dd28，双父为
03bdc0238465bcad79701af02c04b9811f96a51b / 5a18bd0390cb4b8cbed637d412f7482cefff3f36；无冲突，
未rebase/reset或挑拣提交。旧Feature与Green的共同祖先为纯共享1a8078d。

商品数据页面、ViewModel/Mock/API factory、商品实体、Shared/主题/店铺选择器运行代码相对03bd逐字不变，
原141fec65 Radio修补仍保留。默认20/页、列宽304、列表48px/12px/28px及详情64px均未重开发。
Backend/迁移相对Green无差异；已有0046源代码仅随Green继承，不运行Backend、不连接或升级任何数据库。

唯一测试适配：旧跨模块图片回归仍断言候选池缩略图64px，而Green候选池已显式compact为48px。
将该测试名称与两处尺寸期望同步至Green既有48px，详情summary80断言保留；不改候选池代码。
商品数据详情64px由本页边界回归单独验证，不能与选品summary80混为一谈。

## 必要增量验证

- 商品数据View/Table/数据源定向3文件16项PASS，覆盖默认20/条数切换、分组/草稿、列顺序、
  主题边界及Real接口未接入的禁止写入/不回退Mock。
- 本页compact与主要流程浏览器13项PASS，0失败/skip/flaky：三视口、四主题/Radio、
  teleport菜单、分页、默认弹窗/详情及跨页恢复、分组/排序/字段保存/错误恢复、图片调用。
- lint、vue-tsc typecheck PASS。新Candidate提交后执行精确Real production build，结果见回执/manifest。
- 原03bd的39项/19浏览器、原4项Radio修补与2/18/98位字符串复制证据按未变代码继续保留，
  不把它们计为本次重新执行，不重跑无关Backend/PG/全量历史。

本轮浏览器报告/截图：frontend/test-results/product-data-green-sync-20261016/，已忽略。
旧product-data-compact-v3失败报告及product-data-compact-radio-final通过报告均在原位置。
列显隐/顺序偏好不清除；Mock仍使用原店铺夹具及product-selection/fixtures/photos图片。

## 预览与接续

端口先核为空后，仅用本树正常Vite入口恢复127.0.0.1:4177，显式Mock/strictPort，实际PID32552。
地址：http://127.0.0.1:4177/#/product-data 。重开前旧PID104760已不存在，没有关闭或替换其它进程。
最终Candidate HEAD、Vite实际模块/Mock模式与关键文件blob在交付时再核对并写入本地manifest。
不占5180/8100、不启动Electron，不操作生产客户端/Profile/Session或共享stash。

ca97据新Candidate准备唯一Integration的受控Mock/native预览；本轮未执行Gate 2或新增人工确认，
真实Integration Electron/系统剪贴板及新Real浏览器未覆盖。商品数据真实后端仍未接入，
契约盘点独立只读，不新增字段/日期请求/API/DB/迁移/调度/飞书，也不实现占位商品库。
状态为“待集成及用户验收，禁止发布”，不将生产选品或cleanup的既有状态外推到本模块。
