<template>
  <div class="login-page">
    <div class="aurora" aria-hidden="true">
      <span class="blob b1"></span>
      <span class="blob b2"></span>
      <span class="blob b3"></span>
    </div>
    <div class="grid" aria-hidden="true"></div>

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
.b1 { width: 520px; height: 520px; background: radial-gradient(circle, #FFD000, transparent 65%); top: -160px; left: -120px; }
.b2 { width: 480px; height: 480px; background: radial-gradient(circle, #6366f1, transparent 65%); bottom: -140px; right: -160px; animation-delay: -8s; }
.b3 { width: 380px; height: 380px; background: radial-gradient(circle, #22d3ee, transparent 65%); top: 40%; left: 60%; animation-delay: -14s; opacity: 0.35; }

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
  background-size: 44px 44px;
  mask-image: radial-gradient(ellipse at center, black 30%, transparent 75%);
  -webkit-mask-image: radial-gradient(ellipse at center, black 30%, transparent 75%);
}

.login-card {
  position: relative; z-index: 2;
  width: 400px; max-width: calc(100vw - 32px);
  padding: 40px 36px 28px;
  background: rgba(18, 20, 26, 0.55);
  backdrop-filter: blur(24px) saturate(180%);
  -webkit-backdrop-filter: blur(24px) saturate(180%);
  border: 1px solid rgba(255,255,255,0.08);
  border-radius: 18px;
  box-shadow: 0 30px 80px rgba(0,0,0,0.45), inset 0 1px 0 rgba(255,255,255,0.05);
  animation: rise 0.7s cubic-bezier(0.16, 1, 0.3, 1) both;
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

.brand { display: flex; align-items: center; gap: 12px; margin-bottom: 32px; }
.logo {
  width: 40px; height: 40px; border-radius: 10px;
  background: linear-gradient(135deg, #FFD000, #ffb400);
  color: #1a1a1a; font-weight: 700; font-size: 20px;
  display: flex; align-items: center; justify-content: center;
  box-shadow: 0 6px 20px rgba(255, 208, 0, 0.35);
}
.brand-name { font-size: 18px; font-weight: 600; color: #f5f5f7; letter-spacing: 0.5px; }
.brand-sub  { font-size: 12px; color: #909096; margin-top: 2px; letter-spacing: 0.3px; }

.form { display: flex; flex-direction: column; gap: 14px; }

:deep(.el-input__wrapper) {
  background: rgba(255,255,255,0.04) !important;
  box-shadow: 0 0 0 1px rgba(255,255,255,0.08) inset !important;
  border-radius: 10px;
  padding: 4px 14px;
  transition: box-shadow 0.2s;
}
:deep(.el-input__wrapper:hover)   { box-shadow: 0 0 0 1px rgba(255,255,255,0.16) inset !important; }
:deep(.el-input__wrapper.is-focus){ box-shadow: 0 0 0 1px rgba(255, 208, 0, 0.5) inset !important; }
:deep(.el-input__inner) { color: #f5f5f7; height: 42px; }
:deep(.el-input__inner::placeholder) { color: #6b6b73; }
:deep(.el-input__prefix-inner), :deep(.el-input__suffix-inner) { color: #909096; }

.btn {
  height: 44px; margin-top: 6px; border-radius: 10px;
  background: linear-gradient(135deg, #FFD000, #ffb400) !important;
  border: none !important; color: #1a1a1a !important;
  font-weight: 600; letter-spacing: 4px;
  box-shadow: 0 8px 24px rgba(255, 208, 0, 0.28);
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
