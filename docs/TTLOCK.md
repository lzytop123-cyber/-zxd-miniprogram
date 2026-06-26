# 通通锁配置指南

## 两种开门方式

| 方式 | 适用 | 说明 |
|------|------|------|
| **远程开门** | 个体户 / 无蓝牙插件 | 通过 WiFi 网关，小程序点「远程开门」→ 后端调 TTLock 云 API |
| **蓝牙开门** | 企业小程序 | 需在微信后台添加通通锁插件 `wx43d5971c94455481` |

---

## 1. 开放平台

1. 登录 [通通锁开放平台](https://open.sciener.com)
2. 创建应用，获取 `clientId`、`clientSecret`
3. 使用通通锁 APP 账号作为 `username`，密码填 **明文**（后端会自动 MD5）

写入 `backend/.env`：

```env
TTLOCK_CLIENT_ID=你的clientId
TTLOCK_CLIENT_SECRET=你的clientSecret
TTLOCK_USERNAME=通通锁登录手机号
TTLOCK_PASSWORD=通通锁登录密码
```

测试凭证：

```powershell
cd backend
$env:PYTHONPATH="."
python scripts/test_ttlock.py
```

---

## 2. 后台录入门锁

管理后台 → **蓝牙门锁** → 添加：

| 字段 | 来源 |
|------|------|
| lock_id | 通通锁 APP / 开放平台锁列表 |
| lock_data | 锁初始化时的 lockData（蓝牙开门用） |
| mac_address | 锁 MAC（可选） |

本地 seed 自带 mock 锁，未配 TTLock 时可用于联调。

---

## 3. WiFi 网关（远程开门）

1. 在通通锁 APP 添加 WiFi 网关并绑定门锁
2. 锁设置里打开 **「远程开锁」**
3. 小程序支付后 → 入座页 → **远程开门**

---

## 4. 蓝牙插件（企业主体）

1. 微信公众平台 → **设置 → 第三方设置 → 插件管理** → 添加 `wx43d5971c94455481`（通通锁 3.1.4）
2. 确保开发者工具登录的微信号，已在小程序后台 **成员管理** 里设为「开发者」或「管理员」
3. 将 `miniprogram/app.plugin.json` 里的 `plugins` 段合并进 `app.json`（本地联调默认不启用，避免模拟器启动失败）
4. 真机靠近门锁 → **蓝牙开门**

本地开发默认 **不加载插件**，入座页仍可用 **远程开门**。

---

## 5. 业务流程

```
用户支付成功
  → create_ble_keys_for_reservation（发钥匙 + 缓存 lockData）
  → 入座页 loadActive + loadBleKey
  → 蓝牙开门 / 远程开门
  → 记录 door_logs + 自动 checkin
```

---

## 常见问题

- **模拟器启动失败 `provider:wx43d5971c94455481 … 登录用户不是该小程序开发者`**
  1. 开发者工具右上角登录的微信号 → 必须在 [微信公众平台](https://mp.weixin.qq.com) 该小程序（`wx4d3a834429fc6538`）的 **成员管理** 中
  2. 若 `app.json` 里写了 `plugins`，本地未配插件时会直接启动失败 → 已从 `app.json` 移除，需要蓝牙时再合并 `app.plugin.json`
  3. 个体户主体通常无法添加蓝牙插件 → 直接用 **远程开门**
- **远程开门 errcode -4043**：在通通锁 APP 打开该锁的「远程开锁」开关
- **蓝牙插件未加载**：入座页会提示「需企业插件」，请用远程开门
- **钥匙未生成**：后台确认门店已添加启用中的门锁
