<template>
  <el-card>
    <template #header>
      <div class="header-row">
        <span>站内消息</span>
        <el-button type="primary" @click="openCreate">发新消息</el-button>
      </div>
    </template>

    <el-alert
      type="info"
      :closable="false"
      show-icon
      title="站内消息在小程序「我的 → 消息」查看。可发全体广播、单个用户或指定门店。"
      style="margin-bottom: 16px"
    />

    <el-table :data="list" v-loading="loading" stripe>
      <el-table-column prop="id" label="ID" width="70" />
      <el-table-column prop="title" label="标题" min-width="140" />
      <el-table-column prop="content" label="内容" min-width="220" show-overflow-tooltip />
      <el-table-column label="类别" width="90">
        <template #default="{ row }">
          <el-tag :type="catType(row.category)" size="small">{{ catLabel(row.category) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="接收方" min-width="140">
        <template #default="{ row }">
          <span v-if="row.target_type === 'all'">全体用户</span>
          <span v-else-if="row.target_type === 'user'">用户 #{{ row.target_user_id }}</span>
          <span v-else-if="row.target_type === 'store'">门店 #{{ row.store_id }}</span>
        </template>
      </el-table-column>
      <el-table-column prop="read_count" label="已读数" width="80" />
      <el-table-column prop="created_at" label="发送时间" width="150" />
    </el-table>

    <el-pagination
      style="margin-top: 12px; justify-content: flex-end; display: flex"
      layout="prev, pager, next, total"
      :page-size="size"
      :total="total"
      :current-page="page"
      @current-change="onPageChange"
    />

    <el-dialog v-model="showDialog" title="发送站内消息" width="560px">
      <el-form :model="form" label-width="90px">
        <el-form-item label="接收方">
          <el-radio-group v-model="form.target_type">
            <el-radio value="all">全体用户</el-radio>
            <el-radio value="user">指定用户</el-radio>
            <el-radio value="store">指定门店</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item v-if="form.target_type === 'user'" label="用户 ID">
          <el-input-number v-model="form.target_user_id" :min="1" style="width: 200px" />
          <span class="hint">在「用户管理」页可查到 ID</span>
        </el-form-item>
        <el-form-item v-if="form.target_type === 'store'" label="门店">
          <el-select v-model="form.store_id" style="width: 240px" placeholder="选择门店">
            <el-option v-for="s in stores" :key="s.id" :label="s.name" :value="s.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="类别">
          <el-select v-model="form.category" style="width: 200px">
            <el-option label="系统通知" value="system" />
            <el-option label="到期/提醒" value="reminder" />
            <el-option label="活动/营销" value="promo" />
          </el-select>
        </el-form-item>
        <el-form-item label="标题">
          <el-input v-model="form.title" maxlength="100" show-word-limit placeholder="例如：您的月卡将在 3 天后到期" />
        </el-form-item>
        <el-form-item label="正文">
          <el-input v-model="form.content" type="textarea" :rows="5" maxlength="2000" show-word-limit />
        </el-form-item>
        <el-form-item label="跳转路径">
          <el-input v-model="form.link_path" placeholder="选填，如 pages/packages/index" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showDialog = false">取消</el-button>
        <el-button type="primary" :loading="sending" @click="submit">发送</el-button>
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
const loading = ref(false)
const sending = ref(false)
const showDialog = ref(false)
const page = ref(1)
const size = ref(20)
const total = ref(0)

const form = reactive({
  target_type: 'all' as 'all' | 'user' | 'store',
  target_user_id: undefined as number | undefined,
  store_id: undefined as number | undefined,
  category: 'system' as 'system' | 'reminder' | 'promo',
  title: '',
  content: '',
  link_path: '',
})

function catLabel(c: string) {
  return { system: '系统', reminder: '提醒', promo: '活动' }[c] || c
}
function catType(c: string): any {
  return { system: 'info', reminder: 'warning', promo: 'success' }[c] || 'info'
}

async function load() {
  loading.value = true
  try {
    const res = await http.get('/admin/notifications', { params: { page: page.value, size: size.value } })
    list.value = res.data.items
    total.value = res.data.total
  } finally {
    loading.value = false
  }
}

function openCreate() {
  Object.assign(form, {
    target_type: 'all',
    target_user_id: undefined,
    store_id: undefined,
    category: 'system',
    title: '',
    content: '',
    link_path: '',
  })
  showDialog.value = true
}

async function submit() {
  if (!form.title.trim() || !form.content.trim()) {
    ElMessage.warning('标题和正文必填')
    return
  }
  sending.value = true
  try {
    await http.post('/admin/notifications', form)
    ElMessage.success('已发送')
    showDialog.value = false
    page.value = 1
    load()
  } finally {
    sending.value = false
  }
}

function onPageChange(p: number) {
  page.value = p
  load()
}

onMounted(async () => {
  const res = await http.get('/admin/stores')
  stores.value = res.data
  load()
})
</script>

<style scoped>
.header-row { display: flex; justify-content: space-between; align-items: center; }
.hint { margin-left: 12px; color: #999; font-size: 12px; }
</style>
