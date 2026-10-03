# 两家公司共用小程序的门店隔离实施计划

> **供执行者使用：**按 `superpowers:subagent-driven-development` 或 `superpowers:executing-plans` 技能逐项实施；用 `- [ ]` 跟踪每一步。

**目标：**两家公司在同一个小程序里经营各自门店，后台数据隔离，预约收款与退款进入各自商户号。

**方案：**门店和管理员增加公司归属；预约创建时固定记录所属公司与收款商户配置。继续使用一个小程序 AppID、一套后端和数据库。后台所有查询与操作在服务端校验公司归属；微信支付的下单、回调、查单和退款始终使用该订单所属商户。新店开业还需要先完成独立座位图计划。

**技术：**FastAPI、SQLAlchemy 2、SQLite/MySQL、wechatpayv3、Vue 3、Element Plus、微信原生小程序、Python `unittest`、Node `--test`。

**设计说明：**`docs/superpowers/specs/2026-10-03-multi-company-stores-design.md`

## 全程约束

- 一个小程序 AppID；两家公司各使用自己的普通微信支付商户号。
- 现有门店、管理员、预约、充值和购卡订单归入原公司；余额和订单号不改变。
- 新店在座位图、后台权限、支付绑定、价格及真实退款均验收通过前保持停业。
- 新店首版只接受微信支付；老店余额、次卡、优惠券、积分和团购券不能用于新店，也不在新店发放。
- 商户密钥只保存在服务端。缺少新店支付配置时拒绝付款，绝不能回退到老店商户号。
- 顾客正常操作只看门店名称；门店详情提供资质入口；首次将个人信息提供给姐姐公司时单独告知并取得同意。
- 暂不做商家自助入驻、订阅收费、跨公司合单或权益互通。

## 重点检查

1. 后台账号修改 `store_id`、订单 ID、导出条件或网址访问另一家公司数据时，返回 403/404，不泄露数据（任务 2、3）。
2. 新店订单尝试使用老店余额、卡、券或后台模拟收款时，在扣减和履约前拒绝（任务 4）。
3. 某商户签名的支付回调指向另一商户订单，或支付金额不符时，不得记为已付或开门（任务 5）。
4. 门店以后更换商户配置，历史订单仍通过原商户退款（任务 5）。
5. 新店没有已发布座位图或已验证支付配置时，不能对顾客开放预约（任务 6 及座位图计划）。

## 文件分工

- `backend/app/models/__init__.py`、`backend/app/services/schema_migrate.py`：公司、门店、管理员、订单和顾客授权记录。
- `backend/app/api/deps.py`、新增 `backend/app/services/company_access.py`：登录后的公司身份及资源授权。
- `backend/app/api/routes/admin.py`、`admin_tools.py`、`admin_receipts.py`、`ble.py`、`notifications.py`、`admin_market.py`：后台业务接口隔离及全局模块限制。
- `backend/app/services/wechat_pay.py`、`backend/app/api/routes/payment.py`、`reservation.py`、`card.py`、`report.py`：按公司商户号收款、查单、回调、退款和权益限制。
- `backend/app/api/routes/store.py`、`backend/app/schemas/store.py`：门店资质和可用支付方式。
- `admin-web/src/layouts/AdminLayout.vue`、`router/index.ts`、`views/Stores.vue`、新增 `views/Companies.vue`：按权限显示后台功能。
- `miniprogram/pages/store/detail.*`、`pages/booking/order.*`、新增 `pages/store/qualification.*`：门店资质、付款方式和首次授权。
- `backend/scripts/test_multi_company.py`、`miniprogram/tests/multiCompany.test.js`：公司隔离、支付和顾客流程测试。后端使用自带的 `unittest`；项目未安装 `pytest`。

### 任务 1：保存公司归属并迁移旧数据

**文件：**修改 `backend/app/models/__init__.py`、`backend/app/services/schema_migrate.py`、`backend/scripts/init_production.py`；新增 `backend/scripts/test_multi_company.py`。

