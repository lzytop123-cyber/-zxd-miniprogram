<template>
  <el-card>
    <template #header>
      <div class="header-row">
        <span>门店管理</span>
        <div class="actions">
          <el-tag type="info">修改后小程序即时生效</el-tag>
          <el-button type="primary" @click="openCreate">新增门店</el-button>
        </div>
      </div>
    </template>

    <el-table :data="list" v-loading="loading" stripe>
      <el-table-column prop="id" label="ID" width="60" />
      <el-table-column prop="name" label="门店名称" min-width="140" />
      <el-table-column prop="address" label="地址" min-width="200" show-overflow-tooltip />
      <el-table-column label="营业时间" width="140">
        <template #default="{ row }">
          {{ row.open_time || '--' }} - {{ row.close_time || '--' }}
        </template>
      </el-table-column>
      <el-table-column prop="wifi_name" label="WiFi" width="120" show-overflow-tooltip />
      <el-table-column prop="status" label="状态" width="80">
        <template #default="{ row }">
          <el-tag :type="row.status === 1 ? 'success' : 'info'">
            {{ row.status === 1 ? '营业' : '停用' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="100" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="showCreate" title="新增门店" width="560px">
      <el-form :model="createForm" label-width="100px">
        <el-form-item label="门店名称"><el-input v-model="createForm.name" /></el-form-item>
        <el-form-item label="地址"><el-input v-model="createForm.address" type="textarea" :rows="2" /></el-form-item>
        <el-form-item label="纬度"><el-input-number v-model="createForm.latitude" :precision="6" style="width:100%" /></el-form-item>
        <el-form-item label="经度"><el-input-number v-model="createForm.longitude" :precision="6" style="width:100%" /></el-form-item>
        <el-form-item label="开门时间"><el-input v-model="createForm.open_time" placeholder="08:00" /></el-form-item>
        <el-form-item label="关门时间"><el-input v-model="createForm.close_time" placeholder="23:00" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreate = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="createStore">创建</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="showEdit" :title="`编辑门店 · ${form.name}`" width="560px">
      <el-form :model="form" label-width="100px">
        <el-form-item label="门店名称"><el-input v-model="form.name" /></el-form-item>
        <el-form-item label="地址"><el-input v-model="form.address" type="textarea" :rows="2" /></el-form-item>
        <el-form-item label="纬度"><el-input-number v-model="form.latitude" :precision="6" :step="0.000001" style="width:100%" /></el-form-item>
        <el-form-item label="经度"><el-input-number v-model="form.longitude" :precision="6" :step="0.000001" style="width:100%" /></el-form-item>
        <el-form-item label="开门时间"><el-input v-model="form.open_time" placeholder="08:00" /></el-form-item>
        <el-form-item label="关门时间"><el-input v-model="form.close_time" placeholder="23:00" /></el-form-item>
        <el-form-item label="WiFi 名称"><el-input v-model="form.wifi_name" /></el-form-item>
        <el-form-item label="WiFi 密码"><el-input v-model="form.wifi_password" /></el-form-item>
        <el-form-item label="状态">
          <el-switch v-model="form.status" :active-value="1" :inactive-value="0" active-text="营业" inactive-text="停用" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showEdit = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="save">保存</el-button>
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
const saving = ref(false)
const showEdit = ref(false)
const showCreate = ref(false)
const form = reactive<any>({})
const createForm = reactive<any>({
  name: '',
  address: '',
  latitude: null,
  longitude: null,
  open_time: '08:00',
  close_time: '23:00',
})

async function load() {
  loading.value = true
  try {
    const res = await http.get('/admin/stores')
    list.value = res.data
  } finally {
    loading.value = false
  }
}

function openCreate() {
  Object.assign(createForm, {
    name: '',
    address: '',
    latitude: null,
    longitude: null,
    open_time: '08:00',
    close_time: '23:00',
  })
  showCreate.value = true
}

async function createStore() {
  if (!createForm.name?.trim()) {
    ElMessage.warning('请填写门店名称')
    return
  }
  saving.value = true
  try {
    await http.post('/admin/stores', createForm)
    ElMessage.success('门店已创建')
    showCreate.value = false
    load()
  } finally {
    saving.value = false
  }
}

function openEdit(row: any) {
  Object.assign(form, { ...row })
  showEdit.value = true
}

async function save() {
  saving.value = true
  try {
    await http.put(`/admin/stores/${form.id}`, {
      name: form.name,
      address: form.address,
      latitude: form.latitude,
      longitude: form.longitude,
      open_time: form.open_time,
      close_time: form.close_time,
      wifi_name: form.wifi_name,
      wifi_password: form.wifi_password,
      status: form.status,
    })
    ElMessage.success('已保存')
    showEdit.value = false
    load()
  } finally {
    saving.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.header-row { display: flex; justify-content: space-between; align-items: center; gap: 12px; }
.actions { display: flex; align-items: center; gap: 12px; }
</style>
