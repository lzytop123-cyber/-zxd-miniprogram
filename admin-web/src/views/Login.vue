<template>
  <div class="login-page" @pointermove="onMove">
    <div class="aurora" aria-hidden="true">
      <span class="blob b1"></span>
      <span class="blob b2"></span>
      <span class="blob b3"></span>
    </div>
    <div class="grid" aria-hidden="true"></div>
    <div class="spotlight" aria-hidden="true"></div>

    <div class="stage">
      <!-- 左：品牌 · 卖点 · 数据 -->
      <section class="pitch">
        <div class="brand-mark">
          <div class="logo">知</div>
          <div>
            <div class="brand-name">知行岛</div>
            <div class="brand-sub">自习室智能管理平台</div>
          </div>
        </div>

        <h1 class="headline">
          让门店<span class="accent">自己会打理</span><br />
          你只管服务学员
        </h1>

        <ul class="features">
          <li>
            <span class="dot"><el-icon><OfficeBuilding /></el-icon></span>
            <div><b>座位与门锁</b><i>可视化排位、远程/蓝牙一键开门</i></div>
          </li>
          <li>
            <span class="dot"><el-icon><Wallet /></el-icon></span>
            <div><b>四渠道对账</b><i>美团 · 抖音 · 微信支付 · 微信转账</i></div>
          </li>
          <li>
            <span class="dot"><el-icon><DataAnalysis /></el-icon></span>
            <div><b>会员与卡券闭环</b><i>购卡、核销、退款、提醒全流程</i></div>
          </li>
        </ul>

        <div class="stats">
          <span class="pill"><i class="live-dot"></i>生产环境</span>
          <span class="stat">v {{ version }}</span>
        </div>
      </section>

      <!-- 右：登录卡 -->
      <section class="login-card">
        <div class="card-top-glow" aria-hidden="true"></div>

        <div class="card-head">
          <h2>欢迎回来</h2>
          <p>登录后进入后台管理</p>
        </div>

          <el-form :model="form" @submit.prevent="onSubmit" class="form">
            <el-input v-model="form.username" placeholder="用户名" size="large" :prefix-icon="User" autocomplete="username" />
            <el-input v-model="form.password" placeholder="密码" size="large" type="password" show-password :prefix-icon="Lock" autocomplete="current-password" @keyup.enter="onSubmit" />
            <div class="options">
              <el-checkbox v-model="remember">记住登录状态</el-checkbox>
              <a class="link" @click.prevent="onForgot">忘记密码？</a>
            </div>
            <el-button type="primary" native-type="submit" :loading="loading" class="btn" size="large">
              <span>登 录</span>
              <el-icon class="btn-arrow"><Right /></el-icon>
            </el-button>
          </el-form>


        <div class="card-foot">
          <span>首次登录请联系管理员开通账号</span>
        </div>
      </section>
    </div>

    <footer class="page-foot">仅限授权人员登录 · © {{ year }} 知行岛</footer>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { User, Lock, Right, OfficeBuilding, Wallet, DataAnalysis } from '@element-plus/icons-vue'
import http from '../api/http'
import { saveAdminSession, setAdminPermissions } from '../utils/adminAuth'

const router = useRouter()
const loading = ref(false)
const remember = ref(true)
const form = reactive({ username: '', password: '' })
const year = new Date().getFullYear()
const version = '2.0'

function onMove(e: PointerEvent) {
  const el = e.currentTarget as HTMLElement
  el.style.setProperty('--mx', `${e.clientX}px`)
  el.style.setProperty('--my', `${e.clientY}px`)
}

function onForgot() {
  ElMessage.info('请联系系统管理员重置密码')
}