**数据：**新增 `OperatingCompany`，含名称、状态、支付配置引用、支付绑定确认时间、营业执照图片、许可信息及联系方式；`Store`、`AdminUser` 增加 `company_id`，管理员增加 `role`；`Reservation` 增加 `company_id`、`payment_profile`、`pay_mchid`；新增 `UserCompanyConsent`，按用户、公司及告知版本唯一记录同意。

- [ ] 先写 `test_legacy_backfill_idempotent`：旧库升级后建立原公司 ID 1，旧门店、管理员和预约都归原公司；余额、订单号和支付状态不变；重复升级无额外变化。
- [ ] 运行 `cd backend && .venv\Scripts\python -m unittest scripts.test_multi_company -v`，确认新增测试因模型或迁移缺失而失败。
- [ ] 按现有 `schema_migrate.py` 方式增加兼容 SQLite/MySQL 的字段、表和回填；旧充值与购卡逻辑归原公司。升级后服务端拒绝公司归属为空的业务数据。
- [ ] 运行新增测试、`scripts/test_sprint1.py` 和 `scripts/test_card_rules.py`，确认通过。
- [ ] 提交公司归属模型、迁移和测试。

### 任务 2：统一后台公司权限

**文件：**修改 `backend/app/api/deps.py`、`backend/app/api/routes/admin.py`；新增 `backend/app/services/company_access.py`；扩展后端测试。

**接口：**`require_company_store(db, admin, store_id)`、`require_company_reservation(db, admin, reservation_id)`、`company_store_ids(db, admin)`、`require_platform_config(admin)`。`GET /api/admin/me` 返回角色和公司 ID，不返回商户密钥。

- [ ] 先写 `test_company_access_helpers` 和 `test_platform_config_cannot_browse_sister_orders`：两家公司管理员互相取不到门店、订单；停用账号无法访问；平台配置权限能建立公司，但日常经营数据仍按本公司隔离。
- [ ] 运行新增测试，确认因权限函数缺失而失败。
- [ ] 实现授权函数及公司名称、资质、状态、支付配置引用的管理接口；原管理员迁移为原公司平台管理员，姐姐公司的管理员由平台显式创建。密钥不经后台 API 配置。
- [ ] 运行新增测试，通过后提交。

### 任务 3：后台所有业务接口按公司隔离

**文件：**修改 `backend/app/api/routes/admin.py`、`admin_tools.py`、`admin_receipts.py`、`ble.py`、`notifications.py`、`admin_market.py`；扩展后端测试。

**规则：**列表从当前公司门店范围查询；详情与修改逐项核验门店或订单归属。姐姐公司账号不能访问全局余额、卡券、积分、团购、集市、AI 知识库、首页内容和系统配置。

- [ ] 盘点上述文件中的后台接口；写 `test_admin_cross_company_isolation` 覆盖门店/订单列表、直接 ID、修改、导出和统计；写 `test_global_admin_modules_denied` 覆盖全局模块。
- [ ] 对门店、座位、价格、日历、预约、顾客订单、门锁、收据和报表接口加服务端范围限制；姐姐后台的顾客资料只来自她店的订单，只返回履约所需字段。
- [ ] 其余未明确授权的后台接口对姐姐公司默认拒绝；座位图计划新增的后台接口也加同样限制。
- [ ] 运行跨公司测试及现有后台、收据、门锁测试，通过后提交。

### 任务 4：老店权益不能用于新店

**文件：**修改 `backend/app/api/routes/reservation.py`、`card.py`、`report.py`、`exchange.py`、`user.py`、`store.py`、`backend/app/services/booking.py`、`points.py`、`backend/app/schemas/store.py`；扩展后端测试。

**接口：**门店详情返回服务端决定的 `payment_options` 和资质信息；`POST /api/user/company-consents` 记录当前告知版本的明确同意。姐姐店预约只接受 `PayType.wechat`；充值、购卡、团购核销和积分发放首版仅用于老店。

