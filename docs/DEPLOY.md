# 知行岛 · 生产上线指南

本文档对应路线 **① 准备上线**：部署 + 微信/云老板真实对接 + 小程序提审前联调。

> **小程序/商户审核中？** 可先走 **[无微信阶段](#无微信阶段审核中)**（A + C + 后台 + Nginx），微信审核通过后再补 [B. 微信小程序](#b-微信小程序)。

---

## 无微信阶段（审核中）

微信 AppID、商户号尚未就绪时，按下列顺序执行，**跳过 B 节**。

| 步骤 | 动作 |
|------|------|
| 1 | 购买 Linux 服务器（Ubuntu 22.04），开放 80/443 |
| 2 | 安装 Docker + Docker Compose |
| 3 | 上传代码，生成 `backend/.env`（见下方脚本） |
| 4 | `docker compose -f docker-compose.prod.yml --env-file .env.docker up -d --build` |
| 5 | `docker compose ... --env-file .env.docker exec api python scripts/init_production.py` |
| 6 | Nginx 反代 API（可先 HTTP + IP，备案后再 HTTPS） |
| 7 | 构建并部署 `admin-web/dist` |
| 8 | 后台配置团购映射、处理「待配置团购」 |
| 9 | `python scripts/deploy_check.py` 通过 |

**环境变量要点**（`backend/.env.production.example`）：

```env
APP_ENV=production
PRE_WECHAT_LAUNCH=true          # 审核期必开；微信就绪后改 false
COUPON_PROVIDER=meituan         # 云老板真实核销
MEITUAN_CLIENT_ID=...
MEITUAN_SECRET=...
MEITUAN_SHOP_ID=...
# WX_* 留空即可，勿填占位 AppID
```

**本机 Windows 生成生产 .env**（从当前开发 `.env` 复制云老板凭证，输出 `backend/.env.docker`，**不会覆盖**开发用 `.env`）：

```powershell
.\deploy\prepare-production-env.ps1 -ApiBase "http://你的服务器IP:8000"
# 上传到服务器后改名为 backend/.env
```

**Linux 服务器一键脚本**：

```bash
chmod +x deploy/setup-server.sh
./deploy/setup-server.sh
```

此阶段能力：

- 后台管理、团购映射、待配置团购、订单查询
- 美团/云老板真实兑换（需映射齐全）
- 小程序开发者工具 + **勾选「不校验合法域名」** + 本地/HTTP API 联调（`miniprogram/config.js` 指向服务器地址）
- 期限卡支付、mock-pay（`PRE_WECHAT_LAUNCH=true` 且未配商户号时）

暂不可用（等 B 节）：真机 HTTPS 合法域名、真实微信登录/支付、手机号组件。

---

## 阶段总览

| 阶段 | 目标 | 预计 |
|------|------|------|
| A | 服务器 + MySQL + Redis + HTTPS | 1–2 天 |
| B | 微信小程序 + 支付配置 | 1–2 天 |
| C | 云老板团购核销 | 0.5–1 天 |
| D | 通通锁蓝牙 | 0.5–1 天 |
| E | 联调验收 + 提审 | 1–2 天 |

---

## A. 基础设施

### A1. 服务器要求

- Linux（推荐 Ubuntu 22.04）或 Windows Server
- 2 核 4G 起，开放 443（HTTPS）
- 域名：`api.your-domain.com`（API）、`admin.your-domain.com`（后台，可选）

### A2. Docker 一键启动（推荐）

```bash
# 1. 复制生产环境变量
cp backend/.env.production.example backend/.env
# 编辑 backend/.env，至少改 SECRET_KEY、ADMIN_PASSWORD、MYSQL 密码

# 2. 启动 MySQL + Redis + API
docker compose -f docker-compose.prod.yml --env-file .env.docker up -d --build

# 3. 初始化数据库（首次）
docker compose -f docker-compose.prod.yml --env-file .env.docker exec api python scripts/init_production.py
```

验证：`curl http://127.0.0.1:8000/health` → `{"status":"ok"}`

### A3. 手动部署（不用 Docker）

```bash
cd backend
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.production.example .env
# 编辑 .env，DATABASE_URL 指向 MySQL

docker compose up -d          # 仅 MySQL + Redis
python scripts/init_production.py
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2
```

### A4. HTTPS 反向代理

参考 `deploy/nginx.conf.example`，配置 SSL 证书（Let's Encrypt 或云厂商）。

**备案前**：可先用 `deploy/nginx-http.conf.example`（HTTP + IP），仅用于后台与 API 联调；小程序真机仍须 HTTPS 备案域名（见 B 节）。

**重要**：小程序 `request合法域名` 必须是 **HTTPS**，且备案域名。

---

## B. 微信小程序

### B1. 公众平台配置

1. [微信公众平台](https://mp.weixin.qq.com) → 开发 → 开发管理 → 开发设置  
2. 记录 **AppID**、**AppSecret** → 写入 `backend/.env`  
3. **服务器域名** → request 合法域名：`https://api.your-domain.com`  
4. 企业主体才能用：手机号快速验证、订阅消息、通通锁插件

### B2. 小程序端修改

编辑 `miniprogram/config.js`：

```javascript
const API_BASE = 'https://api.your-domain.com/api'  // 生产域名
```

微信开发者工具 → **取消**「不校验合法域名」→ 真机预览测试。

### B3. 微信支付

1. [微信支付商户平台](https://pay.weixin.qq.com) 开通 JSAPI 支付  
2. 关联小程序 AppID  
3. 下载 API 证书 → 放到 `backend/certs/`  
4. 填写 `.env`：

```env
APP_ENV=production
WX_PAY_MCHID=商户号
WX_PAY_SERIAL_NO=证书序列号
WX_PAY_API_V3_KEY=APIv3密钥
WX_PAY_CERT_PATH=./certs/apiclient_cert.pem
WX_PAY_KEY_PATH=./certs/apiclient_key.pem
```

5. 商户平台配置 **支付回调 URL**：  
   `https://api.your-domain.com/api/payment/wechat/notify`

> 生产环境在 `APP_ENV=production` 且填写 `WX_PAY_*` 证书后会走真实微信支付 v3；开发环境仍用 mock-pay，**生产环境 mock 接口已禁用**。

### B4. 手机号绑定

需企业小程序 + 开通「手机号快速验证组件」。生产环境 `APP_ENV=production` 会走真实微信接口。

---

## C. 云老板团购（美团/抖音）

1. 联系云老板开通 ISP 团购核销  
2. 获取 `clientId`、`secret`、`shopId`  
3. 写入 `backend/.env`（支持 `MEITUAN_*` 或 `YUNLAOBAN_*` 命名）：

```env
MEITUAN_CLIENT_ID=xxx
MEITUAN_SECRET=xxx
MEITUAN_SHOP_ID=xxx
MEITUAN_PLATFORM=1
COUPON_PROVIDER=meituan
```

4. 后台 **团购映射** 配置 `dealId` → 期限卡权益  
5. **待配置团购**（推荐流程）：
   - 用户兑换时若缺映射，系统 **不会核销券**，并自动记录到后台「待配置团购」
   - 管理员在 **团购映射** 页点 **一键配置** → 用户 **用同一张券再兑一次**
   - 不必每个团购都先买一券；每种主要类型用 1 张测试券走通即可
6. 注意：美团开店宝显示的 ID 与云老板验券返回的 `dealId` **可能不同**，以验券报错或待配置列表中的 ID 为准

Mock 末位规则仅在 `COUPON_PROVIDER=mock` 或无云老板凭证时生效。

---

## D. 通通锁蓝牙

1. [通通锁开放平台](https://open.sciener.com) 创建应用  
2. 填写 `TTLOCK_*` 环境变量  
3. 小程序 `app.json` 恢复通通锁插件（需企业 AppID）  
4. 后台 **蓝牙锁管理** 录入真实 lockId / lockData

---

## E. 上线前检查清单

### 安全

- [ ] `SECRET_KEY` 已改为随机长字符串  
- [ ] `ADMIN_PASSWORD` 已改为强密码  
- [ ] `.env` 未提交 Git  
- [ ] 生产环境 mock-pay / mock-recharge 不可用（已代码禁用）

### 功能

- [ ] 微信登录（真机）  
- [ ] 选座预约 + 微信支付  
- [ ] 美团兑换 → 期限卡 → 预约支付  
- [ ] 缺映射时「待配置团购」自动记录 + 一键配置后重试  
- [ ] 蓝牙开门（真锁或门店实测）  
- [ ] 后台订单、座位、团购映射可查

### 运维

- [ ] MySQL 每日备份  
- [ ] 日志与进程守护（systemd / Docker restart）  
- [ ] 运行 `python scripts/test_sprint4.py` 通过（开发环境回归）

---

## 后台前端部署

```bash
cd admin-web
npm install
npm run build
# 将 dist/ 上传到 Nginx root（见 nginx.conf.example admin 站点）
```

构建前复制 `admin-web/.env.production.example` 为 `.env.production`，设置 `VITE_API_BASE=https://api.your-domain.com/api`。

---

## 常见问题

**Q: 小程序 request 失败**  
A: 检查合法域名、HTTPS 证书、后端 CORS；真机关闭「不校验域名」再测。

**Q: 登录仍是 dev_openid**  
A: `WX_APPID` 不能是 `your_wx_appid` 占位符，且 `APP_ENV=production`。

**Q: 团购兑换 400**  
A: 检查云老板凭证、deal 映射、券码是否已兑换。

**Q: SQLite 数据如何迁 MySQL**  
A: 生产请用 `init_production.py` 重新 seed；历史订单需单独导出导入。

---
