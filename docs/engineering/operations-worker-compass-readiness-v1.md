# Worker 罗盘会话状态

Worker 0.5.10 通过 RPA 本机桥接的 `compass_status` 读取指定店铺已加密快照的罗盘验证标记，并在设备清单中以可选 `compassSessionVerified` 上报；不传输会话内容。状态只对应本次快照，读取前后快照变化时不报告结果。旧 RPA 不支持时为未知，普通商品预检继续使用原有状态和权限。

中控 `GET /api/v1/devices/{device_id}/local-shops` 返回可选 `compass_session_verified`，供运营中心挑选已验证过罗盘身份的店铺。该值不保证平台当前会话有效；实际失效仍由 Worker 的平台响应确认。先发布兼容中控，再发布 Worker，最后更新 RPA 和运营中心。无 Migration。
