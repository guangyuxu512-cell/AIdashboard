# 候选池默认每页20条 — 最小增量交接

人类原始消息 `01a13e9d-2daa-71d3-ad2c-dd136d2f8108`（规划turn `01a13e9c-74c8-7950-873a-8c6e7aa0b9f8`）按上下文为每页20条，不是20个分页。沿原Feature、父候选 `38e9abfe9484aa194c37608101e338276cface1f`；开工干净，已确认前端视觉不修改、不重复验收。

## 核验与必要变化

- 旧实际初始值为 `model/candidate-query.ts` 的fallback10，序列化也以10为省略值；旧截图显示20/页不能证明默认20。
- 只在该候选池模型定义私有默认20，同时用于解析／序列化。无 `candidate_size` 或无效值时20；URL有效显式10／20／50／100不覆盖，非默认值保留在URL，重载能回读。
- 仓库当前候选池没有独立localStorage/sessionStorage分页偏好；无清存储／重置旧偏好操作。不改全局分页组件、选项、Token、策略或店铺页默认。
- 定向验证发现同页跳转到越界URL且服务端校正页码与上次相同时，旧watch仅监听页面数字不触发，URL残留99。仅把既有校正watch监听源改为本次响应对象，再读取其page；保留原权限／查询／页码赋值路径，不加状态层。已在实际Mock验证50条／page99校正、重载保持50条。
- 商品库仍占位，只在前端契约登记未来正式列表默认20，不造页面。商品数据由7d55按ca97独立纯共享1a依赖接入，不合整条选品0046；本Owner不改其文件。

## 实际验证

- `pnpm exec vitest run src/features/product-selection/model/candidate-query.spec.ts src/features/product-selection/ui/CandidatePool.spec.ts --maxWorkers=2`：2文件14项通过（7.38s）。默认／无效值20、显式10/20/50/100与筛选排序页码round-trip、组件实际向service传20、默认20行与第二页首项020、原选择／失败行为覆盖。旧010断言按新20条正确同步，不改变夹具。
- 受影响eslint与当前`pnpm typecheck`通过；`git diff --check`通过。
- `pnpm exec playwright test --config ../.codex/selection-product-info-mock.config.ts --grep 'candidate fresh default is 20' --output ../.codex/candidate-default20-fixed-20261015 --reporter=line`：1项通过（9.0s）。全新入口20行／20每页，第二页12行；切10回第1页并重载保留10；显式50／越界页校正后重载仍32条全部结果且保持50每页。首次运行暴露上述校正watch边界，修复后通过，不隐藏失败。
- 既有十行视觉用例只显式指定 `candidate_size=10` 保留其原场景，避免用默认值变化重做布局；本轮未重跑旧整套视觉／699／后台／平台。已同步其分页假设但不称全部历史场景通过。
- 38候选已确认的三列／居中／竖线／图片／字体／行高／详情完全不变；Shared、entities、Backend、Electron、Worker、依赖、0046相对38零diff。无数据库连接或平台请求。

精确新Candidate随提交推送交ca97；Root仅必要增量／一次匹配Real构建后更新同一5180／Electron，保留登录、Profile、数据与已有显式选择，不再请求整体视觉批准。当前新版本未加载／Gate2未完成，不部署。独立真实basic Gate仍未完成，本分页增量不代表整个选品任务或商品库完成。
