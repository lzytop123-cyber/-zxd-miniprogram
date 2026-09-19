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

        <div class="tabs">
          <button type="button" class="tab" :class="{ active: tab === 'password' }" @click="tab = 'password'">
            <el-icon><Key /></el-icon><span>账号密码</span>
          </button>
          <button type="button" class="tab" :class="{ active: tab === 'qr' }" @click="tab = 'qr'">
            <el-icon><Grid /></el-icon><span>扫码登录</span>
          </button>
          <span class="tab-indicator" :style="{ transform: `translateX(${tab === 'qr' ? '100%' : '0'})` }"></span>
        </div>

        <transition name="swap" mode="out-in">
          <el-form v-if="tab === 'password'" key="pw" :model="form" @submit.prevent="onSubmit" class="form">
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

          <div v-else key="qr" class="qr-panel">
            <div class="qr-frame">
              <svg class="qr" viewBox="0 0 220 220" xmlns="http://www.w3.org/2000/svg" aria-label="扫码登录二维码">
                <rect width="220" height="220" fill="#fff" rx="8" />
                <g fill="#0a0b0d">
                  <rect v-for="(c, i) in qrCells" :key="i" :x="10 + c.x * 9" :y="10 + c.y * 9" width="9" height="9" />
                </g>
                <!-- 三个定位框 -->
                <g>
                  <rect x="10" y="10" width="63" height="63" fill="#0a0b0d" />
                  <rect x="19" y="19" width="45" height="45" fill="#fff" />
                  <rect x="28" y="28" width="27" height="27" fill="#0a0b0d" />

                  <rect x="147" y="10" width="63" height="63" fill="#0a0b0d" />
                  <rect x="156" y="19" width="45" height="45" fill="#fff" />
                  <rect x="165" y="28" width="27" height="27" fill="#0a0b0d" />

                  <rect x="10" y="147" width="63" height="63" fill="#0a0b0d" />
                  <rect x="19" y="156" width="45" height="45" fill="#fff" />
                  <rect x="28" y="165" width="27" height="27" fill="#0a0b0d" />
                </g>
                <!-- 中央品牌 -->
                <rect x="80" y="80" width="60" height="60" fill="#fff" rx="10" />
                <rect x="86" y="86" width="48" height="48" fill="url(#brand-grad)" rx="12" />
                <text x="110" y="123" text-anchor="middle" font-size="30" font-weight="700" fill="#1a1a1a" font-family="-apple-system, PingFang SC, sans-serif">知</text>
                <defs>
                  <linearGradient id="brand-grad" x1="0" y1="0" x2="1" y2="1">
                    <stop offset="0%" stop-color="#FFD000" />
                    <stop offset="100%" stop-color="#ffb400" />
                  </linearGradient>
                </defs>
              </svg>
              <div class="qr-scan-line" aria-hidden="true"></div>
            </div>
            <p class="qr-hint">请使用「知行岛管理员」小程序扫码</p>
            <p class="qr-sub">首次使用请先在小程序内绑定账号 · <a class="link" @click.prevent="refreshQr">刷新</a></p>
          </div>
        </transition>

        <div class="card-foot">
          <span>首次登录请联系管理员开通账号</span>
        </div>
      </section>
    </div>

    <footer class="page-foot">仅限授权人员登录 · © {{ year }} 知行岛</footer>
  </div>
</template>

<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { User, Lock, Right, OfficeBuilding, Wallet, DataAnalysis, Key, Grid } from '@element-plus/icons-vue'
import http from '../api/http'

const router = useRouter()
const loading = ref(false)
const remember = ref(true)
const tab = ref<'password' | 'qr'>('password')
const form = reactive({ username: '', password: '' })
const year = new Date().getFullYear()
const version = '2.0'

// 生成一个"看起来像 QR"的静态点阵；跳过定位框和中央 logo 区域。
const qrSeed = ref(42)
const qrCells = computed(() => {
  let seed = qrSeed.value
  const rng = () => { seed = (seed * 9301 + 49297) % 233280; return seed / 233280 }
  const out: { x: number, y: number }[] = []
  for (let y = 0; y < 21; y++) {
    for (let x = 0; x < 21; x++) {
      const inMarker = (x < 8 && y < 8) || (x > 12 && y < 8) || (x < 8 && y > 12)
      const inCenter = x >= 8 && x <= 12 && y >= 8 && y <= 12
      if (inMarker || inCenter) continue
      if (rng() < 0.48) out.push({ x, y })
    }
  }
  return out
})
function refreshQr() { qrSeed.value = Math.floor(Math.random() * 999) + 1 }

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
    localStorage.setItem('admin_token', res.data.token)
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

