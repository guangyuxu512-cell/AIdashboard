# 商品库预检材质和图片规则 Worker 交接

- 基线：Green dev `77f4a6e3a3a5179706e1d861200d36c9b4e5486c`。候选为本分支的 `douyin.category_schema` 能力修复；不改变任务、结果信封或 Worker 运行时版本。
- 依据：用户打开的抖店发布页当前 schema 模型，类目 `1000010274` 的属性 `785` 的度量模板含 250 个 `value_options`；同一模型的 `category_property_pic.items` 中含对应的“水洗标/吊牌图”规则，该项为非必填。另观察到图片变更触发 `single_property_refresh`。这里记录的是页面运行模型，尚未抓取原始 HTTP 响应或做真实识图请求。
- 修复：在既有嵌套白名单中保留 `value_options`，只保留选项的已允许字段。按属性 ID 附加可见、有效且无歧义的 `property_picture` 定义，保留名称、提示和必填状态，不回传图片值、事件、商品原包或店铺凭据。旧结果信封不变；旧商品库忽略新增字段。
- 验证：`worker` 目录执行 `python -m pytest tests/test_douyin_precheck_capability.py tests/test_direct_precheck_delivery.py`，30 项通过。新增用例覆盖选项、图片规则、隐私字段剔除、隐藏项与重复 ID。尚需 Gate 2、签名能力包发布及执行设备实际更新，并用真实平台 schema 验证完整链路。
- 数据库、Migration Slot、端口：无。回滚：发布上一版已签名能力包；保留现有 Worker 身份、店铺资料和任务。不能把代码测试或能力包生成当作设备已更新。
- 后续依赖：商品库需要解析 `property_picture` 并处理属性图片保存；独立 RPA 需要读取和上传保存的图片。平台识图调用及其准确性尚未实测。

## 完整类目树及兼容

- `POST /internal/applications/v1/worker-prechecks` 的 `input.full_category_tree` 是可选严格布尔值，默认 `false`；只有 `operation=tree` 可设为 `true`。旧中控会返回 422，调用方不得将其视为有效空结果或缓存。新中控找不到支持完整类目的设备时返回 503 / `PRECHECK_UNAVAILABLE`。
- 商品库属性查询与自动预检使用 `input.require_schema_metadata=true`（严格布尔，仅 `operation=schema`）。该请求同样仅分配能力至少 `2.0.1` 的设备，且签名时再次核验；旧中控返回 422、没有兼容设备返回 503。未显式要求时维持旧预检行为，不把旧能力结果写入新版属性缓存。此标记保证能力会保留平台返回的材质选项和图片规则，不表示所有类目一定包含这些字段。
- 完整树请求仅分配给 `douyin.category_schema >= 2.0.1`，任务内部冻结完整树标记，签名时再次核对设备能力并使用 `display_all=1`；设备降级或能力缺失时明确失败，绝不改回部分树。旧请求仍使用 `display_all=0`，旧能力继续服务旧请求。Worker 同时接受 0/1，保留平台的 `enable`、`industry_status` 原值及原有输出信封。
- 已观察 HuanYu 父类目 `1000005081` 在 `display_all=0` 时返回 7 项，在 `display_all=1` 时返回 14 项，包括 `1000011128`，其 `industry_status=2`。这代表该店未开通，不推断其他店的状态。
- 本次无 Migration，不变更 Worker 底座和店铺资料。先发布兼容的中控，再签名发布能力包 `2.0.1` 并核实设备实际加载，最后由商品库切换显式完整树请求和缓存版本。
- 回滚能力包须使用递增序号的新签名清单引用上一版内容；不能重发较低序号的旧清单。回退中控前必须先关闭商品库的完整树与属性规则标记，否则旧接口将返回 422。
- 定向检查：Worker 类目、直传、能力更新和并发回归通过；Backend 完整树契约、旧类目契约、直传、设备范围、上下文及纯算签名共 27 项通过。新增 PostgreSQL 集成用例覆盖旧设备拒绝完整树、旧请求不变、新设备完整树及任务领取后设备降级。该 PostgreSQL 用例须在 CI / Gate 2 继续验证。
