<template>
  <el-card>
    <template #header>
      <div class="header-row">
        <span>管理员账号</span>
        <el-button type="primary" @click="showAdd = true">新增管理员</el-button>
      </div>
    </template>

    <el-table :data="list" v-loading="loading" stripe>
      <el-table-column prop="id" label="ID" width="60" />
      <el-table-column prop="username" label="用户名" width="140" />
      <el-table-column prop="name" label="姓名" width="120" />
      <el-table-column prop="status" label="状态" width="80">
        <template #default="{ row }">
          <el-tag :type="row.status === 1 ? 'success' : 'info'" size="small">
            {{ row.status === 1 ? '正常' : '停用' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="created_at" label="创建时间" width="170" />
    </el-table>

    <el-dialog v-model="showAdd" title="新增管理员" width="420px">
      <el-form :model="form" label-width="80px">
        <el-form-item label="用户名"><el-input v-model="form.username" /></el-form-item>
        <el-form-item label="密码"><el-input v-model="form.password" type="password" show-password /></el-form-item>
        <el-form-item label="姓名"><el-input v-model="form.name" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showAdd = false">取消</el-button>
        <el-button type="primary" @click="submit">创建</el-button>
      </template>
    </el-dialog>
  </el-card>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import http from '../api/http'

const list = ref<any[]>([])
const loading = ref(false)
const showAdd = ref(false)
const form = reactive({ username: '', password: '', name: '' })

async function load() {
  loading.value = true
  try {
    const res = await http.get('/admin/admins')
    list.value = res.data
  } finally {
    loading.value = false
  }
}

async function submit() {
  await http.post('/admin/admins', form)
  ElMessage.success('已创建')
  showAdd.value = false
  form.username = ''
  form.password = ''
  form.name = ''
  load()
}

onMounted(load)
</script>

<style scoped>
.header-row { display: flex; justify-content: space-between; align-items: center; }
</style>
