# 部署完成后 · 下一步

API + 后台已上线后，按本清单继续（**微信审核中可跳过 B 节**）。

前置：服务器上 `curl http://127.0.0.1:8000/health` 返回 `{"status":"ok"}`，后台能登录。

---

## 步骤 1：小程序指向服务器

编辑 `miniprogram/config.js`，把 `PROD_API_BASE` 改成你的线上地址：

```javascript
const USE_PROD = true
const PROD_API_BASE = 'https://api.你的域名.com/api'   // ← 改这里
const DEV_API_BASE = 'http://127.0.0.1:8000/api'
const API_BASE = USE_PROD ? PROD_API_BASE : DEV_API_BASE
```

微信开发者工具：

1. 重新 **编译**
2. **详情 → 本地设置** → 勾选「不校验合法域名」（审核通过后再关）
3. 真机预览前确认手机能访问该 HTTPS 域名

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
| **数据总览** | 能打开，无报错 |
| **座位管理** | 24 座启用；按门店实际调整 |
| **团购映射** | seed 自带映射是否齐全；缺的开源 dealId 补上 |
| **待配置团购** | 若有记录 → **一键配置** → 让用户用同券再兑一次 |
| **订单列表** | 能查到测试单 |

云老板凭证在 `backend/.env` 的 `MEITUAN_*`，改后需：

```bash
docker compose -f docker-compose.prod.yml --env-file .env.docker restart api
```

---

## 步骤 4：业务联调（每种卡各测 1 次）

在小程序走完整链路：**兑换 → 我的期限卡 → 选座预约 → 期限卡支付**。

| 卡种 | 验证点 |
|------|--------|
| 小时卡 | 扣小时数 |
| 天卡 | 约 1 次预约即核销 |
| 周卡 | 约 1 次预约即核销 |
| 月卡 / 季卡 | 约 1 次预约即核销 |
| 次卡 | 连选 N 天扣 N 次 |
| 夜读月卡 | 夜读时段 + 1 次核销 |

美团 **真实券** 在 `COUPON_PROVIDER=meituan` 下测试；缺映射时不应核销，应进「待配置团购」。

微信支付未配置时：选「微信支付」会返回 mock 参数，订单页可走 mock-pay（需 `PRE_WECHAT_LAUNCH=true`）。

---

## 步骤 5：仍跳过（等微信）

- 公众平台合法域名、真实微信登录
- 真实微信支付、手机号组件
- 通通锁真机（D 节，`TTLOCK_*` + 企业 AppID）

微信下来后见 [DEPLOY.md](./DEPLOY.md) 第二节，并把 `PRE_WECHAT_LAUNCH=false`。

---

## 步骤 6：日常备份（建议现在就设）

```bash
# 手动备份
docker exec zxd-mysql mysqldump -uzxd -p zxd_study > backup_$(date +%F).sql

# 可加 crontab 每日 3 点（密码用 .env.docker 里的）
# 0 3 * * * docker exec zxd-mysql mysqldump -uzxd -p'密码' zxd_study > /backup/zxd_$(date +\%F).sql
```

---

## 验收打勾

- [ ] 公网 `/health` 正常
- [ ] 后台登录 + 各菜单无 401
- [ ] 小程序能登录（dev_openid）
- [ ] 至少 1 张真实美团券兑换成功
- [ ] 期限卡预约 + 支付成功
- [ ] 待配置团购流程走通
- [ ] `deploy_check.py` 通过
- [ ] `smoke_remote.py` 通过

全部完成后，进入 **微信/商户审核通过 → 切 PRE_WECHAT_LAUNCH=false → 真机验收 → 提审**。

---

## 相关文档

- 部署配置：[SERVER-SETUP.md](./SERVER-SETUP.md)
- 上线总览：[DEPLOY.md](./DEPLOY.md)
