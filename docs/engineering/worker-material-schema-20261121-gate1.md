# 商品库预检材质和图片规则 Worker 交接

- 基线：Green dev `77f4a6e3a3a5179706e1d861200d36c9b4e5486c`。候选为本分支的 `douyin.category_schema` 能力修复；不改变任务、结果信封或 Worker 运行时版本。
- 依据：用户打开的抖店发布页当前 schema 模型，类目 `1000010274` 的属性 `785` 的度量模板含 250 个 `value_options`；同一模型的 `category_property_pic.items` 中含对应的“水洗标/吊牌图”规则，该项为非必填。另观察到图片变更触发 `single_property_refresh`。这里记录的是页面运行模型，尚未抓取原始 HTTP 响应或做真实识图请求。
- 修复：在既有嵌套白名单中保留 `value_options`，只保留选项的已允许字段。按属性 ID 附加可见、有效且无歧义的 `property_picture` 定义，保留名称、提示和必填状态，不回传图片值、事件、商品原包或店铺凭据。旧结果信封不变；旧商品库忽略新增字段。
- 验证：`worker` 目录执行 `python -m pytest tests/test_douyin_precheck_capability.py tests/test_direct_precheck_delivery.py`，30 项通过。新增用例覆盖选项、图片规则、隐私字段剔除、隐藏项与重复 ID。尚需 Gate 2、签名能力包发布及执行设备实际更新，并用真实平台 schema 验证完整链路。
- 数据库、Migration Slot、端口：无。回滚：发布上一版已签名能力包；保留现有 Worker 身份、店铺资料和任务。不能把代码测试或能力包生成当作设备已更新。
- 后续依赖：商品库需要解析 `property_picture` 并处理属性图片保存；独立 RPA 需要读取和上传保存的图片。平台识图调用及其准确性尚未实测。
