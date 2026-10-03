# 各门店独立座位图实施计划

> **供执行者使用：**按 `superpowers:subagent-driven-development` 或 `superpowers:executing-plans` 技能逐项实施；用 `- [ ]` 跟踪每一步。

**目标：**每家门店显示自己的座位图。老店保留现有固定布局和历史预约；新店可上传平面图、标注座位并发布。

**方案：**`Seat.id` 继续作为预约对应的座位身份。新店的图片、座位坐标保存为“草稿”和“已发布”版本；顾客只看到已发布版本。小程序按门店的座位图模式加载对应布局。支付和公司权限尚未完成前，新店保持停业。

**技术：**FastAPI、SQLAlchemy、SQLite/MySQL、Vue 3、Element Plus、微信原生小程序、Python `unittest`、Node `--test`。

**设计说明：**`docs/superpowers/specs/2026-10-01-configurable-store-seat-maps-design.md`

## 全程约束

- 现有门店使用 `legacy` 模式；原座位图、预约和座位 ID 保持不变。
- 新建门店使用 `image` 模式，默认 `status=0`。发布座位图不会自动开店。
- 图片模式下，座位编号只需在本店唯一，可以超出 1–28；预约仍引用 `Seat.id`。
- 保存草稿不能改变顾客看到的图片、座位位置或可订状态；发布必须一次完成切换。
- 有历史预约的座位不能删除，可以停用；停用后历史订单仍可查看。
- 本计划不接通姐姐公司的商户号，也不开放她的店或后台账号。

## 重点检查

1. 移动草稿上的座位后，发布前顾客仍看到旧图片和旧位置（任务 2）。
2. 跨店座位、未发布座位在预览、下单和自动分配时均被拒绝（任务 4）。
3. 切换门店后，较晚返回的上家门店请求不能覆盖当前座位图（任务 5）。
4. 图片加载失败或尚未发布时，显示不可预约状态，不能错用老店的固定布局（任务 5）。
5. 换图不改变座位 ID 和历史订单；停用旧座位后不能产生新预约（任务 4）。

## 文件分工

| 文件 | 职责 |
| --- | --- |
| `backend/app/models/__init__.py`、`backend/app/services/schema_migrate.py` | 门店模式、座位图版本和兼容旧库的迁移 |
| `backend/app/services/store_seat_maps.py` | 草稿、发布、恢复及本店可订座位规则 |
| `backend/app/api/routes/admin_seat_maps.py`、`backend/app/main.py` | 后台上传图片及编辑、发布接口 |
| `backend/app/api/routes/admin.py`、`admin_tools.py` | 新店默认停业；图片模式不自动补齐固定座位 |
| `backend/app/api/routes/store.py`、`backend/app/services/booking.py`、`business.py` | 顾客座位图、空位及服务端预约校验 |
| `miniprogram/components/floor-plan-map/index.*`、`miniprogram/pages/store/seats.*` | 显示新店图片和座位标记，保留老店布局 |
| `admin-web/src/views/Seats.vue`、`admin-web/src/views/Stores.vue` | 每店座位图编辑器和草稿、停业状态 |
| `backend/tests/test_store_seat_maps.py`、`miniprogram/tests/seat-map.test.js` | 行为验证 |

---

### 任务 1：保存座位图模式，新店默认停业

**文件：**修改 `backend/app/models/__init__.py`、`backend/app/services/schema_migrate.py`、`backend/app/api/routes/admin.py`、`admin-web/src/views/Stores.vue`；新增 `backend/tests/test_store_seat_maps.py`。

**接口与数据：**`Store.seat_map_mode` 为 `legacy` 或 `image`；`StoreSeatMap` 包含 `id`、`store_id`、`version`、`state`（`draft`/`published`/`archived`）、`image_path`、`aspect_ratio`、`markers`、`created_at`、`published_at`。每个标记包含 `seat_id`、百分比坐标 `x_pct/y_pct` 和方向 `orient`。`Store.floor_plan` 继续保存已发布图片路径，以兼容旧代码。

- [ ] 先写模型测试：旧店默认为 `legacy`；新店可保存带座位标记的草稿；提交后重新读取仍一致。
- [ ] 运行 `cd backend && python -m unittest discover -s tests -p test_store_seat_maps.py -v`，确认新增测试因字段和模型缺失而失败。
- [ ] 增加字段和幂等迁移；现有门店迁移为 `legacy`；自动补齐固定座位的逻辑只处理 `legacy`。
- [ ] 后台新建门店时设为 `image`、`status=0`；门店页显示停业状态；接口测试确认停业新店不出现在顾客门店列表。
- [ ] 运行新增后端测试及 `cd admin-web && npm run build`；用一次性旧库副本核对迁移结果。
- [ ] 提交模型、迁移、停业规则和测试。

### 任务 2：草稿、发布和恢复

**文件：**新增 `backend/app/services/store_seat_maps.py`；扩展 `backend/tests/test_store_seat_maps.py`。

**接口：**`get_draft_map(db, store_id)`、`get_published_map(db, store_id)`、`save_draft_map(db, store_id, image_path, aspect_ratio, markers)`、`publish_draft_map(db, store_id)`、`restore_map(db, store_id, map_id)`、`published_image_seat_ids(db, store_id)`。

