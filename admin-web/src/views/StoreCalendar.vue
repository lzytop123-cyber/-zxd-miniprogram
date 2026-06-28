<template>
  <el-card>
    <template #header>
      <div class="header-row">
        <div class="left">
          <span>营业日历</span>
          <el-select v-model="storeId" style="width: 200px; margin-left: 12px" @change="load">
            <el-option v-for="s in stores" :key="s.id" :label="s.name" :value="s.id" />
          </el-select>
        </div>
        <el-button type="primary" @click="openAdd">添加特殊日</el-button>
      </div>
    </template>

    <el-alert
      type="info"
      :closable="false"
      show-icon
      title="用于标记闭店日或特殊营业时间，后续预约校验可接入此配置。"
      style="margin-bottom: 16px"
    />

    <el-table :data="list" v-loading="loading" stripe>
      <el-table-column prop="day" label="日期" width="120" />
      <el-table-column label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="row.is_closed ? 'danger' : 'success'" size="small">
            {{ row.is_closed ? '闭店' : '特殊营业' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="营业时间" width="140">
        <template #default="{ row }">
          <span v-if="row.is_closed">-</span>
          <span v-else>{{ row.open_time || '-' }} - {{ row.close_time || '-' }}</span>
        </template>
      </el-table-column>
      <el-table-column prop="remark" label="备注" min-width="160" />
      <el-table-column label="操作" width="120" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
          <el-button link type="danger" @click="remove(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="showDialog" :title="form.day ? '编辑特殊日' : '添加特殊日'" width="480px">
      <el-form :model="form" label-width="100px">
        <el-form-item label="日期">
          <el-date-picker v-model="form.day" type="date" value-format="YYYY-MM-DD" style="width:100%" />
        </el-form-item>
        <el-form-item label="闭店">
          <el-switch v-model="form.is_closed" :active-value="1" :inactive-value="0" />
        </el-form-item>
        <el-form-item v-if="!form.is_closed" label="开门"><el-input v-model="form.open_time" placeholder="09:00" /></el-form-item>
        <el-form-item v-if="!form.is_closed" label="关门"><el-input v-model="form.close_time" placeholder="22:00" /></el-form-item>
        <el-form-item label="备注"><el-input v-model="form.remark" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showDialog = false">取消</el-button>
        <el-button type="primary" @click="submit">保存</el-button>
      </template>
    </el-dialog>
  </el-card>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import http from '../api/http'

const stores = ref<any[]>([])
const storeId = ref<number | null>(null)
const list = ref<any[]>([])
const loading = ref(false)
const showDialog = ref(false)
const form = reactive({
  day: '',
  is_closed: 0,
  open_time: '',
  close_time: '',
  remark: '',
})

async function load() {
  if (!storeId.value) return
  loading.value = true
  try {
    const res = await http.get(`/admin/stores/${storeId.value}/calendar`)
    list.value = res.data
  } finally {
    loading.value = false
  }
}

function openAdd() {
  Object.assign(form, { day: '', is_closed: 0, open_time: '', close_time: '', remark: '' })
  showDialog.value = true
}

function openEdit(row: any) {
  Object.assign(form, {
    day: row.day,
    is_closed: row.is_closed,
    open_time: row.open_time || '',
    close_time: row.close_time || '',
    remark: row.remark || '',
  })
  showDialog.value = true
}

async function submit() {
  if (!storeId.value || !form.day) {
    ElMessage.warning('请选择日期')
    return
  }
  await http.put(`/admin/stores/${storeId.value}/calendar/${form.day}`, {
    day: form.day,
    is_closed: form.is_closed,
    open_time: form.open_time || null,
    close_time: form.close_time || null,
    remark: form.remark || null,
  })
  ElMessage.success('已保存')
  showDialog.value = false
  load()
}

async function remove(row: any) {
  await ElMessageBox.confirm(`确定删除 ${row.day} 的日历记录？`, '删除确认', { type: 'warning' })
  await http.delete(`/admin/stores/${storeId.value}/calendar/${row.day}`)
  ElMessage.success('已删除')
  load()
}

onMounted(async () => {
  const res = await http.get('/admin/stores')
  stores.value = res.data
  if (stores.value.length) {
    storeId.value = stores.value[0].id
    await load()
  }
})
</script>

<style scoped>
.header-row { display: flex; justify-content: space-between; align-items: center; }
.left { display: flex; align-items: center; }
</style>