- [ ] 写 `test_sister_store_rejects_legacy_entitlements`：旧余额、全店通用卡（`store_id=None`）、券、积分或团购码不能用于姐姐店，拒绝后余额和卡次不变。写 `test_sister_booking_requires_consent`：未授权不能向姐姐店下单，同意记录按版本保存，不能替别的用户授权。
- [ ] 运行新增测试，确认失败。
- [ ] 在服务端预约和权益入口按门店所属公司限制；小程序隐藏按钮不能替代服务端校验。老店原有流程保持不变。
- [ ] 运行新增和现有预约、卡规则测试，通过后提交。

### 任务 5：微信支付按订单所属商户处理

**文件：**修改 `backend/app/core/config.py`、`backend/app/services/wechat_pay.py`、`backend/app/api/routes/payment.py`、`reservation.py`、`card.py`、`report.py`、`backend/.env.production.example`、`docker-compose.prod.yml`；扩展后端测试。

**接口：**`WechatPayService.create_jsapi_order(..., profile_key)`、`query_order(order_no, profile_key)`、`verify_notify(headers, body, profile_key)`、`refund(..., profile_key)`。新增 `/api/payment/wechat/{profile_key}/notify`；原回调地址保留给老店历史订单。支付配置引用在服务端对应商户号及密钥路径。

- [ ] 写 `test_payment_profile_routing`、`test_wrong_merchant_callback_rejected`、`test_duplicate_callback_idempotent`、`test_refund_uses_order_profile`：新店选姐姐商户，旧充值和购卡仍选原商户；缺配置拒绝付款；错商户或金额不符不履约；重复回调不重复处理；历史退款不受门店新配置影响。
- [ ] 运行新增测试，确认失败。
- [ ] 把单一微信支付客户端改为按配置引用缓存；预约下单、查单和退款使用订单快照。回调验签后再次核对商户号、金额和订单状态；保留旧回调地址。
- [ ] 运行新增及现有支付、收据测试；确认配置示例只有占位符，响应和日志不包含私钥。
- [ ] 提交多商户支付与测试。

### 任务 6：后台、小程序及开店验收

**文件：**修改 `admin-web/src/layouts/AdminLayout.vue`、`router/index.ts`、`views/Stores.vue`、`views/Admins.vue`、`miniprogram/pages/store/detail.*`、`pages/booking/order.*`、`miniprogram/app.json`；新增 `admin-web/src/views/Companies.vue`、`miniprogram/pages/store/qualification.*`、`miniprogram/tests/multiCompany.test.js`；修改 `docs/POST-DEPLOY.md`。

**界面：**后台按 `/api/admin/me` 返回的角色显示菜单；平台配置账号可录入公司资质与绑定状态。门店详情有“店铺资质”入口；顾客第一次在姐姐店下单时显示必要的信息告知并记录同意。平时选店和付款界面仍以门店名称为主。

- [ ] 写小程序测试：切换不同座位图、各店付款选项、姐姐店不显示老店权益、资质入口、首次授权。手工检查两家公司后台菜单与跳转。
- [ ] 实现前台和后台界面；门店选择页及日常结算页不额外突出公司名称，但资质页和首次告知写明实际主体。
- [ ] 运行 `cd admin-web && npm run build` 及 `cd miniprogram && npm test`；手工确认切店后不会显示上家门店的旧座位图。
- [ ] 更新 `docs/POST-DEPLOY.md`：支付异主体绑定、真实小额支付退款、两家公司账单核对。座位图、价格、营业时间和权限都验收通过前，姐姐店不能开业。
- [ ] 提交后台、小程序和上线检查说明。

## 实施顺序

先完成已有的 `docs/superpowers/plans/2026-10-01-configurable-store-seat-maps.md`：老店维持现有布局，新店上传并发布自己的图片和座位位置。再按本计划完成公司归属、后台隔离、不同商户收款和上线验收。两部分可以分别提交代码，但姐姐店必须在全部检查通过后才开放。
