# Admin 错题本管理模块设计

日期：2026-09-04  
状态：已确认，已实现

## 背景

错题本已在 C 端（小程序 + `/api/wrongbook`）落地，admin-web 与 `/admin` 侧尚无管理能力。运营需要跨用户查看、编辑文本字段与状态、删除违规内容。

## 目标与非目标

### 目标

- 管理后台可分页浏览全部用户错题
- 按用户、状态、关键词等筛选
- 抽屉内查看详情（含图片只读预览）
- 编辑：学科、状态、OCR、答案文本、错因、标签
- 硬删除错题并记审计日志

### 非目标

- 代用户新建错题
- 独立学科管理页（重命名/删除学科等）
- 后台上传或替换题干/答案图片
- 修改 `review_count` / `bump_review` 等复习计数逻辑
- 新增 RBAC（沿用「登录即可」）

## 方案

采用**独立 Admin API + 单页管理**（与 Users / 二手市场一致）：

- 后端：`/api/admin/wrongbook/*`，`get_current_admin`
- 前端：学习助手菜单下「错题本」单页，列表 + 抽屉编辑

不复用 C 端 `/wrongbook`（其强制 `user_id` 隔离，不适合跨用户运维）。

## 后端设计

### 文件

| 文件 | 作用 |
|------|------|
| `backend/app/api/routes/admin_wrongbook.py` | 新建 Admin 路由 |
| `backend/app/main.py` | `include_router(admin_wrongbook.router, prefix="/api")` |

复用：`app.services.wrongbook`（`question_to_dict` / `subject_to_dict` / `STATUS_LABELS`）、`log_admin_action`、`ResponseModel` / `PageResult`。

### 接口

前缀：`/api/admin/wrongbook`  
鉴权：`Depends(get_current_admin)`

#### `GET /questions`

分页列表（DB `count` + `offset/limit`，不要 C 端那种先全量再内存过滤）。

Query：

| 参数 | 说明 |
|------|------|
| `page` | ≥1，默认 1 |
| `page_size` | 1–100，默认 20 |
| `user_id` | 可选，精确匹配 |
| `subject_id` | 可选 |
| `status` | 可选，0/1/2 |
| `keyword` | 可选；匹配 OCR / 错因 / 答案文本，以及用户昵称、手机号（LIKE） |
| `tag` | 可选；若实现成本高可先在当前页结果内存过滤，或跳过 V1（见下方「范围裁决」） |

响应 `data`：`{ items, total, page, page_size }`。

列表项字段（在 `question_to_dict` 基础上扩充）：

- 既有错题字段（含 `subject_name`、`status_label`、`image_urls` 等）
- `user_nickname`、`user_phone`（或项目中用户展示用的等价字段）
- 可选：`thumb_url` = `image_urls[0]`（前端也可直接取）

排序：`updated_at DESC, id DESC`。

#### `GET /questions/{id}`

详情：404 若不存在。返回同列表项的完整字段 + 用户信息。图片 URL 原样返回（相对 `/static/wrongbook/...`）。

#### `PUT /questions/{id}`

Body（均可选，部分更新）：

| 字段 | 约束 |
|------|------|
| `subject_id` | 必须属于该错题的 `user_id`，否则 400 |
| `ocr_text` | 字符串 |
| `answer_text` | 字符串 |
| `reason` | 最长 200（与模型一致） |
| `tags` | `list[str]` |
| `status` | 0 / 1 / 2 |

**忽略/拒绝**：`image_urls`、`answer_image_urls`、`user_id`、`review_count`。若客户端传入图片字段，直接忽略即可，不报错。

成功后：`log_admin_action(..., action="wrongbook_update", target_type="wrong_question", target_id=id)`，返回更新后的详情 dict。

#### `DELETE /questions/{id}`

硬删行；`log_admin_action(..., action="wrongbook_delete", ...)`。  
V1 **不**强制清理磁盘文件（与 C 端 DELETE 行为一致）；可后续再做。

#### `GET /subjects?user_id=`

`user_id` 必填。返回该用户学科列表（`subject_to_dict`）。  
**不**调用 `ensure_preset_subjects`（避免管理操作副作用播种）；用户若无学科则返回空数组，编辑时无法改学科（或提示）。

### 范围裁决

- **tag 筛选**：V1 实现则与 C 端类似——SQL 拉候选后再按 tag 过滤会破坏分页；推荐 V1 **不做 tag 筛选项**，仅在详情/编辑展示与修改 tags。列表筛选用 `user_id` / `status` / `keyword` / `subject_id` 即可。
- **subject_id 列表筛选**：可选；前端首版可不放筛选控件，但 API 支持无妨。

## 前端设计

### 改动点

| 文件 | 改动 |
|------|------|
| `admin-web/src/views/Wrongbook.vue` | 新建页面 |
| `admin-web/src/router/index.ts` | `path: 'wrongbook'` |
| `admin-web/src/layouts/AdminLayout.vue` | 「学习助手」下增加「错题本」 |

模式对齐 `Users.vue`：`http` + `parsePageResult` + `el-table` + `el-drawer`，无独立 api module / Pinia。

### 列表

- 筛选：关键词、状态（全部 / 未掌握 / 仍然错 / 已掌握）、用户 ID（可选数字输入）
- 列：缩略图、ID、用户（昵称/手机）、学科、状态、错因摘要、更新时间、操作
- 操作：详情、删除（`ElMessageBox.confirm`）
- 分页：`page_size: 20`

图片展示：拼接与其它后台静态资源一致的 base（若现有页面已对 `/static` 有处理则复用；否则用 `VITE_API_BASE` 同源或站点根路径解析）。

### 抽屉

- **只读**：用户信息、题干图、答案图（`el-image` 可预览）
- **可编辑**：学科（打开时 `GET /admin/wrongbook/subjects?user_id=`）、状态、OCR、答案文本、错因、标签（逗号或 tag 输入，与项目习惯一致即可）
- **操作**：保存（PUT）、删除

### 菜单与路由

- 路由：`/wrongbook`
- 菜单文案：错题本
- 分组：学习助手（与学习数据、AI 知识库并列）

## 错误与审计

- 鉴权失败：沿用现有 admin 401/403
- 资源不存在：404，`detail`/`message` 中文「错题不存在」
- 学科不属于该用户：400
- 写操作必须 `log_admin_action` 后 `commit`

## 测试建议

- 后端：列表分页与 keyword；PUT 改 status/subject；非法 subject_id；DELETE 后 404
- 前端：手动验筛选、抽屉保存、删除确认

（不必新增 E2E；可仿 `backend/scripts/test_wrongbook.py` 加短脚本或 pytest，非必须。）

## 成功标准

1. 管理员登录后侧栏可见「错题本」
2. 能看到跨用户错题列表并筛选
3. 抽屉可预览图片并保存文本/状态/学科/标签修改
4. 删除后列表不再出现该条，审计日志有记录
5. 无法通过本模块上传图片或新建错题
