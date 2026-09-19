<template>
  <div class="login-page" @pointermove="onMove">
    <div class="aurora" aria-hidden="true">
      <span class="blob b1"></span>
      <span class="blob b2"></span>
      <span class="blob b3"></span>
    </div>
    <div class="grid" aria-hidden="true"></div>
    <div class="spotlight" aria-hidden="true"></div>

    <div class="login-card">
      <div class="brand">
        <div class="logo">知</div>
        <div class="brand-meta">
          <div class="brand-name">知行岛</div>
          <div class="brand-sub">后台管理系统</div>
        </div>
      </div>

      <el-form :model="form" @submit.prevent="onSubmit" class="form">
        <el-input v-model="form.username" placeholder="用户名" size="large" :prefix-icon="User" />
        <el-input v-model="form.password" placeholder="密码" size="large" type="password" show-password :prefix-icon="Lock" @keyup.enter="onSubmit" />
        <el-button type="primary" native-type="submit" :loading="loading" class="btn" size="large">登 录</el-button>
      </el-form>

      <div class="footer">仅限授权人员登录 · © {{ year }}</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { User, Lock } from '@element-plus/icons-vue'
import http from '../api/http'

const router = useRouter()
const loading = ref(false)
const form = reactive({ username: 'admin', password: 'admin123' })
const year = new Date().getFullYear()

function onMove(e: PointerEvent) {
  const el = e.currentTarget as HTMLElement
  el.style.setProperty('--mx', `${e.clientX}px`)
  el.style.setProperty('--my', `${e.clientY}px`)
}

async function onSubmit() {
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
  background: #0a0b0d;
  color: #e6e6e8;
  overflow: hidden;
  font-family: -apple-system, BlinkMacSystemFont, "PingFang SC", "Microsoft YaHei", "Segoe UI", sans-serif;
}

.aurora { position: absolute; inset: 0; z-index: 0; overflow: hidden; }
.blob {
  position: absolute; display: block; border-radius: 50%;
  filter: blur(90px); opacity: 0.55;
  animation: drift 22s ease-in-out infinite;
  will-change: transform;
}
.b1 { width: 640px; height: 640px; background: radial-gradient(circle, #FFD000, transparent 65%); top: -180px; left: -140px; opacity: 0.6; }
.b2 { width: 560px; height: 560px; background: radial-gradient(circle, #6366f1, transparent 65%); bottom: -180px; right: -140px; animation-delay: -8s; opacity: 0.55; }
.b3 { width: 460px; height: 460px; background: radial-gradient(circle, #22d3ee, transparent 65%); top: 46%; left: 52%; animation-delay: -14s; opacity: 0.32; }

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

/* Cursor spotlight: warm brand highlight follows pointer */
.spotlight {
  position: absolute; inset: 0; z-index: 1; pointer-events: none;
  background: radial-gradient(560px circle at var(--mx, 50%) var(--my, 50%),
    rgba(255, 208, 0, 0.10), transparent 60%);
  transition: background 0.15s ease-out;
}

.login-card {
  position: relative; z-index: 2;
  width: 460px; max-width: calc(100vw - 32px);
  padding: 52px 48px 36px;
  background: rgba(18, 20, 26, 0.58);
  backdrop-filter: blur(28px) saturate(180%);
  -webkit-backdrop-filter: blur(28px) saturate(180%);
  border: 1px solid rgba(255,255,255,0.09);
  border-radius: 20px;
  box-shadow: 0 40px 100px rgba(0,0,0,0.5), 0 0 0 1px rgba(255, 208, 0, 0.04), inset 0 1px 0 rgba(255,255,255,0.06);
  animation: rise 0.7s cubic-bezier(0.16, 1, 0.3, 1) both;
}
.login-card::before {
  content: ''; position: absolute; inset: -1px; border-radius: 20px; pointer-events: none;
  background: linear-gradient(135deg, rgba(255, 208, 0, 0.25), transparent 30%, transparent 70%, rgba(99, 102, 241, 0.2));
  -webkit-mask: linear-gradient(#000 0 0) content-box, linear-gradient(#000 0 0);
  mask: linear-gradient(#000 0 0) content-box, linear-gradient(#000 0 0);
  -webkit-mask-composite: xor; mask-composite: exclude;
  padding: 1px; opacity: 0.6;
}

@keyframes rise {
  from { opacity: 0; transform: translateY(24px); }
  to   { opacity: 1; transform: translateY(0); }
}

.login-card > * { animation: fade 0.6s cubic-bezier(0.16, 1, 0.3, 1) both; }
.login-card > *:nth-child(1) { animation-delay: 0.10s; }
.login-card > *:nth-child(2) { animation-delay: 0.22s; }
.login-card > *:nth-child(3) { animation-delay: 0.34s; }

@keyframes fade {
  from { opacity: 0; transform: translateY(10px); }
  to   { opacity: 1; transform: translateY(0); }
}

.brand { display: flex; align-items: center; gap: 14px; margin-bottom: 40px; }
.logo {
  width: 44px; height: 44px; border-radius: 12px;
  background: linear-gradient(135deg, #FFD000, #ffb400);
  color: #1a1a1a; font-weight: 700; font-size: 22px;
  display: flex; align-items: center; justify-content: center;
  box-shadow: 0 8px 24px rgba(255, 208, 0, 0.35);
}
.brand-name { font-size: 20px; font-weight: 600; color: #f5f5f7; letter-spacing: 0.5px; }
.brand-sub  { font-size: 12px; color: #909096; margin-top: 3px; letter-spacing: 0.3px; }

.form { display: flex; flex-direction: column; gap: 16px; }

:deep(.el-input__wrapper) {
  background: rgba(255,255,255,0.04) !important;
  box-shadow: 0 0 0 1px rgba(255,255,255,0.08) inset !important;
  border-radius: 12px;
  padding: 6px 16px;
  transition: box-shadow 0.2s;
}
:deep(.el-input__wrapper:hover)   { box-shadow: 0 0 0 1px rgba(255,255,255,0.18) inset !important; }
:deep(.el-input__wrapper.is-focus){ box-shadow: 0 0 0 1px rgba(255, 208, 0, 0.55) inset, 0 0 0 4px rgba(255, 208, 0, 0.08) !important; }
:deep(.el-input__inner) { color: #f5f5f7; height: 46px; font-size: 14px; }
:deep(.el-input__inner::placeholder) { color: #6b6b73; }
:deep(.el-input__prefix-inner), :deep(.el-input__suffix-inner) { color: #909096; }

.btn {
  height: 48px; margin-top: 10px; border-radius: 12px;
  background: linear-gradient(135deg, #FFD000, #ffb400) !important;
  border: none !important; color: #1a1a1a !important;
  font-weight: 600; letter-spacing: 6px; font-size: 15px;
  box-shadow: 0 10px 28px rgba(255, 208, 0, 0.3);
  transition: transform 0.2s, box-shadow 0.2s;
}
.btn:hover:not(.is-loading) {
  transform: translateY(-1px);
  box-shadow: 0 12px 28px rgba(255, 208, 0, 0.4);
}

.footer {
  margin-top: 24px; text-align: center;
  font-size: 11px; color: #5c5c66; letter-spacing: 0.5px;
}

@media (prefers-reduced-motion: reduce) {
  .blob, .login-card, .login-card > * { animation: none; }
}
</style>
