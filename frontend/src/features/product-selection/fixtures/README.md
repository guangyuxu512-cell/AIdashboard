# 商品照片测试夹具

仅用于 `VITE_API_MODE=mock` 的选品前端布局测试，不是中控台或抖店采集数据。
2026-10-08 从 DummyJSON 产品演示数据的前 10 项 `thumbnail` 下载原始 WebP 文件，
未生成文字 SVG、未用 AI 效果图替代商品照片，也未修改图像内容。

来源说明：https://dummyjson.com/docs/products
样本来源：https://dummyjson.com/products?limit=10&select=title,thumbnail
图片 CDN：https://cdn.dummyjson.com/product-images/

| 文件                   | 演示商品                      |
| ---------------------- | ----------------------------- |
| photos/product-1.webp  | Essence Mascara Lash Princess |
| photos/product-2.webp  | Eyeshadow Palette with Mirror |
| photos/product-3.webp  | Powder Canister               |
| photos/product-4.webp  | Red Lipstick                  |
| photos/product-5.webp  | Red Nail Polish               |
| photos/product-6.webp  | Calvin Klein CK One           |
| photos/product-7.webp  | Chanel Coco Noir Eau De       |
| photos/product-8.webp  | Dior J'adore                  |
| photos/product-9.webp  | Dolce Shine Eau de            |
| photos/product-10.webp | Gucci Bloom                   |

本地打包避免视觉验收依赖 CDN 可用性。32 条候选循环使用这 10 张照片；
照片与演示店铺/标题/统计数值不代表真实业务关系。正常夹具没有故意损坏的图片。
失败测试只在测试内将已渲染的图片源替换成异常测试域名并拦截失败，验证无系统认证 Header；
点击重试由组件重新使用原夹具图片，正常列表及业务 service 不含异常 URL。

由 Mock handler 引用，Real production build 不包含这些照片；不复用带认证的资产下载链路。
