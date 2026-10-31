# 软件调用店铺 Session V1（候选）

## 边界

该接口供受信任的软件后端直接调用：商品库、选品及后续软件均可独立接入，不需要 Worker、
Device、Task、影刀或设备绑定。店铺 Session 的加密原件仍由中控持有。接口不提供账号密码、
不代理平台请求，也不修改 Session。平台请求由调用软件自己执行，实际出口 IP 属于调用软件
运行所在的网络；不能因为拿到 Cookie 就宣称另一台机器一定登录有效。

每个软件使用独立的服务凭证，并显式授权具体的店铺 ID。人员登录、设备 Token、既有手机采集
凭证和 RPA 商品库凭证均不是该接口的认证方式。普通前端不能调用该接口或保存 Session。
客户端只应将结果保存在后端内存，不能写到 URL、浏览器、审计、应用日志或 Git。

## 配置与网络

默认关闭。`BACKEND_APPLICATION_SHOP_SESSION_ENABLED=true` 才启用，
`BACKEND_APPLICATION_SHOP_SESSION_CLIENTS_FILE` 指向后端进程可读、受操作系统保护的 JSON 文件。
修改开关或文件路径需重启；文件内容在每次鉴权及发送 Session 前重新读取。使用原子替换更新文件，
停用软件或撤掉店铺 ID 可阻止后续读取；不可撤销已经交付给客户端的 Session，应重新登录使其失效。

JSON 契约：

```json
{
  "version": 1,
  "clients": [
    {
      "client_id": "product-library",
      "token_sha256": "REPLACE_WITH_64_LOWERCASE_HEX_CHARACTERS",
      "authorized_by_user_id": "00000000-0000-4000-8000-000000000001",
      "enabled": true,
      "shop_ids": ["00000000-0000-4000-8000-000000000002"]
    }
  ]
}
```

以上均为不可使用的示例。`authorized_by_user_id` 必须是实际启用的中控超级账号，该账号被停用或
失去超级账号身份时读取即失败。文件由有权管理员部署，客户端的独立 Token 应用
`secrets.token_urlsafe(32)` 等加密随机源生成；配置文件保存其 SHA-256 摘要而不是 Token，
客户端单独安全保存明文 Token。不得提交真实配置文件或 Token。每软件指定不同 Token，
不得复用既有服务凭证。客户端 ID 唯一，店铺列表显式列出，不能使用通配符。配置格式错误时拒绝服务。

必须经过可信 HTTPS。应用仅在 ASGI `scheme=https` 时接收凭证，**不会**自行信任外部传来的
`X-Forwarded-Proto`。如 TLS 在反向代理终止，ASGI 服务器的代理信任名单只能包含受控代理；
后端监听端口不得绕过代理直连。应限制服务网络访问，验证证书并保持默认关闭直至联调和安全审查通过。

## HTTP 契约

每次调用携带 `X-Application-ID: <client_id>` 与 `Authorization: Bearer <独立服务Token>`。
不发送 Worker 标识或任务 ID。所有 ID 为中控稳定 UUID，错误按现有 `AppError` 契约返回。

| 方法与路径 | 作用 |
| --- | --- |
| `GET /internal/applications/v1/shops` | 返回该软件授权且启用的店铺：`shop_id`、`display_name`、`platform`、`session_status`；状态来自中控存档，不代表平台实时在线。 |
| `GET /internal/applications/v1/shops/{shop_id}/session` | 返回一店的 `shop_id`、`platform`、`session_version` 和 Cookie 数组。成功响应 `Cache-Control: no-store`。 |

读取前检查软件凭据、店铺授权和授权人，锁定授权人/店铺/Session，并验证存档平台店铺身份；
缺失、失效或身份不一致的 Session 不返回。`captured`/`valid` 仅表示中控保存状态，
是否仍被平台接受需要实际请求才能判断。过期时间按既有 Session 策略处理，不推断平台状态。
敏感读取先提交数据库审计再返回；审计主体类型是软件，记录软件 ID、授权管理员、店铺 ID 和版本，
不记录 Token 或 Cookie。审计提交失败时不会返回 Session。

## 明确未完成

此候选只提供读取 Session 和店铺清单，不提供签名服务、抖店预检、平台请求、商品库接入或
批量预检。现有中控签名器的离线样例只能说明代码可生成测试签名，不能证明真实店铺 Session
在 NAS 及抖店平台有效。签名器在商品库运行环境的部署方式、真实请求、访问代理/TLS 的配置、
并发/限流和版本兼容都须继续验证。本候选默认关闭，未生产部署；无 Schema 变更。
