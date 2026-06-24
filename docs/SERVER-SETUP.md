# 服务器部署与配置指南

本文档说明如何在 **有 Docker 的 Linux 服务器** 上部署知行岛，以及 **笔记本当开发服务器** 的简化方式。

相关文档：
- [DEPLOY.md](./DEPLOY.md) — 上线总览（微信 / 云老板 / 通通锁 / 检查清单）
- 配置模板：`backend/.env.production.example`
- 脚本目录：`deploy/`

---

## 一、先搞清楚：要不要单独装 MySQL？

| 部署方式 | 要不要自己装 MySQL |
|----------|-------------------|
| **Docker（推荐）** | ❌ **不用**。`docker-compose.prod.yml` 已包含 MySQL + Redis 容器 |
| 笔记本本地开发 | ❌ **不用**。默认 SQLite `backend/zxd_study.db` |
| 手动部署（不用 Docker） | ✅ 要，或使用云 RDS |

Docker 启动后，MySQL 数据保存在 Docker 卷 `mysql_data` 中，重启服务器数据仍在。

---

## 二、两种常见场景

### 场景 A：Linux 服务器 + Docker（正式/内测）

```
Internet → Nginx(443) → API 容器(:8000) → MySQL 容器
                                      → Redis 容器
后台静态页 → Nginx → /var/www/zxd-admin
```

### 场景 B：Windows 笔记本当服务器（开发联调）

```
局域网设备 → 笔记本 0.0.0.0:8000 → SQLite（zxd_study.db）
```

- 不用 Docker、不用 MySQL
- 小程序开发者工具勾选「不校验合法域名」
- 适合审核前联调；**不适合** 7×24 对外营业

---

## 三、Docker 服务器完整步骤

### 3.1 前置条件

- Ubuntu 22.04（或同类 Linux）
- 已安装 Docker + Docker Compose v2
- 安全组/防火墙开放：**22、80、443**（8000 可只本机访问，由 Nginx 反代）
- 代码目录示例：`/opt/zxd-pro`

安装 Docker（若未装）：

```bash
cd /opt/zxd-pro
chmod +x deploy/install-docker-ubuntu.sh
sudo bash deploy/install-docker-ubuntu.sh
```

### 3.2 上传代码

```bash
cd /opt
git clone <你的仓库> zxd-pro
cd zxd-pro
```

或用 `scp` / 压缩包上传后解压。

### 3.3 配置文件（两个文件，缺一不可）

#### 文件 1：项目根目录 `.env.docker`

供 `docker compose` 创建 MySQL 时使用，**只有密码**：

```bash
cd /opt/zxd-pro
cat > .env.docker << 'EOF'
MYSQL_ROOT_PASSWORD=请设强密码Root
MYSQL_PASSWORD=请设强密码Db
EOF
```

#### 文件 2：`backend/.env`

供 API 应用读取。**`DATABASE_URL` 里的密码必须与 `.env.docker` 中 `MYSQL_PASSWORD` 一致。**

**方式 1 — 在 Windows 本机生成后上传（推荐）**

不会覆盖开发用的 `backend/.env`：

```powershell
cd f:\zxd-pro
.\deploy\prepare-production-env.ps1 -ApiBase "https://api.你的域名.com"
# 或暂无域名：-ApiBase "http://公网IP:8000"
```

生成：
- `backend/.env.docker` → 上传到服务器后 **改名为** `backend/.env`
- 根目录 `.env.docker` → 上传到服务器项目根目录

脚本会随机生成 `SECRET_KEY`、`ADMIN_PASSWORD`、MySQL 密码，**请保存输出**。

**方式 2 — 在服务器上手工编辑**

```bash
cp backend/.env.production.example backend/.env
nano backend/.env
```

**微信审核中（跳过 B 节）最少要改：**

```env
APP_ENV=production
PRE_WECHAT_LAUNCH=true

SECRET_KEY=<openssl rand -hex 32>
BASE_URL=https://api.你的域名.com

DATABASE_URL=mysql+pymysql://zxd:与.env.docker相同的密码@mysql:3306/zxd_study?charset=utf8mb4
REDIS_URL=redis://redis:6379/0

# 微信先留空
WX_APPID=
WX_APP_SECRET=
WX_PAY_MCHID=
WX_PAY_SERIAL_NO=
WX_PAY_API_V3_KEY=

# 云老板（从开发 backend/.env 复制）
MEITUAN_BASE_URL=https://openapi.yunlaoban.vip
MEITUAN_PLATFORM=1
MEITUAN_SHOP_ID=你的shopId
MEITUAN_CLIENT_ID=你的clientId
MEITUAN_SECRET=你的secret
MEITUAN_TIMEOUT=60000
COUPON_PROVIDER=meituan

ADMIN_USERNAME=admin
ADMIN_PASSWORD=强密码
```