/* 登录方式 tabs */
.tabs {
  position: relative;
  display: grid; grid-template-columns: 1fr 1fr;
  padding: 4px; margin-bottom: 22px;
  background: rgba(255,255,255,0.03);
  border: 1px solid rgba(255,255,255,0.07);
  border-radius: 12px;
  isolation: isolate;
}
.tab {
  position: relative; z-index: 2;
  display: inline-flex; align-items: center; justify-content: center; gap: 6px;
  padding: 9px 12px; border: 0; background: transparent;
  color: #909096; font-size: 13px; font-weight: 500;
  cursor: pointer; border-radius: 8px;
  transition: color 0.25s ease;
}
.tab.active { color: #1a1a1a; }
.tab:not(.active):hover { color: #d0d0d6; }
.tab-indicator {
  position: absolute; z-index: 1;
  top: 4px; bottom: 4px; left: 4px; width: calc(50% - 4px);
  background: linear-gradient(135deg, #FFD000, #ffb400);
  border-radius: 8px;
  box-shadow: 0 4px 14px rgba(255, 208, 0, 0.35);
  transition: transform 0.35s cubic-bezier(0.16, 1, 0.3, 1);
}

/* 面板切换动画 */
.swap-enter-active, .swap-leave-active { transition: opacity 0.25s ease, transform 0.25s ease; }
.swap-enter-from { opacity: 0; transform: translateY(6px); }
.swap-leave-to   { opacity: 0; transform: translateY(-6px); }

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

/* QR 面板 */
.qr-panel {
  display: flex; flex-direction: column; align-items: center;
  gap: 14px; padding: 4px 0 10px;
}
.qr-frame {
  position: relative;
  width: 200px; height: 200px;
  padding: 10px; border-radius: 16px;
  background: #fff;
  box-shadow: 0 8px 28px rgba(255, 208, 0, 0.15), 0 0 0 1px rgba(255, 208, 0, 0.25);
  overflow: hidden;
}
.qr-frame::before, .qr-frame::after,
.qr-frame > .qr-scan-line::before, .qr-frame > .qr-scan-line::after {
  /* 四角装饰 */
  content: ''; position: absolute; width: 14px; height: 14px;
  border-color: #FFD000; border-style: solid; border-width: 0; pointer-events: none;
}
.qr-frame::before      { top: -1px; left: -1px; border-top-width: 2px; border-left-width: 2px; border-top-left-radius: 8px; }
.qr-frame::after       { top: -1px; right: -1px; border-top-width: 2px; border-right-width: 2px; border-top-right-radius: 8px; }
.qr-scan-line::before  { bottom: -1px; left: -1px; border-bottom-width: 2px; border-left-width: 2px; border-bottom-left-radius: 8px; }
.qr-scan-line::after   { bottom: -1px; right: -1px; border-bottom-width: 2px; border-right-width: 2px; border-bottom-right-radius: 8px; }
.qr { width: 100%; height: 100%; display: block; }
.qr-scan-line {
  position: absolute; left: 12px; right: 12px; height: 2px;
  background: linear-gradient(90deg, transparent, #FFD000 30%, #FFD000 70%, transparent);
  box-shadow: 0 0 12px rgba(255, 208, 0, 0.7);
  animation: scan 2.4s cubic-bezier(0.4, 0, 0.6, 1) infinite;
}
@keyframes scan {
  0%       { top: 14px;  opacity: 0; }
  10%      { opacity: 1; }
  90%      { opacity: 1; }
  100%     { top: 184px; opacity: 0; }
}
.qr-hint { margin: 6px 0 0; color: #d0d0d6; font-size: 13.5px; letter-spacing: 0.3px; }
.qr-sub  { margin: 0; color: #6b6b73; font-size: 12px; letter-spacing: 0.2px; }

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
  .blob, .stage, .stage > *, .live-dot, .qr-scan-line { animation: none; }
}
</style>
