# Worker 类目预检纯算签名

`BACKEND_WORKER_PRECHECK_PURE_SIGNER_ENABLED` 控制 Worker 类目预检签名：默认 `false` 沿用原有服务，设为 `true` 时在中控进程中使用之前商品库的 Python 纯算实现。改动只影响此受限接口，不修改 Worker、店铺 Session、平台请求或任务授权；回退时设为 `false` 并重启 Backend。

纯算实现来自商品库 `eaae070`，许可证见 `app/integrations/douyin_signer/LICENSE.pure_signer`。对当前预检的 GET 与 POST，签名使用最终请求的编码查询串和 UTF-8 正文字节；已保存的 `msToken` 沿用原值，缺失时不构造新的 token。签名计算不访问网络，不记录会话、正文或签名。

离线测试和模拟平台链路不能证明平台当前接受该签名；发布核验须结合实际平台业务响应，不以 HTTP 200 或签名生成成功替代业务成功。
