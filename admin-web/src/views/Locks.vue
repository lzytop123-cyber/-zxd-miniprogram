<template>
  <el-card>
    <template #header>
      <div class="header">
        <span>蓝牙门锁</span>
        <div class="header-actions">
          <el-select v-model="storeFilter" clearable placeholder="全部门店" style="width:160px" @change="load">
            <el-option v-for="s in stores" :key="s.id" :label="s.name" :value="s.id" />
          </el-select>
          <el-button type="primary" @click="openCreate">添加门锁</el-button>
        </div>
      </div>
    </template>

    <el-alert
      v-for="a in alerts"
      :key="a.id"
      :title="a.message"
      type="warning"
      show-icon
      closable
      class="alert-item"
      @close="readAlert(a.id)"
    />

    <el-table :data="list" stripe>
      <el-table-column prop="id" label="ID" width="60" />
      <el-table-column prop="lock_name" label="名称" />
      <el-table-column prop="lock_id" label="锁ID" show-overflow-tooltip />
      <el-table-column prop="mac_address" label="MAC" width="140" />
      <el-table-column prop="battery_level" label="电量" width="100">
        <template #default="{ row }">
          <el-tag :type="batteryType(row.battery_level)">
            {{ row.battery_level ?? '-' }}%
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="status" label="状态" width="80">
        <template #default="{ row }">
          <el-tag :type="row.status === 1 ? 'success' : 'danger'">
            {{ row.status === 1 ? '启用' : '停用' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="160">
        <template #default="{ row }">
          <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
          <el-button link type="primary" @click="refreshBattery(row.id)">刷新电量</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="dialogVisible" :title="editingId ? '编辑门锁' : '添加门锁'" width="480px">
      <el-form :model="form" label-width="88px">
        <el-form-item label="门店">
          <el-select v-model="form.store_id" style="width:100%">
            <el-option v-for="s in stores" :key="s.id" :label="s.name" :value="s.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="名称"><el-input v-model="form.lock_name" /></el-form-item>
        <el-form-item label="锁ID"><el-input v-model="form.lock_id" placeholder="通通锁数字 ID，勿用 mock_" /></el-form-item>
        <el-form-item label="MAC"><el-input v-model="form.mac_address" /></el-form-item>
        <el-form-item label="lockData"><el-input v-model="form.lock_data" type="textarea" :rows="4" placeholder="锁初始化 lockData" /></el-form-item>
        <el-form-item v-if="editingId" label="状态">
          <el-switch v-model="form.status" :active-value="1" :inactive-value="0" active-text="启用" inactive-text="停用" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitLock">确定</el-button>
      </template>
    </el-dialog>
  </el-card>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import http from '../api/http'

const list = ref<any[]>([])
const stores = ref<any[]>([])
const alerts = ref<any[]>([])
const dialogVisible = ref(false)
const editingId = ref<number | null>(null)
const storeFilter = ref<number | null>(null)

const form = reactive({
  store_id: 1,
  lock_name: '',
  lock_id: '',
  mac_address: '',
  lock_data: '',
  status: 1,
})

function batteryType(level: number | null) {
  if (level == null) return 'info'
  if (level < 20) return 'danger'
  if (level < 40) return 'warning'
  return 'success'
}

function resetForm() {
  form.store_id = stores.value[0]?.id || 1
  form.lock_name = ''
  form.lock_id = ''
  form.mac_address = ''
  form.lock_data = ''
  form.status = 1
}

function openCreate() {
  editingId.value = null
  resetForm()
  dialogVisible.value = true
}

function openEdit(row: any) {
  editingId.value = row.id
  form.store_id = row.store_id || stores.value[0]?.id || 1
  form.lock_name = row.lock_name || ''
  form.lock_id = row.lock_id || ''
  form.mac_address = row.mac_address || ''
  form.lock_data = ''
  form.status = row.status ?? 1
  dialogVisible.value = true
}

async function loadStores() {
  const res = await http.get('/admin/stores')
  stores.value = res.data || []
}

async function load() {
  const params = storeFilter.value ? { store_id: storeFilter.value } : {}
  const [locksRes, alertsRes] = await Promise.all([
    http.get('/admin/locks', { params }),
    http.get('/admin/locks/alerts'),
  ])
  list.value = locksRes.data
  alerts.value = alertsRes.data
}

async function readAlert(id: number) {
  await http.post(`/admin/locks/alerts/${id}/read`)
  load()
}

async function submitLock() {
  if (editingId.value) {
    const payload: Record<string, unknown> = {
      lock_name: form.lock_name,
      lock_id: form.lock_id,
      mac_address: form.mac_address || null,
      status: form.status,
    }
    if (form.lock_data.trim()) payload.lock_data = form.lock_data.trim()
    await http.put(`/admin/locks/${editingId.value}`, payload)
    ElMessage.success('已更新')
  } else {
    await http.post('/admin/locks', {
      store_id: form.store_id,
      lock_name: form.lock_name,
      lock_id: form.lock_id,
      mac_address: form.mac_address || null,
      lock_data: form.lock_data || null,
    })
    ElMessage.success('添加成功')
  }
  dialogVisible.value = false
  load()
}

async function refreshBattery(id: number) {
  const res = await http.post(`/admin/locks/${id}/refresh-battery`)
  ElMessage.success(`电量: ${res.data.battery_level}%`)
  load()
}

onMounted(async () => {
  await loadStores()
  await load()
})
</script>

<style scoped>
.header { display: flex; justify-content: space-between; align-items: center; }
.header-actions { display: flex; gap: 12px; align-items: center; }
.alert-item { margin-bottom: 12px; }
</style>
