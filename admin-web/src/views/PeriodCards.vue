<template>
  <el-card>
    <template #header>
      <div class="header-row">
        <span>期限卡</span>
        <div class="right">
          <el-input-number v-model="userId" :min="1" placeholder="用户ID" controls-position="right" style="width:120px" />
          <el-select v-model="status" clearable placeholder="状态" style="width:100px; margin-left:8px">
            <el-option label="有效" :value="1" />
            <el-option label="失效" :value="0" />
          </el-select>
          <el-button type="primary" style="margin-left:8px" @click="search">查询</el-button>
          <el-button type="success" style="margin-left:8px" @click="openIssue">手动发放</el-button>
        </div>
      </div>
    </template>

    <el-table :data="list" v-loading="loading" stripe>
      <el-table-column prop="id" label="ID" width="60" />
      <el-table-column label="用户" width="120">
        <template #default="{ row }">
          <div>{{ row.user_nickname || '-' }}</div>
          <div class="sub">ID {{ row.user_id }}</div>
        </template>
      </el-table-column>
      <el-table-column prop="card_name" label="卡名称" min-width="140" />
      <el-table-column label="类型" width="100">
        <template #default="{ row }">{{ cardTypeLabel(row.card_type) }}</template>
      </el-table-column>
      <el-table-column label="余量" width="140">
        <template #default="{ row }">
          <span v-if="row.remaining_hours != null">{{ row.remaining_hours }}小时</span>
          <span v-if="row.total_hours != null" class="sub"> / 共{{ row.total_hours }}h</span>
          <span v-else-if="row.remaining_sessions != null">{{ row.remaining_sessions }}次</span>
          <span v-else>-</span>
        </template>
      </el-table-column>
      <el-table-column label="有效期" width="200">
        <template #default="{ row }">
          {{ row.start_date || '-' }} ~ {{ row.end_date || '-' }}
        </template>
      </el-table-column>
      <el-table-column label="来源" width="90">
        <template #default="{ row }">{{ sourceLabel(row.source) }}</template>
      </el-table-column>
      <el-table-column prop="status" label="状态" width="80">
        <template #default="{ row }">
          <el-tag :type="row.status === 1 ? 'success' : 'info'" size="small">
            {{ row.status === 1 ? '有效' : '失效' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="created_at" label="发放时间" width="170" />
      <el-table-column label="操作" width="160" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="openEdit(row)">运维</el-button>
          <el-button v-if="row.status === 1" link type="danger" @click="revoke(row)">作废</el-button>
        </template>
      </el-table-column>
    </el-table>

    <div class="pager">
      <el-pagination v-model:current-page="page" :total="total" layout="total, prev, pager, next" @current-change="load" />
    </div>

    <el-dialog v-model="issueVisible" title="手动发放期限卡" width="520px">
      <el-form :model="issueForm" label-width="100px">
        <el-form-item label="用户ID"><el-input-number v-model="issueForm.user_id" :min="1" style="width:100%" /></el-form-item>
        <el-form-item label="门店ID"><el-input-number v-model="issueForm.store_id" :min="1" style="width:100%" /></el-form-item>
        <el-form-item label="卡类型">
          <el-select v-model="issueForm.card_type" style="width:100%">
            <el-option v-for="t in cardTypes" :key="t.value" :label="t.label" :value="t.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="数值">
          <el-input-number v-model="issueForm.reward_value" :min="1" style="width:100%" />
          <div class="hint">小时卡=小时数；次卡=次数；天/周/月/季=有效天数</div>
        </el-form-item>
        <el-form-item label="卡名称"><el-input v-model="issueForm.card_name" placeholder="可选" /></el-form-item>
        <el-form-item label="备注"><el-input v-model="issueForm.remark" placeholder="可选" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="issueVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitIssue">发放</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="editVisible" title="期限卡运维" width="520px">
      <el-form :model="editForm" label-width="110px">
        <el-form-item label="卡名称"><el-input :model-value="editRow?.card_name" disabled /></el-form-item>
        <el-form-item label="延长天数"><el-input-number v-model="editForm.extend_days" :min="0" style="width:100%" /></el-form-item>
        <el-form-item v-if="editRow?.card_type === 'hourly'" label="剩余小时">
          <el-input-number v-model="editForm.remaining_hours" :min="0" :step="0.5" :precision="1" style="width:100%" />
        </el-form-item>
        <el-form-item v-if="editRow?.card_type === 'hourly'" label="总小时">
          <el-input-number v-model="editForm.total_hours" :min="0" :step="0.5" :precision="1" style="width:100%" />
        </el-form-item>
        <el-form-item v-if="editRow?.card_type === 'session'" label="剩余次数">
          <el-input-number v-model="editForm.remaining_sessions" :min="0" style="width:100%" />
        </el-form-item>
        <el-form-item label="备注"><el-input v-model="editForm.remark" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitEdit">保存</el-button>
      </template>
    </el-dialog>
  </el-card>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import http from '../api/http'

const list = ref<any[]>([])
const loading = ref(false)
const submitting = ref(false)
const page = ref(1)
const total = ref(0)
const userId = ref<number | null>(null)
const status = ref<number | null>(null)

const issueVisible = ref(false)
const editVisible = ref(false)
const editRow = ref<any>(null)
const issueForm = reactive({
  user_id: null as number | null,
  store_id: null as number | null,
  card_type: 'hourly',
  reward_value: 4,
  card_name: '',
  remark: '',
})
const editForm = reactive({
  extend_days: 0,
  remaining_hours: null as number | null,
  total_hours: null as number | null,
  remaining_sessions: null as number | null,
  remark: '',
})

const cardTypes = [
  { value: 'hourly', label: '小时卡' },
  { value: 'daily', label: '天卡' },
  { value: 'weekly', label: '周卡' },
  { value: 'monthly', label: '月卡' },
  { value: 'quarterly', label: '季卡' },
  { value: 'session', label: '次卡' },
  { value: 'night_monthly', label: '夜读月卡' },
]

const cardTypeMap: Record<string, string> = Object.fromEntries(cardTypes.map((t) => [t.value, t.label]))
const sourceMap: Record<string, string> = {
  purchase: '在线购买', meituan: '美团兑换', douyin: '抖音兑换', admin: '后台发放', gift: '赠送',
}

function cardTypeLabel(v: string) { return cardTypeMap[v] || v }
function sourceLabel(v: string) { return sourceMap[v] || v }

const route = useRoute()

async function load() {
  loading.value = true
  try {
    const params: Record<string, unknown> = { page: page.value, page_size: 20 }
    if (userId.value) params.user_id = userId.value
    if (status.value !== null && status.value !== undefined) params.status = status.value
    const res = await http.get('/admin/period-cards', { params })
    list.value = res.data.items
    total.value = res.data.total
  } finally {
    loading.value = false
  }
}

function search() { page.value = 1; load() }

function openIssue() {
  issueForm.user_id = userId.value
  issueVisible.value = true
}

async function submitIssue() {
  if (!issueForm.user_id) {
    ElMessage.warning('请填写用户ID')
    return
  }
  submitting.value = true
  try {
    const res = await http.post('/admin/period-cards', {
      user_id: issueForm.user_id,
      store_id: issueForm.store_id || undefined,
      card_type: issueForm.card_type,
      reward_value: issueForm.reward_value,
      card_name: issueForm.card_name || undefined,
      remark: issueForm.remark || undefined,
    })
    ElMessage.success(res.message || '已发放')
    issueVisible.value = false
    load()
  } finally {
    submitting.value = false
  }
}

function openEdit(row: any) {
  editRow.value = row
  editForm.extend_days = 0
  editForm.remaining_hours = row.remaining_hours
  editForm.total_hours = row.total_hours
  editForm.remaining_sessions = row.remaining_sessions
  editForm.remark = row.remark || ''
  editVisible.value = true
}

async function submitEdit() {
  if (!editRow.value) return
  submitting.value = true
  try {
    const body: Record<string, unknown> = { remark: editForm.remark }
    if (editForm.extend_days > 0) body.extend_days = editForm.extend_days
    if (editForm.remaining_hours != null) body.remaining_hours = editForm.remaining_hours
    if (editForm.total_hours != null) body.total_hours = editForm.total_hours
    if (editForm.remaining_sessions != null) body.remaining_sessions = editForm.remaining_sessions
    const res = await http.patch(`/admin/period-cards/${editRow.value.id}`, body)
    ElMessage.success(res.message || '已更新')
    editVisible.value = false
    load()
  } finally {
    submitting.value = false
  }
}

async function revoke(row: any) {
  await ElMessageBox.confirm(`确定作废「${row.card_name}」吗？`, '作废期限卡', { type: 'warning' })
  await http.patch(`/admin/period-cards/${row.id}`, { status: 0, remark: '管理员作废' })
  ElMessage.success('已作废')
  load()
}

onMounted(() => {
  const q = route.query.userId
  if (q) userId.value = Number(q)
  load()
})
</script>

<style scoped>
.header-row { display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px; }
.right { display: flex; align-items: center; flex-wrap: wrap; }
.sub { font-size: 12px; color: #999; }
.pager { margin-top: 16px; display: flex; justify-content: flex-end; }
.hint { font-size: 12px; color: #999; margin-top: 4px; }
</style>
