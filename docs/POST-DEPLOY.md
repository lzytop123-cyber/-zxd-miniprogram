# 部署完成后 · 下一步

API + 后台已上线后，按本清单完成自检、运营配置与生产验收。

> 生产模式（`APP_ENV=production`）强制要求 `PRE_WECHAT_LAUNCH=false`，后端会自动禁用 `dev_openid` 与 `mock-pay` 接口，所有登录和支付均走真实微信链路。

前置：服务器上 `curl http://127.0.0.1:8000/health` 返回 `{"status":"ok", ...}`，管理后台可正常登录。

---

## 步骤 1：小程序指向服务器

编辑 `miniprogram/config.js`，把 `PROD_API_BASE` 和 `PROD_STATIC_BASE` 改成你的线上 HTTPS 域名（真机调试 / 体验版 / 正式版会自动走生产地址；仅开发者工具模拟器走本地开发地址）：

```javascript
const PROD_API_BASE = 'https://api.你的域名.com/api'
const PROD_STATIC_BASE = 'https://api.你的域名.com'
```

微信小程序公众平台与开发者工具：

1. 在公众平台「开发管理 → 开发设置 → 服务器域名」中配置 `request`、`uploadFile`、`downloadFile` 合法域名为 `https://api.你的域名.com`
2. 开发者工具重新 **编译**，真机预览/体验版确认手机能正常访问该 HTTPS 域名

---

## 步骤 2：服务器自检

在服务器上：

```bash
cd /opt/zxd-pro   # 你的项目目录
docker compose -f docker-compose.prod.yml --env-file .env.docker exec api python scripts/deploy_check.py
```

在本机对公网地址冒烟（把 URL 和密码换成你的）：

```powershell
cd f:\zxd-pro\backend
$env:PYTHONPATH="f:\zxd-pro\backend"
$env:ZXD_API_BASE="https://api.你的域名.com"
$env:ZXD_ADMIN_PASSWORD="你在 backend/.env 里设的密码"
.\.venv\Scripts\python scripts\smoke_remote.py
```

---

## 步骤 3：后台运营配置

登录 `https://admin.你的域名.com`，依次确认：

| 菜单 | 动作 |
|------|------|
| **数据总览** | 能打开，无报错，实时指标正常 |
| **座位管理** | 座位布局完整并已发布；按门店实际调整 |
| **团购映射** | 核对映射是否齐全；缺的团购商品补全映射 |
| **待配置团购** | 若有记录 → **一键配置** → 让用户用同券再兑一次 |
| **预约订单** | 能查询测试单并支持远程开门 / 换座 / 取消 |

云老板凭证在 `backend/.env` 的 `MEITUAN_*`，修改后需重启 API：

```bash
docker compose -f docker-compose.prod.yml --env-file .env.docker restart api
```

---

## 步骤 4：业务联调（每种卡各测 1 次）

在小程序走完整链路：**微信登录 → 兑换团购 / 购卡 → 我的期限卡 → 选座预约 → 支付 → 开门入座**。

| 卡种 | 验证点 |
|------|--------|
| 小时卡 | 扣小时数 |
| 天卡 | 约 1 次预约即核销 |
| 周卡 | 约 1 次预约即核销 |
| 月卡 / 季卡 | 约 1 次预约即核销 |
| 次卡 | 连选 N 天扣 N 次 |
| 夜读月卡 | 夜读时段 + 1 次核销 |

- 美团 **真实券** 在 `COUPON_PROVIDER=meituan` 下测试；缺映射时不应核销，应进「待配置团购」。
- 微信支付使用小额真实支付单验证下单、回调与退款闭环，并确认 `WX_PAY_PUBLIC_KEY_PATH=./certs/pub_key.pem` 等证书配置正确。

---

## 步骤 5：硬件与扩展能力核对

- 确认通通锁真机凭证（`TTLOCK_*`）及门锁电量刷新、远程开门、蓝牙开门均正常
- 如已开通微信订阅消息，在 `backend/.env` 配置 `WX_SUBSCRIBE_*_TMPL_ID` 模板 ID

更多上线配置见 [DEPLOY.md](./DEPLOY.md)。

---

## 步骤 6：日常备份（建议现在就设）

```bash
set -euo pipefail
umask 077
backup="/backup/zxd_$(date +%F_%H%M%S)"
mkdir -p "$backup"
# 密码从 MySQL 容器自身环境取得，不写到命令行或日志。
docker exec zxd-mysql sh -c 'MYSQL_PWD="$MYSQL_PASSWORD" exec mysqldump -uzxd --single-transaction --no-tablespaces zxd_study' > "$backup/database.sql"
test -s "$backup/database.sql"
paths=(backend/uploads backend/data backend/.env .env.docker)
[[ ! -d backend/certs ]] || paths+=(backend/certs)
tar -czf "$backup/files.tar.gz" "${paths[@]}"
sha256sum "$backup/database.sql" "$backup/files.tar.gz" > "$backup/SHA256SUMS"
```

将脚本保存为服务器受限权限文件后加入每日定时任务，监测退出码并将加密副本同步到异机。备份含用户数据、商户私钥及密码，限制读取权限；部署更新必须保留 `backend/uploads`，其容器挂载是 `/app/uploads`。

定期在隔离容器演练恢复；以下命令只创建临时 MySQL，不映射端口、不接生产网络。将 `backup` 指向某次备份，先校验散列，再恢复：

```bash
set -euo pipefail
sha256sum -c "$backup/SHA256SUMS"
export MYSQL_ROOT_PASSWORD="$(openssl rand -hex 32)"
docker run -d --name zxd-restore-check --network none \
  -e MYSQL_ROOT_PASSWORD -e MYSQL_DATABASE=zxd_restore mysql:8.0
unset MYSQL_ROOT_PASSWORD
for i in $(seq 1 60); do
  if docker exec zxd-restore-check sh -c 'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysqladmin -uroot ping --silent' >/dev/null 2>&1; then break; fi
  sleep 2
done
docker exec -i zxd-restore-check sh -c 'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" exec mysql -uroot zxd_restore' < "$backup/database.sql"
docker exec zxd-restore-check sh -c 'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" exec mysql -uroot zxd_restore -e "SELECT COUNT(*) AS orders FROM reservations; SELECT COUNT(*) AS users FROM users;"'
mkdir -p "$backup/restore-files-check"
tar -xzf "$backup/files.tar.gz" -C "$backup/restore-files-check"
```

对照该备份时间点的业务台账检查订单、用户、余额/期限卡、价格和团购映射，并打开抽样上传图片。通过后记录备份时间、恢复耗时和核对结果，再删除临时容器 `docker rm -f -v zxd-restore-check`。真实事故恢复需先停写业务并备份当前状态，将已验证备份恢复到新库/新目录，审阅配置与文件权限，再切换服务、自检和真机验收；不要在运行中的生产库直接试导入。

---

## 验收打勾

- [ ] 公网 `/health` 正常，容器 healthcheck 为 healthy
- [ ] 后台登录 + 各菜单无 401
- [ ] 小程序真机微信登录 + 手机号绑定正常
- [ ] 真实微信支付 + 退款回调正常
- [ ] 至少 1 张真实团购券兑换成功
- [ ] 期限卡预约 + 支付 + 开门入座成功
- [ ] 待配置团购流程走通
- [ ] `deploy_check.py` 通过
- [ ] `smoke_remote.py` 通过

---

## 相关文档

- 部署配置：[SERVER-SETUP.md](./SERVER-SETUP.md)
- 上线总览：[DEPLOY.md](./DEPLOY.md)
