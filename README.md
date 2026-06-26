# 知行岛自习室预约系统

全栈自习室预约系统：微信小程序 + Web 后台 + FastAPI 后端。

## 技术栈

- **后端**: Python FastAPI + SQLAlchemy + MySQL 8 + Redis
- **后台**: Vue3 + Vite + Element Plus
- **小程序**: 微信原生 + 通通锁蓝牙插件

## 快速开始

### 1. 启动基础设施（可选）

有 Docker 时使用 MySQL + Redis：

```bash
docker compose up -d
# 并将 backend/.env 中 DATABASE_URL 改为 MySQL 连接串
```

无 Docker 时默认使用 **SQLite**（`backend/zxd_study.db`）+ 内存 Redis 降级，可直接开发。

### 2. 后端

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt
copy .env.example .env
python scripts/seed.py
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

API 文档: http://localhost:8000/docs

### 3. 后台管理

```bash
cd admin-web
npm install
npm run dev
```

访问 http://localhost:5173 ，默认账号 `admin / admin123`

### 4. 微信小程序

1. 微信开发者工具导入 `miniprogram` 目录
2. 修改 `app.js` 中 `apiBase` 为后端地址
3. 开发阶段勾选「不校验合法域名」
4. 企业小程序账号需申请通通锁插件 `wx43d5971c94455481`

## 项目结构

```
zxd-pro/
├── backend/          # FastAPI 后端
├── admin-web/        # Vue3 后台管理
├── miniprogram/      # 微信小程序
└── docker-compose.yml
```

## Sprint 1 已实现

- [x] 微信登录 + 手机号绑定
- [x] 门店列表与详情
- [x] 按小时预约（自动分配座位）
- [x] 微信支付（开发环境模拟支付）
- [x] 蓝牙开门（TTLock 插件 + 后端钥匙管理）
- [x] 基础后台：订单查询 + 蓝牙锁管理

## Sprint 2 已实现

- [x] 座位可视化选择（分布图选座）
- [x] 按天/月/夜读预约
- [x] 余额充值与余额支付
- [x] 学习报告与排行榜
- [x] 个人中心：钱包、订单、期限卡
- [x] 后台运营报表（营收/入住率）

## Sprint 3 已实现

- [x] 美团/抖音团购券兑换（云老板 API + 开发 Mock）
- [x] 期限卡发放与预约抵扣（小时卡/天卡/月卡/夜读月卡/次卡）
- [x] 优惠券预览、下单与支付核销
- [x] 小程序：团购兑换页、优惠券、下单选卡选券
- [x] 后台：团购 deal 映射、优惠券发放

### Sprint 3 开发测试

1. 执行 `python scripts/seed.py` 写入团购映射与测试券（需先小程序登录一次生成 dev 用户）
2. 美团兑换 Mock 券码：任意 6 位以上，**末位数字**决定卡种  
   - `...1` → 4小时卡  
   - `...2` → 天卡  
   - `...3` → 月卡  
   - `...4` → 夜读月卡  
   - `...5` → 10次卡  
3. 预约下单时可选择「期限卡」或「优惠券」支付

## Sprint 4 已实现

- [x] 自习离座积分（每 10 分钟 1 分）
- [x] 邀请码体系（邀请人 +50 / 被邀请 +20）
- [x] 人脸录入（开发 Mock，生产对接门禁）
- [x] 蓝牙锁低电量告警（后台提醒 + 开门模拟耗电）
- [x] 定时任务：未支付取消、订单过期、电量巡检

### Sprint 4 测试

1. 执行 `python scripts/seed.py`（新建积分/告警表，补全邀请码）
2. **积分**：入座 → 离座后查看「我的 → 我的积分」
3. **邀请**：「我的 → 邀请有礼」复制邀请码，另一账号填写领取
4. **人脸**：「我的 → 人脸录入」拍照保存
5. **低电量**：后台「蓝牙锁管理」查看告警（可将门锁电量改低于 20% 测试）

## Sprint 5 已实现

- [x] 门店 24 座（A/B/C 三区）+ 选座图分区说明
- [x] 后台座位管理（启用/停用）
- [x] 小程序兑换记录页
- [x] 自动化测试 `scripts/test_sprint4.py`

### 一键回归测试

```powershell
cd f:\zxd-pro\backend
$env:PYTHONPATH="f:\zxd-pro\backend"
.\.venv\Scripts\python scripts\test_sprint4.py
```

## 环境变量

参见 `backend/.env.example` 与 **`backend/.env.production.example`**

## 生产上线

| 文档 | 内容 |
|------|------|
| **[docs/POST-DEPLOY.md](docs/POST-DEPLOY.md)** | API/后台上线后：小程序联调、后台配置、验收清单 |
| **[docs/DEPLOY.md](docs/DEPLOY.md)** | 上线总览：微信 / 云老板 / 通通锁 / 检查清单 |

Docker 服务器快速启动（详见 SERVER-SETUP.md）：

```bash
# 准备 .env.docker + backend/.env 后：
docker compose -f docker-compose.prod.yml --env-file .env.docker up -d --build
docker compose -f docker-compose.prod.yml --env-file .env.docker exec api python scripts/init_production.py
```

## 开发备注

- 开发环境微信/支付/TTLock 均支持 Mock 模式，无需真实密钥即可联调
- 生产部署前请配置真实微信 AppID、支付证书、TTLock 开放平台凭证
