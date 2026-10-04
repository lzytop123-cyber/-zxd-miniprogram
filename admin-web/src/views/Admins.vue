<template>
  <el-card>
    <template #header>
      <div class="header-row">
        <span>管理员账号</span>
        <el-button type="primary" @click="openAdd">新增管理员</el-button>
      </div>
    </template>

    <el-table :data="list" v-loading="loading" stripe>
      <el-table-column prop="id" label="ID" width="60" />
      <el-table-column prop="username" label="用户名" width="140" />
      <el-table-column prop="name" label="姓名" width="120" />
      <el-table-column label="角色" width="100">
        <template #default="{ row }">
          <el-tag :type="row.role === 'store' ? 'warning' : 'success'" size="small">
            {{ row.role === 'store' ? '店长' : '总部' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="门店" min-width="140">
        <template #default="{ row }">
          {{ row.role === 'store' ? (row.store_name || `#${row.store_id}`) : '—' }}
        </template>
      </el-table-column>
      <el-table-column label="权限" width="110">
        <template #default="{ row }">
          {{ permLabel(row) }}
        </template>
      </el-table-column>
      <el-table-column prop="status" label="状态" width="80">
        <template #default="{ row }">
          <el-tag :type="row.status === 1 ? 'success' : 'info'" size="small">
            {{ row.status === 1 ? '正常' : '停用' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="created_at" label="创建时间" width="170" />
      <el-table-column label="操作" width="90" fixed="right">
        <template #default="{ row }">
          <el-button
            v-if="canEditRow(row)"
            type="primary"
            link
            @click="openEdit(row)"
          >编辑</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="showDialog" :title="editingId ? '编辑管理员' : '新增管理员'" width="640px">
      <el-form :model="form" label-width="90px">
        <el-form-item label="用户名">
          <el-input v-model="form.username" :disabled="!!editingId" />
        </el-form-item>
        <el-form-item :label="editingId ? '新密码' : '密码'">
          <el-input v-model="form.password" type="password" show-password :placeholder="editingId ? '留空则不修改' : ''" />
        </el-form-item>
        <el-form-item label="姓名"><el-input v-model="form.name" /></el-form-item>
        <el-form-item label="角色">
          <el-radio-group v-model="form.role" :disabled="isStoreActor" @change="onRoleChange">
            <el-radio v-if="!isStoreActor" value="hq">总部</el-radio>
            <el-radio value="store">店长</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item v-if="form.role === 'store' && !isStoreActor" label="绑定门店">
          <el-select v-model="form.store_id" style="width:100%" placeholder="选择门店">
            <el-option v-for="s in stores" :key="s.id" :label="s.name" :value="s.id" />
          </el-select>
        </el-form-item>
        <template v-if="form.role === 'store'">
          <el-form-item label="本店模块">
            <el-checkbox-group v-model="form.permissions" class="perm-grid">
              <el-checkbox v-for="key in STORE_DEFAULT_PERMISSIONS" :key="key" :value="key">
                {{ MODULE_LABELS[key] || key }}
              </el-checkbox>
            </el-checkbox-group>
          </el-form-item>
          <el-form-item label="扩展模块">
            <el-checkbox-group v-model="form.permissions" class="perm-grid">
              <el-checkbox v-for="key in EXTENDED_PERMISSIONS" :key="key" :value="key">
                {{ MODULE_LABELS[key] || key }}
                <span v-if="isGlobalConfig(key)" class="global-hint">全站配置</span>
              </el-checkbox>
            </el-checkbox-group>
          </el-form-item>
          <el-form-item>
            <el-button @click="restoreStandard">恢复标准店长</el-button>
          </el-form-item>
        </template>
      </el-form>
      <template #footer>
        <el-button @click="showDialog = false">取消</el-button>
        <el-button type="primary" @click="submit">{{ editingId ? '保存' : '创建' }}</el-button>
      </template>
    </el-dialog>
  </el-card>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import http from '../api/http'
import { getAdminRole, getAdminStoreId } from '../utils/adminAuth'
import {
  EXTENDED_PERMISSIONS,
  GLOBAL_CONFIG_MODULES,
  MODULE_LABELS,
  STORE_DEFAULT_PERMISSIONS,
} from '../utils/adminModules'

const GLOBAL_SET = new Set<string>(GLOBAL_CONFIG_MODULES)
const DEFAULT_SET = new Set<string>(STORE_DEFAULT_PERMISSIONS)

const isStoreActor = getAdminRole() === 'store'
const list = ref<any[]>([])
const stores = ref<any[]>([])
const loading = ref(false)
const showDialog = ref(false)
const editingId = ref<number | null>(null)
const form = reactive({
  username: '',
  password: '',
  name: '',
  role: 'hq' as 'hq' | 'store',
  store_id: null as number | null,
  permissions: [] as string[],
})

function isGlobalConfig(key: string) {
  return GLOBAL_SET.has(key)
}

function restoreStandard() {
  form.permissions = [...STORE_DEFAULT_PERMISSIONS]
}

function onRoleChange() {
  if (form.role === 'store') restoreStandard()
}

function permLabel(row: any) {
  if (row.role !== 'store') return '—'
  const keys: string[] = Array.isArray(row.permissions) ? row.permissions.map(String) : [...STORE_DEFAULT_PERMISSIONS]
  if (!keys.length) return '自定义(0)'
  const keySet = new Set(keys)
  if (keySet.size === DEFAULT_SET.size && [...DEFAULT_SET].every((k) => keySet.has(k))) return '标准'
  if ([...DEFAULT_SET].every((k) => keySet.has(k))) return `标准+${keySet.size - DEFAULT_SET.size}`
  return `自定义(${keys.length})`
}

function canEditRow(row: any) {
  if (isStoreActor && row.role !== 'store') return false
  return true
}

function resetForm() {
  form.username = ''
  form.password = ''
  form.name = ''
  form.role = isStoreActor ? 'store' : 'hq'
  form.store_id = isStoreActor ? getAdminStoreId() : null
  form.permissions = isStoreActor ? [...STORE_DEFAULT_PERMISSIONS] : []
}

async function load() {
  loading.value = true
  try {
    const [adminsRes, storesRes] = await Promise.all([
      http.get('/admin/admins'),
      http.get('/admin/stores'),
    ])
    list.value = adminsRes.data
    stores.value = storesRes.data || []
  } finally {
    loading.value = false
  }
}

function openAdd() {
  editingId.value = null
  resetForm()
  showDialog.value = true
}

function openEdit(row: any) {
  editingId.value = row.id
  form.username = row.username
  form.password = ''
  form.name = row.name || ''
  form.role = row.role === 'store' ? 'store' : 'hq'
  form.store_id = row.store_id ?? (isStoreActor ? getAdminStoreId() : null)
  form.permissions = form.role === 'store'
    ? (Array.isArray(row.permissions) ? [...row.permissions] : [...STORE_DEFAULT_PERMISSIONS])
    : []
  showDialog.value = true
}

async function submit() {
  if (!editingId.value && (!form.username || !form.password)) {
    ElMessage.warning('请填写用户名和密码')
    return
  }
  if (form.role === 'store' && !isStoreActor && !form.store_id) {
    ElMessage.warning('店长必须绑定门店')
    return
  }
  const storeId = isStoreActor ? getAdminStoreId() : (form.role === 'store' ? form.store_id : null)
  if (editingId.value) {
    const body: Record<string, unknown> = { name: form.name }
    if (form.password) body.password = form.password
    if (!isStoreActor) {
      body.role = form.role
      body.store_id = storeId
    }
    if (form.role === 'store') body.permissions = form.permissions
    await http.patch(`/admin/admins/${editingId.value}`, body)
    ElMessage.success('已保存')
  } else {
    const body: Record<string, unknown> = {
      username: form.username,
      password: form.password,
      name: form.name,
      role: isStoreActor ? 'store' : form.role,
      store_id: storeId,
    }
    if ((isStoreActor ? 'store' : form.role) === 'store') {
      body.permissions = form.permissions
    }
    await http.post('/admin/admins', body)
    ElMessage.success('已创建')
  }
  showDialog.value = false
  load()
}

onMounted(load)
</script>

<style scoped>
.header-row { display: flex; justify-content: space-between; align-items: center; }
.perm-grid { display: flex; flex-wrap: wrap; gap: 4px 8px; }
.global-hint { color: #909399; font-size: 12px; margin-left: 4px; }
</style>
