# Skill 执行规范

一个 Skill 表示一个明确可执行能力。

例如：
- douyin.publish_product
- douyin.fetch_orders
- douyin.refresh_session

统一输入至少：
- task_id
- skill_id
- params

需要店铺时再包含：
- shop_id
- runtime context

统一输出：
- status
- result
- error_code
- error_message
- artifacts

Runtime 到 Executor 映射统一维护。
禁止在 Skill 内重复实现 subprocess、timeout、log capture、cancellation。
