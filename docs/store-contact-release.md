# 联系店长：门店配置上线步骤

1. 后端更新前备份数据库，按现有 Alembic 部署流程执行 `alembic upgrade head`，新增 `store_contact_settings` 表。
2. 部署后端与管理后台，在「联系店长」选择各门店，分别上传二维码。旧全局海报保留，不自动分配给任何门店。
3. 确认门店经纬度准确，微信后台定位用途声明与功能一致，图片域名允许下载。
4. 发布小程序前真机验证：授权定位、拒绝定位、手动切店、快速切店、入座订单进入、未上传二维码、保存图片。

本地验证：`node miniprogram/tests/contact-selection.test.js`；后端目录执行 `python -m scripts.test_store_contact`；管理后台执行 `npm run build`。
