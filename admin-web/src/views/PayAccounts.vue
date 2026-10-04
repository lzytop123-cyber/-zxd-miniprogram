<template>
  <el-card>
    <template #header>
      <div class="header-row">
        <span>收款账户</span>
        <el-button v-if="isHq" type="primary" @click="openCreate">新增账户</el-button>
      </div>
    </template>

    <p class="page-hint">
      每个账户对应一套微信支付商户（结算到指定对公）。在「门店管理」里把新店绑到新账户。密钥不会在列表中回显。
    </p>

    <el-table :data="list" v-loading="loading" stripe>
      <el-table-column prop="id" label="ID" width="60" />
      <el-table-column prop="name" label="名称" min-width="140" />
      <el-table-column prop="mchid" label="商户号" width="140" />
      <el-table-column prop="serial_no" label="证书序列号" min-width="160" show-overflow-tooltip />
      <el-table-column prop="key_path" label="私钥路径" min-width="160" show-overflow-tooltip />
      <el-table-column label="APIv3" width="80">
        <template #default="{ row }">
          <el-tag :type="row.has_api_v3_key ? 'success' : 'danger'" size="small">
            {{ row.has_api_v3_key ? '已配置' : '缺' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="status" label="状态" width="80">
        <template #default="{ row }">
          <el-tag :type="row.status === 1 ? 'success' : 'info'" size="small">
            {{ row.status === 1 ? '启用' : '停用' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="100" fixed="right">
        <template #default="{ row }">
          <el-button v-if="isHq" link type="primary" @click="openEdit(row)">编辑</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="showDialog" :title="editingId ? '编辑收款账户' : '新增收款账户'" width="560px">
      <el-form :model="form" label-width="120px">
        <el-form-item label="名称"><el-input v-model="form.name" placeholder="如：新店对公B" /></el-form-item>
        <el-form-item label="商户号"><el-input v-model="form.mchid" /></el-form-item>
        <el-form-item label="证书序列号"><el-input v-model="form.serial_no" /></el-form-item>
        <el-form-item label="APIv3 密钥">
          <el-input
            v-model="form.api_v3_key"
            type="password"
            show-password
            :placeholder="editingId ? '留空表示不修改' : '必填'"
          />
        </el-form-item>
        <el-form-item label="私钥路径">
          <el-input v-model="form.key_path" placeholder="如 ./certs/store2/apiclient_key.pem" />
        </el-form-item>
        <el-form-item label="证书路径">
          <el-input v-model="form.cert_path" placeholder="可选" />
        </el-form-item>
        <el-form-item label="公钥 ID">
          <el-input v-model="form.public_key_id" placeholder="公钥模式时填写" />
        </el-form-item>
        <el-form-item label="公钥路径">
          <el-input v-model="form.public_key_path" placeholder="可选" />
        </el-form-item>
        <el-form-item v-if="editingId" label="启用">
          <el-switch v-model="form.status" :active-value="1" :inactive-value="0" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showDialog = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submit">保存</el-button>
      </template>
    </el-dialog>
  </el-card>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import http from '../api/http'
import { isHqAdmin } from '../utils/adminAuth'

const isHq = computed(() => isHqAdmin())

const list = ref<any[]>([])
const loading = ref(false)
const saving = ref(false)
const showDialog = ref(false)
const editingId = ref<number | null>(null)
const form = reactive<any>({})

function emptyForm() {
  return {
    name: '',
    mchid: '',
    serial_no: '',
    api_v3_key: '',
    key_path: '',
    cert_path: '',
    public_key_id: '',
    public_key_path: '',
    status: 1,
  }
}

async function load() {
  loading.value = true
  try {
    const res = await http.get('/admin/pay-accounts')
    list.value = res.data || []
  } finally {
    loading.value = false
  }
}

function openCreate() {
  editingId.value = null
  Object.assign(form, emptyForm())
  showDialog.value = true
}

function openEdit(row: any) {
  editingId.value = row.id
  Object.assign(form, {
    name: row.name,
    mchid: row.mchid,
    serial_no: row.serial_no,
    api_v3_key: '',
    key_path: row.key_path || '',
    cert_path: row.cert_path || '',
    public_key_id: row.public_key_id || '',
    public_key_path: row.public_key_path || '',
    status: row.status,
  })
  showDialog.value = true
}

async function submit() {
  if (!form.name?.trim() || !form.mchid?.trim()) {
    ElMessage.warning('请填写名称和商户号')
    return
  }
  if (!editingId.value && !form.api_v3_key?.trim()) {
    ElMessage.warning('请填写 APIv3 密钥')
    return
  }
  if (!form.key_path?.trim() || !form.serial_no?.trim()) {
    ElMessage.warning('请填写证书序列号和私钥路径')
    return
  }
  saving.value = true
  try {
    const payload: any = {
      name: form.name,
      mchid: form.mchid,
      serial_no: form.serial_no,
      key_path: form.key_path,
      cert_path: form.cert_path || null,
      public_key_id: form.public_key_id || null,
      public_key_path: form.public_key_path || null,
      status: form.status,
    }
    if (form.api_v3_key?.trim()) payload.api_v3_key = form.api_v3_key.trim()
    if (editingId.value) {
      await http.put(`/admin/pay-accounts/${editingId.value}`, payload)
    } else {
      payload.api_v3_key = form.api_v3_key.trim()
      await http.post('/admin/pay-accounts', payload)
    }
    ElMessage.success('已保存')
    showDialog.value = false
    load()
  } finally {
    saving.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.header-row { display: flex; justify-content: space-between; align-items: center; }
.page-hint { margin: 0 0 16px; color: #666; font-size: 13px; line-height: 1.6; }
</style>
