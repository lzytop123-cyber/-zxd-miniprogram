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

    <p class="page-hint">
      可配置封面图、地址、营业时间、WiFi 等。封面展示在小程序首页门店卡片与门店详情页轮播。
    </p>

    <el-table :data="list" v-loading="loading" stripe>
      <el-table-column prop="id" label="ID" width="60" />
      <el-table-column label="封面" width="88">
        <template #default="{ row }">
          <el-image v-if="row.cover_images?.length" :src="row.cover_images[0]" fit="cover" class="thumb" />
          <span v-else class="muted">未设置</span>
        </template>
      </el-table-column>
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

    <el-dialog v-model="showCreate" title="新增门店" width="620px">
      <StoreFormFields
        :form="createForm"
        :uploading="uploading"
        @upload="(opt, f) => uploadCover(opt, f)"
        @remove="removeCover"
      />
      <template #footer>
        <el-button @click="showCreate = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="createStore">创建</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="showEdit" :title="`编辑门店 · ${form.name}`" width="620px">
      <StoreFormFields
        :form="form"
        :uploading="uploading"
        show-status
        @upload="(opt, f) => uploadCover(opt, f)"
        @remove="removeCover"
      />
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
import type { UploadRequestOptions } from 'element-plus'
import http from '../api/http'
import StoreFormFields from '../components/StoreFormFields.vue'

const list = ref<any[]>([])
const loading = ref(false)
const saving = ref(false)
const uploading = ref(false)
const showEdit = ref(false)
const showCreate = ref(false)
const form = reactive<any>({})
const createForm = reactive<any>(emptyForm())

function emptyForm() {
  return {
    name: '',
    address: '',
    latitude: null,
    longitude: null,
    open_time: '08:00',
    close_time: '23:00',
    wifi_name: '',
    wifi_password: '',
    meituan_shop_id: '',
    cover_images: [] as string[],
    status: 1,
  }
}

async function uploadCover(options: UploadRequestOptions, target: any) {
  uploading.value = true
  try {
    const fd = new FormData()
    fd.append('file', options.file as File)
    const res = await http.post('/admin/stores/upload-cover', fd, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    if (!target.cover_images) target.cover_images = []
    target.cover_images.push(res.data.url)
    ElMessage.success('图片已上传')
  } finally {
    uploading.value = false
  }
}

function removeCover(target: any, index: number) {
  target.cover_images.splice(index, 1)
}

function buildPayload(data: any) {
  return {
    name: data.name,
    address: data.address,
    latitude: data.latitude,
    longitude: data.longitude,
    open_time: data.open_time,
    close_time: data.close_time,
    wifi_name: data.wifi_name,
    wifi_password: data.wifi_password,
    meituan_shop_id: data.meituan_shop_id || null,
    cover_images: data.cover_images || [],
    ...(data.status !== undefined ? { status: data.status } : {}),
  }
}

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
  Object.assign(createForm, emptyForm())
  showCreate.value = true
}

async function createStore() {
  if (!createForm.name?.trim()) {
    ElMessage.warning('请填写门店名称')
    return
  }
  saving.value = true
  try {
    await http.post('/admin/stores', buildPayload(createForm))
    ElMessage.success('门店已创建')
    showCreate.value = false
    load()
  } finally {
    saving.value = false
  }
}

function openEdit(row: any) {
  Object.assign(form, {
    ...row,
    cover_images: [...(row.cover_images || [])],
    meituan_shop_id: row.meituan_shop_id || '',
  })
  showEdit.value = true
}

async function save() {
  saving.value = true
  try {
    await http.put(`/admin/stores/${form.id}`, buildPayload(form))
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
.page-hint { margin: 0 0 16px; color: #666; font-size: 13px; line-height: 1.6; }
.thumb { width: 56px; height: 40px; border-radius: 6px; }
.muted { color: #999; font-size: 12px; }
</style>