生成 SECRET_KEY：

```bash
openssl rand -hex 32
```

### 3.4 环境变量说明

| 变量 | 必填 | 说明 |
|------|------|------|
| `APP_ENV` | 是 | 服务器固定 `production` |
| `PRE_WECHAT_LAUNCH` | 审核期 | `true` = 未配微信时仍可用 dev 登录 + mock 支付；微信就绪后改 `false` |
| `SECRET_KEY` | 是 | ≥32 位随机串，勿用默认值 |
| `BASE_URL` | 是 | 对外 API 根地址，如 `https://api.example.com`（无 `/api` 后缀） |
| `DATABASE_URL` | 是 | Docker 内主机名必须是 `mysql`，不是 `127.0.0.1` |
| `REDIS_URL` | 是 | Docker 内为 `redis://redis:6379/0` |
| `MEITUAN_*` | 核销要 | 云老板凭证；`COUPON_PROVIDER=meituan` |
| `WX_*` | 审核后 | 审核中可留空 |
| `ADMIN_PASSWORD` | 是 | 后台登录密码，勿用 `admin123` |

### 3.5 启动容器

```bash
cd /opt/zxd-pro
docker compose -f docker-compose.prod.yml --env-file .env.docker up -d --build
```

查看状态：

```bash
docker compose -f docker-compose.prod.yml ps
curl http://127.0.0.1:8000/health
# 期望：{"status":"ok"}
```

查看日志：

```bash
docker compose -f docker-compose.prod.yml logs -f api
docker compose -f docker-compose.prod.yml logs -f mysql
```

### 3.6 初始化数据库（仅首次）

```bash
docker compose -f docker-compose.prod.yml --env-file .env.docker exec api python scripts/init_production.py
```

- 创建所有表
- 执行 `seed.py`（门店、座位、价格、团购映射等）

**注意：以后更新代码不要重复执行**，否则会重新 seed，可能覆盖生产数据。

部署自检：

```bash
docker compose -f docker-compose.prod.yml --env-file .env.docker exec api python scripts/deploy_check.py
```

### 3.7 部署后台前端

```bash
cd /opt/zxd-pro/admin-web
npm install
echo 'VITE_API_BASE=https://api.你的域名.com/api' > .env.production
npm run build

sudo mkdir -p /var/www/zxd-admin
sudo cp -r dist/* /var/www/zxd-admin/
```

也可在 Windows 本机构建后，只上传 `admin-web/dist/` 到服务器。

### 3.8 配置 Nginx（HTTPS）

已有 SSL 证书时（Let's Encrypt 示例）：

```bash
cd /opt/zxd-pro
chmod +x deploy/configure-nginx.sh

export API_DOMAIN=api.你的域名.com
export ADMIN_DOMAIN=admin.你的域名.com
export SSL_CERT=/etc/letsencrypt/live/api.你的域名.com/fullchain.pem
export SSL_KEY=/etc/letsencrypt/live/api.你的域名.com/privkey.pem

sudo ./deploy/configure-nginx.sh
```

验证：

```bash
curl https://api.你的域名.com/health
# 浏览器打开 https://admin.你的域名.com
```

**暂无 HTTPS / 备案前**：参考 `deploy/nginx-http.conf.example`（仅内测，小程序真机仍须 HTTPS 域名）。

### 3.9 小程序指向服务器

编辑 `miniprogram/config.js`：

```javascript
const API_BASE = 'https://api.你的域名.com/api'
```

微信审核中：开发者工具 → **勾选**「不校验合法域名」。  
审核通过后：公众平台配置合法域名，并 **取消** 勾选。

---

## 四、笔记本当服务器（不用 Docker）

适合本机已有 SQLite 数据、局域网联调。

### 4.1 启动