- [ ] 先写失败测试：保存草稿不改变已发布图和 `Store.floor_plan`；发布同时切换两者；恢复旧版生成新的已发布版本；没有草稿时不能发布。
- [ ] 运行座位图测试，确认因服务函数缺失而失败。
- [ ] 实现校验：图片存在、画布比例为有限正数、发布时至少一个座位；标记不重复，坐标在 0–100%，方向有效，座位和区域都属于本店。发布时锁定门店行，把旧版归档、新版和 `floor_plan` 一并提交。
- [ ] 增加跨店座位、重复标记、越界坐标、未知座位和空草稿测试；失败时已发布数据不变。未发布的新座位不得出现在可订 ID 集合中。
- [ ] 运行后端测试，通过后提交服务和测试。

### 任务 3：后台座位图接口

**文件：**新增 `backend/app/api/routes/admin_seat_maps.py`；修改 `backend/app/main.py`、`backend/app/api/routes/admin_tools.py`、`backend/app/api/routes/admin.py`；扩展后端测试。

**接口：**`GET /api/admin/stores/{store_id}/seat-map` 返回草稿和已发布摘要；`POST .../seat-map/image` 上传不超过 2 MB 的 JPEG/PNG/WebP/GIF；`PUT .../seat-map/draft` 保存图片、比例和标记；`POST .../seat-map/publish` 发布；`POST .../seat-map/restore/{map_id}` 恢复。另提供本店区域的增删改查；有座位的区域不能删除。全部要求管理员登录，写操作记审计日志。

- [ ] 先写接口测试：未登录返回 401；正常草稿和发布成功；错误图片类型、过大图片、跨店标记或区域、旧店编辑均被拒绝；不存在的对象返回 404。
- [ ] 运行接口测试，确认因路由缺失而失败。
- [ ] 实现路由和图片保存；图片文件名唯一，只返回公开 URL，不暴露服务器路径；区域写入校验门店归属并记日志。
- [ ] 图片模式的座位创建、编辑、删除和统计只处理本店座位，不调用固定座位补齐；有历史预约的座位仍禁止删除。旧店补座按钮只在 `legacy` 模式可用。
- [ ] 运行接口测试和老店后台选座检查，通过后提交。

### 任务 4：顾客端和预约只使用已发布座位

**文件：**修改 `backend/app/api/routes/store.py`、`backend/app/api/routes/admin.py`、`backend/app/services/booking.py`、`backend/app/services/business.py`；扩展后端测试。

**接口：**`GET /api/store/{store_id}/seat-map` 对图片模式返回 `mode`、`image_url`、`aspect_ratio`、`markers`；对旧店返回 `mode='legacy'`。图片模式下，顾客空位、自动分配、后台预约、换座都只使用 `published_image_seat_ids`。

- [ ] 先写失败测试：停业或未发布的新店不可预约；发布并在测试中开店后，超出 1–28 的座位可出现；未发布、停用或跨店座位不能预览、创建或自动分配。
- [ ] 运行测试，确认固定编号过滤和缺失的预约校验导致失败。
- [ ] 改顾客座位、空位和所有下单入口，按门店模式读取座位；图片模式区域名从 `Zone` 获取；服务端再次校验座位已发布且属于本店。
- [ ] 增加历史连续性测试：换图后旧订单仍引用原 `seat_id`；停用旧座位不能新订，但历史订单仍显示原编号；老店固定座位流程不变。
- [ ] 运行座位图和现有预约测试，通过后提交。

### 任务 5：小程序显示各店自己的图

**文件：**修改 `miniprogram/pages/store/seats.js/.wxml/.wxss`、`miniprogram/components/floor-plan-map/index.js/.wxml/.wxss`；新增 `miniprogram/tests/seat-map.test.js`。

**接口：**选座页请求 `/store/{storeId}/seat-map`。`legacy` 使用现有 `getLayout()`；`image` 按服务端座位 ID、坐标和空位状态叠加标记，不根据旧店固定坐标生成。

- [ ] 先写测试：42 座的新店显示 42 个标记；切店后旧请求的迟到响应不覆盖新店；缺图不能选座；旧店仍使用 `getLayout()`。
- [ ] 运行 `cd miniprogram && npm test`，确认新增测试失败。
- [ ] 实现图片模式显示、缩放和点击；切店先清空旧数据；图片失败或未发布时明确提示不可预约，不能回退为旧店布局。
- [ ] 运行测试；在微信开发者工具中检查横竖版图片、不同屏宽、缩放、选择、占用、停用及图片失败状态。
- [ ] 提交小程序改动和测试。

### 任务 6：后台可视化编辑和发布验收

**文件：**修改 `admin-web/src/views/Seats.vue`、`admin-web/src/views/Stores.vue`；新增 `admin-web/src/components/SeatMapEditor.vue`。

**接口：**编辑器调用任务 3 的接口；拖动座位标记时保存 0–100% 坐标；“保存草稿”和“发布”是两个独立操作；后台同时显示草稿、已发布及门店营业状态。

- [ ] 实现上传/替换图片、区域和座位管理、画布点选/拖动、预览、保存、发布与恢复上一版；坐标限制在画布范围内。
- [ ] 旧店补齐固定座位功能只在 `legacy` 显示；已发布版本可只读预览；图片、座位或坐标无效时不能发布；发布不自动开店。
- [ ] 运行 `cd admin-web && npm run build`；手工检查上传、拖动、保存草稿、顾客仍看到旧图、发布、恢复和切店。
- [ ] 运行后端座位图测试及 `cd miniprogram && npm test`；确认改动没有触及商户密钥、顾客余额或旧订单号。
- [ ] 提交后台编辑器。

## 与公司隔离计划的衔接

此计划完成后仍保持姐姐的新店停业。继续执行 `docs/superpowers/plans/2026-10-03-multi-company-stores.md`，完成她的商户号、后台权限、老店权益隔离、支付退款和独立报表；真实支付和退款验收通过后才开店。
