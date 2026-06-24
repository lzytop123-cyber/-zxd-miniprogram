<template>
  <div class="login-page">
    <el-card class="login-card">
      <h2>知行岛后台登录</h2>
      <el-form :model="form" @submit.prevent="onSubmit">
        <el-form-item label="用户名">
          <el-input v-model="form.username" placeholder="admin" />
        </el-form-item>
        <el-form-item label="密码">
          <el-input v-model="form.password" type="password" placeholder="admin123" show-password />
        </el-form-item>
        <el-button type="primary" native-type="submit" :loading="loading" class="btn">登录</el-button>
      </el-form>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import http from '../api/http'

const router = useRouter()
const loading = ref(false)
const form = reactive({ username: 'admin', password: 'admin123' })

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
.login-page { min-height: 100vh; display: flex; align-items: center; justify-content: center; background: #f5f5f5; }
.login-card { width: 400px; }
.login-card h2 { text-align: center; margin-bottom: 24px; color: #1a1a1a; }
.btn { width: 100%; background: #FFD000; border-color: #FFD000; color: #1a1a1a; }
</style>