```powershell
cd f:\zxd-pro\backend
$env:PYTHONPATH="f:\zxd-pro\backend"
.\.venv\Scripts\uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### 4.2 查局域网 IP

```powershell
ipconfig
# 例如 192.168.1.100
```

### 4.3 小程序

`miniprogram/config.js`：

```javascript
const API_BASE = 'http://192.168.1.100:8000/api'
```

Windows 防火墙需放行 **8000** 端口。

### 4.4 与 Docker 服务器的关系

| | 笔记本 SQLite | 服务器 Docker MySQL |
|--|---------------|---------------------|
| 数据文件 | `backend/zxd_study.db` | Docker 卷 `mysql_data` |
| 是否同步 | ❌ 不自动同步 | 部署时 `init_production.py` 新建 |
| 本机测试订单 | 在 SQLite 里 | 不会自动过去 |

上线时一般以 **服务器 MySQL 为准**；本机 SQLite 仅作开发。

---

## 五、一键脚本（可选）

服务器上已配好 `backend/.env` 和 `.env.docker` 后：

```bash
chmod +x deploy/setup-server.sh
./deploy/setup-server.sh
```

会执行：`docker compose up` → 健康检查 → 询问是否 `init_production.py` → `deploy_check.py`。

---

## 六、日常运维

```bash
cd /opt/zxd-pro

# 查看容器
docker compose -f docker-compose.prod.yml ps

# 重启 API
docker compose -f docker-compose.prod.yml --env-file .env.docker restart api

# 更新代码后重建
git pull
docker compose -f docker-compose.prod.yml --env-file .env.docker up -d --build

# 备份 MySQL
docker exec zxd-mysql mysqldump -uzxd -p zxd_study > backup_$(date +%F).sql

# 停止（保留数据）
docker compose -f docker-compose.prod.yml --env-file .env.docker down

# 停止并删除数据卷（慎用！）
docker compose -f docker-compose.prod.yml --env-file .env.docker down -v
```

---

## 七、微信审核通过后

1. 填写 `backend/.env` 中 `WX_APPID`、`WX_APP_SECRET`、支付证书（`backend/certs/`）
2. `PRE_WECHAT_LAUNCH=false`
3. 公众平台配置 request 合法域名
4. 重启 API：`docker compose ... restart api`
5. 详见 [DEPLOY.md](./DEPLOY.md) 第二节「微信小程序」

---

## 八、常见问题

**Q: 还要在服务器上 apt install mysql 吗？**  
A: 不用。Docker compose 会拉 `mysql:8.0` 镜像并自动建库 `zxd_study`。

**Q: `curl 127.0.0.1:8000/health` 失败**  
A: 看 `docker compose logs api`；常见原因是 `backend/.env` 配错，或 MySQL 尚未 healthy。

**Q: `DATABASE_URL` 密码和 `.env.docker` 不一致**  
A: API 连不上 MySQL。两处 `MYSQL_PASSWORD` 必须相同。

**Q: 后台能开，登录失败**  
A: 检查 `ADMIN_PASSWORD`；确认 `VITE_API_BASE` 指向正确的 `https://api.xxx.com/api`。

**Q: 团购兑换 400**  
A: 检查云老板凭证、`COUPON_PROVIDER=meituan`、后台团购映射；缺映射看「待配置团购」。

**Q: 本机 SQLite 数据怎么迁到服务器？**  
A: 默认不迁移。生产用 `init_production.py` 重新 seed；历史订单需自行导出导入。

**Q: `PRE_WECHAT_LAUNCH=true` 时 mock 支付能用吗？**  
A: 能。未配置 `WX_PAY_MCHID` 时，审核期可用 mock 支付联调期限卡流程。

---

## 九、文件清单

| 文件 | 作用 |
|------|------|
| `docker-compose.prod.yml` | MySQL + Redis + API 三容器 |
| `.env.docker` | MySQL root/用户密码（compose 用） |
| `backend/.env` | 应用配置（勿提交 Git） |
| `backend/.env.production.example` | 配置模板 |
| `deploy/prepare-production-env.ps1` | Windows 生成 `.env.docker` |
| `deploy/setup-server.sh` | Linux 一键启动 |
| `deploy/configure-nginx.sh` | Nginx HTTPS 反代 |
| `deploy/nginx.conf.example` | Nginx 配置参考 |
| `deploy/nginx-http.conf.example` | 备案前 HTTP 参考 |
