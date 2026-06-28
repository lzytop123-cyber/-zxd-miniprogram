<template>
  <el-card>
    <template #header>
      <div class="header-row">
        <span>消息公告</span>
        <el-button type="primary" @click="openCreate">新建公告</el-button>
      </div>
    </template>

    <el-alert
      type="info"
      :closable="false"
      show-icon
      title="启用且勾选「首页展示」的公告会在小程序首页弹窗/公告栏展示。"
      style="margin-bottom: 16px"
    />

    <el-table :data="list" v-loading="loading" stripe>
      <el-table-column prop="title" label="标题" min-width="140" />
      <el-table-column prop="content" label="内容" min-width="220" show-overflow-tooltip />
      <el-table-column label="展示" width="90">
        <template #default="{ row }">
          <el-tag :type="row.show_on_home ? 'success' : 'info'" size="small">
            {{ row.show_on_home ? '首页' : '否' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="弹窗一次" width="90">
        <template #default="{ row }">{{ row.popup_once ? '是' : '否' }}</template>
      </el-table-column>
      <el-table-column prop="priority" label="优先级" width="80" />
      <el-table-column label="状态" width="80">
        <template #default="{ row }">
          <el-tag :type="row.is_active ? 'success' : 'info'" size="small">
            {{ row.is_active ? '启用' : '停用' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="140" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
          <el-button link type="danger" @click="remove(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="showDialog" :title="editingId ? '编辑公告' : '新建公告'" width="560px">
      <el-form :model="form" label-width="100px">
        <el-form-item label="标题"><el-input v-model="form.title" maxlength="100" show-word-limit /></el-form-item>
        <el-form-item label="内容"><el-input v-model="form.content" type="textarea" :rows="4" /></el-form-item>
        <el-form-item label="跳转路径"><el-input v-model="form.link_path" placeholder="可选，小程序页面路径" /></el-form-item>
        <el-form-item label="首页展示"><el-switch v-model="form.show_on_home" :active-value="1" :inactive-value="0" /></el-form-item>
        <el-form-item label="弹窗一次"><el-switch v-model="form.popup_once" :active-value="1" :inactive-value="0" /></el-form-item>
        <el-form-item label="优先级"><el-input-number v-model="form.priority" :min="0" /></el-form-item>
        <el-form-item label="启用"><el-switch v-model="form.is_active" :active-value="1" :inactive-value="0" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showDialog = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submit">保存</el-button>
      </template>
    </el-dialog>
  </el-card>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import http from '../api/http'

const list = ref<any[]>([])
const loading = ref(false)
const showDialog = ref(false)
const saving = ref(false)
const editingId = ref<number | null>(null)
const form = reactive({
  title: '',
  content: '',
  link_path: '',
  show_on_home: 1,
  popup_once: 1,
  priority: 0,
  is_active: 1,
})

async function load() {
  loading.value = true
  try {
    const res = await http.get('/admin/announcements')
    list.value = res.data
  } finally {
    loading.value = false
  }
}

function resetForm() {
  Object.assign(form, {
    title: '',
    content: '',
    link_path: '',
    show_on_home: 1,
    popup_once: 1,
    priority: 0,
    is_active: 1,
  })
}

function openCreate() {
  editingId.value = null
  resetForm()
  showDialog.value = true
}

function openEdit(row: any) {
  editingId.value = row.id
  Object.assign(form, {
    title: row.title,
    content: row.content,
    link_path: row.link_path || '',
    show_on_home: row.show_on_home,
    popup_once: row.popup_once,
    priority: row.priority,
    is_active: row.is_active,
  })
  showDialog.value = true
}

async function submit() {
  if (!form.title.trim() || !form.content.trim()) {
    ElMessage.warning('请填写标题和内容')
    return
  }
  saving.value = true
  try {
    const payload = { ...form, link_path: form.link_path || null }
    if (editingId.value) {
      await http.patch(`/admin/announcements/${editingId.value}`, payload)
    } else {
      await http.post('/admin/announcements', payload)
    }
    ElMessage.success('已保存')
    showDialog.value = false
    load()
  } finally {
    saving.value = false
  }
}

async function remove(row: any) {
  await ElMessageBox.confirm(`确定删除公告「${row.title}」？`, '删除确认', { type: 'warning' })
  await http.delete(`/admin/announcements/${row.id}`)
  ElMessage.success('已删除')
  load()
}

onMounted(load)
</script>

<style scoped>
.header-row { display: flex; justify-content: space-between; align-items: center; }
</style>