async function onSubmit() {
  if (!form.username || !form.password) {
    ElMessage.warning('请输入用户名和密码')
    return
  }
  loading.value = true
  try {
    const res = await http.post('/admin/login', form)
    saveAdminSession({
      token: res.data.token,
      username: res.data.username,
      name: res.data.name,
      role: res.data.role || 'hq',
      store_id: res.data.store_id,
      store_name: res.data.store_name,
      permissions: Array.isArray(res.data.permissions) ? res.data.permissions : undefined,
    }, remember.value)
    try {
      const me = await http.get('/admin/me')
      if (Array.isArray(me.data?.permissions)) {
        setAdminPermissions(me.data.permissions)
      }
    } catch {
      /* login permissions already stored */
    }
    ElMessage.success('登录成功')
    router.push('/dashboard')
  } catch (e: any) {
    ElMessage.error(e.message || '登录失败')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-page {
  position: relative;
  min-height: 100vh;
  display: flex; align-items: center; justify-content: center;
  padding: 40px 24px;
  background: #0a0b0d;
  color: #e6e6e8;
  overflow: hidden;
  font-family: -apple-system, BlinkMacSystemFont, "PingFang SC", "Microsoft YaHei", "Segoe UI", sans-serif;
}

.aurora { position: absolute; inset: 0; z-index: 0; overflow: hidden; }
.blob {
  position: absolute; display: block; border-radius: 50%;
  filter: blur(90px); animation: drift 22s ease-in-out infinite;
  will-change: transform;
}
.b1 { width: 640px; height: 640px; background: radial-gradient(circle, #FFD000, transparent 65%); top: -180px; left: -140px; opacity: 0.55; }
.b2 { width: 560px; height: 560px; background: radial-gradient(circle, #6366f1, transparent 65%); bottom: -180px; right: -140px; animation-delay: -8s; opacity: 0.50; }
.b3 { width: 460px; height: 460px; background: radial-gradient(circle, #22d3ee, transparent 65%); top: 46%; left: 52%; animation-delay: -14s; opacity: 0.28; }
@keyframes drift {
  0%, 100% { transform: translate(0, 0) scale(1); }
  33%      { transform: translate(60px, -40px) scale(1.06); }
  66%      { transform: translate(-40px, 30px) scale(0.94); }
}

.grid {
  position: absolute; inset: 0; z-index: 1; pointer-events: none;
  background-image:
    linear-gradient(rgba(255,255,255,0.05) 1px, transparent 1px),
    linear-gradient(90deg, rgba(255,255,255,0.05) 1px, transparent 1px);
  background-size: 48px 48px;
  mask-image: radial-gradient(ellipse at center, black 25%, transparent 70%);
  -webkit-mask-image: radial-gradient(ellipse at center, black 25%, transparent 70%);
}
.spotlight {
  position: absolute; inset: 0; z-index: 1; pointer-events: none;
  background: radial-gradient(560px circle at var(--mx, 50%) var(--my, 50%),
    rgba(255, 208, 0, 0.10), transparent 60%);
  transition: background 0.15s ease-out;
}

/* 双栏舞台 */
.stage {
  position: relative; z-index: 2;
  display: grid;
  grid-template-columns: minmax(0, 1.05fr) minmax(0, 0.95fr);
  gap: 72px;
  align-items: center;
  max-width: 1120px; width: 100%;
  animation: rise 0.7s cubic-bezier(0.16, 1, 0.3, 1) both;
}
@keyframes rise {
  from { opacity: 0; transform: translateY(24px); }
  to   { opacity: 1; transform: translateY(0); }
}
.stage > * { animation: fade 0.7s cubic-bezier(0.16, 1, 0.3, 1) both; }
.stage > *:nth-child(1) { animation-delay: 0.15s; }
.stage > *:nth-child(2) { animation-delay: 0.28s; }
@keyframes fade {
  from { opacity: 0; transform: translateY(12px); }
  to   { opacity: 1; transform: translateY(0); }
}

/* 左：品牌区 */
.pitch { display: flex; flex-direction: column; gap: 40px; padding: 8px 0; }
.brand-mark { display: flex; align-items: center; gap: 14px; }
.logo {
  width: 46px; height: 46px; border-radius: 12px;
  background: linear-gradient(135deg, #FFD000, #ffb400);
  color: #1a1a1a; font-weight: 700; font-size: 22px;
  display: flex; align-items: center; justify-content: center;
  box-shadow: 0 10px 26px rgba(255, 208, 0, 0.35);
}
.brand-name { font-size: 20px; font-weight: 700; color: #f5f5f7; letter-spacing: 0.5px; }
.brand-sub  { font-size: 13px; color: #909096; margin-top: 3px; letter-spacing: 0.3px; }

.headline {
  font-size: 40px; line-height: 1.25; font-weight: 700; color: #f5f5f7;
  letter-spacing: -0.5px; margin: 0;
}
.accent {
  background: linear-gradient(135deg, #FFD000, #ffb400);
  -webkit-background-clip: text; background-clip: text; color: transparent;
}

.features { list-style: none; padding: 0; margin: 0; display: flex; flex-direction: column; gap: 8px; }
.features li {
  display: flex; gap: 14px; align-items: flex-start;
  padding: 12px 14px; border-radius: 12px;
  border: 1px solid transparent;
  background: transparent;
  transition: background 0.3s ease, border-color 0.3s ease, transform 0.3s ease, box-shadow 0.3s ease;
  cursor: default;
}
.features li:hover {
  background: linear-gradient(135deg, rgba(255,208,0,0.06), rgba(99,102,241,0.04));
  border-color: rgba(255,208,0,0.18);
  transform: translateX(4px);
  box-shadow: 0 8px 32px rgba(255, 208, 0, 0.08), inset 0 1px 0 rgba(255,255,255,0.04);
}
.features .dot {
  width: 36px; height: 36px; border-radius: 10px; flex-shrink: 0;
  background: rgba(255, 208, 0, 0.10);
  border: 1px solid rgba(255, 208, 0, 0.25);
  color: #FFD000;
  display: flex; align-items: center; justify-content: center;
  font-size: 18px;
  transition: background 0.3s ease, border-color 0.3s ease, box-shadow 0.3s ease, color 0.3s ease, transform 0.3s ease;
}
.features li:hover .dot {
  background: rgba(255, 208, 0, 0.20);
  border-color: rgba(255, 208, 0, 0.55);
  color: #ffdc4d;
  box-shadow: 0 0 24px rgba(255, 208, 0, 0.35);
  transform: scale(1.06);
}
.features b { display: block; font-size: 14px; color: #e6e6e8; font-weight: 600; margin-bottom: 2px; }
.features i { font-style: normal; font-size: 12.5px; color: #808088; letter-spacing: 0.2px; transition: color 0.3s ease; }
.features li:hover i { color: #a0a0a8; }

.stats { display: flex; align-items: center; gap: 12px; }
.pill {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 4px 10px; border-radius: 999px;
  background: rgba(34, 197, 94, 0.10); border: 1px solid rgba(34, 197, 94, 0.25);
  color: #86efac; font-size: 11.5px; letter-spacing: 0.3px;
}
.live-dot {
  width: 6px; height: 6px; border-radius: 50%; background: #22c55e;
  box-shadow: 0 0 8px #22c55e;
  animation: pulse 1.6s ease-in-out infinite;
}
@keyframes pulse {
  0%, 100% { opacity: 1; transform: scale(1); }
  50%      { opacity: 0.4; transform: scale(0.85); }
}
.stat { color: #5c5c66; font-size: 11.5px; letter-spacing: 0.5px; }

/* 右：登录卡 */
.login-card {
  position: relative;
  padding: 44px 40px 32px;
  background: rgba(18, 20, 26, 0.62);
  backdrop-filter: blur(28px) saturate(180%);
  -webkit-backdrop-filter: blur(28px) saturate(180%);
  border: 1px solid rgba(255,255,255,0.09);
  border-radius: 20px;
  box-shadow: 0 40px 100px rgba(0,0,0,0.5), inset 0 1px 0 rgba(255,255,255,0.06);
  overflow: hidden;
}
.login-card::before {
  content: ''; position: absolute; inset: -1px; border-radius: 20px; pointer-events: none;
  background: linear-gradient(135deg, rgba(255, 208, 0, 0.3), transparent 30%, transparent 70%, rgba(99, 102, 241, 0.25));
  -webkit-mask: linear-gradient(#000 0 0) content-box, linear-gradient(#000 0 0);
  mask: linear-gradient(#000 0 0) content-box, linear-gradient(#000 0 0);
  -webkit-mask-composite: xor; mask-composite: exclude;
  padding: 1px; opacity: 0.7;
}
.card-top-glow {
  position: absolute; left: 20%; right: 20%; top: 0; height: 1px;
  background: linear-gradient(90deg, transparent, #FFD000, transparent);
  opacity: 0.7;
}

.card-head { margin-bottom: 20px; }
.card-head h2 { margin: 0; font-size: 22px; color: #f5f5f7; font-weight: 600; letter-spacing: 0.5px; }
.card-head p  { margin: 6px 0 0; font-size: 13px; color: #7c7c86; }

.form { display: flex; flex-direction: column; gap: 14px; }

:deep(.el-input__wrapper) {
  background: rgba(255,255,255,0.04) !important;
  box-shadow: 0 0 0 1px rgba(255,255,255,0.08) inset !important;
  border-radius: 12px;
  padding: 6px 16px;
  transition: box-shadow 0.2s;
}
:deep(.el-input__wrapper:hover)   { box-shadow: 0 0 0 1px rgba(255,255,255,0.18) inset !important; }
:deep(.el-input__wrapper.is-focus){ box-shadow: 0 0 0 1px rgba(255, 208, 0, 0.55) inset, 0 0 0 4px rgba(255, 208, 0, 0.08) !important; }
:deep(.el-input__inner) { color: #f5f5f7; height: 44px; font-size: 14px; }
:deep(.el-input__inner::placeholder) { color: #6b6b73; }
:deep(.el-input__prefix-inner), :deep(.el-input__suffix-inner) { color: #909096; }

.options {
  display: flex; align-items: center; justify-content: space-between;
  margin: 2px 2px 4px;
}
:deep(.el-checkbox__label) { color: #909096; font-size: 12.5px; }
:deep(.el-checkbox__inner) { background: transparent; border-color: rgba(255,255,255,0.2); }
:deep(.el-checkbox__input.is-checked .el-checkbox__inner) { background: #FFD000; border-color: #FFD000; }
:deep(.el-checkbox__input.is-checked .el-checkbox__inner::after) { border-color: #1a1a1a; }
:deep(.el-checkbox__input.is-checked + .el-checkbox__label) { color: #e6e6e8; }
.link { font-size: 12.5px; color: #909096; cursor: pointer; letter-spacing: 0.2px; transition: color 0.15s; }
.link:hover { color: #FFD000; }

.btn {
  position: relative;
  height: 48px; margin-top: 6px; border-radius: 12px;
  background: linear-gradient(135deg, #FFD000, #ffb400) !important;
  border: none !important; color: #1a1a1a !important;
  font-weight: 600; letter-spacing: 6px; font-size: 15px;
  box-shadow: 0 10px 28px rgba(255, 208, 0, 0.3);
  transition: transform 0.2s, box-shadow 0.2s;
  display: flex; align-items: center; justify-content: center; gap: 8px;
}
.btn:hover:not(.is-loading) {
  transform: translateY(-1px);
  box-shadow: 0 14px 34px rgba(255, 208, 0, 0.42);
}
.btn:hover .btn-arrow { transform: translateX(4px); }
.btn-arrow { font-size: 16px; transition: transform 0.2s; }

.card-foot {
  margin-top: 22px; padding-top: 20px;
  border-top: 1px dashed rgba(255,255,255,0.08);
  text-align: center; font-size: 11.5px; color: #5c5c66; letter-spacing: 0.4px;
}

.page-foot {
  position: absolute; left: 0; right: 0; bottom: 20px;
  text-align: center; z-index: 2;
  font-size: 11px; color: #4a4a52; letter-spacing: 0.6px;
}

/* 小屏：折叠回单栏 */
@media (max-width: 900px) {
  .stage { grid-template-columns: 1fr; gap: 36px; max-width: 460px; }
  .pitch { text-align: left; }
  .headline { font-size: 30px; }
  .features { gap: 14px; }
  .login-card { padding: 36px 28px 26px; }
}

@media (prefers-reduced-motion: reduce) {
  .blob, .stage, .stage > *, .live-dot { animation: none; }
}
</style>
