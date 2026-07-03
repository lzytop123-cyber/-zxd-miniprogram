<template>
  <el-card>
    <template #header>
      <div class="header-row">
        <div class="left">
          <span>价格管理</span>
          <el-select v-model="storeId" style="width: 200px; margin-left: 12px" @change="load">
            <el-option v-for="s in stores" :key="s.id" :label="s.name" :value="s.id" />
          </el-select>
        </div>
        <div class="right-actions">
          <el-button @click="openCopy">复制到其他门店</el-button>
          <el-button type="primary" @click="openAdd">新增规则</el-button>
        </div>
      </div>
    </template>

    <el-table :data="list" v-loading="loading" stripe>
      <el-table-column prop="bill_type" label="计费类型" width="110">
        <template #default="{ row }">{{ billLabel(row.bill_type) }}</template>
      </el-table-column>
      <el-table-column prop="seat_type" label="座位类型" width="100" />
      <el-table-column prop="price" label="价格(元)" width="100" />
      <el-table-column prop="min_hours" label="最少小时" width="90" />
      <el-table-column prop="max_hours" label="最多小时" width="90" />
      <el-table-column prop="valid_days" label="天数/次数" width="100">
        <template #default="{ row }">
          <span v-if="row.bill_type === 'session'">{{ row.valid_days || 10 }}次</span>
          <span v-else-if="row.valid_days != null">{{ row.valid_days }}天</span>
          <span v-else>-</span>
        </template>
      </el-table-column>
      <el-table-column label="夜读时段" width="130">
        <template #default="{ row }">
          <span v-if="row.night_start">{{ row.night_start }}-{{ row.night_end }}</span>
          <span v-else>-</span>
        </template>
      </el-table-column>
      <el-table-column prop="remark" label="说明" min-width="140" show-overflow-tooltip />
      <el-table-column prop="is_active" label="状态" width="80">
        <template #default="{ row }">
          <el-tag :type="row.is_active === 1 ? 'success' : 'info'">
            {{ row.is_active === 1 ? '启用' : '停用' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="100" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
          <el-button link type="danger" @click="removeRule(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="showDialog" :title="dialogTitle" width="520px">
      <el-form :model="form" label-width="100px">
        <el-form-item v-if="!editingId" label="计费类型">
          <el-select v-model="form.bill_type" style="width:100%">
            <el-option v-for="opt in billTypes" :key="opt.value" :label="opt.label" :value="opt.value" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="!editingId" label="座位类型">
          <el-input v-model="form.seat_type" placeholder="standard" />
        </el-form-item>
        <el-form-item label="价格(元)"><el-input-number v-model="form.price" :min="0" :precision="2" style="width:100%" /></el-form-item>
        <el-form-item label="最少小时"><el-input-number v-model="form.min_hours" :min="0" style="width:100%" /></el-form-item>
        <el-form-item label="最多小时"><el-input-number v-model="form.max_hours" :min="0" style="width:100%" /></el-form-item>
        <el-form-item :label="form.bill_type === 'session' ? '次数' : '有效天数'">
          <el-input-number v-model="form.valid_days" :min="1" style="width:100%" />
          <div v-if="form.bill_type === 'session'" class="field-hint">次卡在线购买时发放的次数</div>
        </el-form-item>
        <el-form-item label="夜读开始"><el-input v-model="form.night_start" placeholder="18:00" /></el-form-item>
        <el-form-item label="夜读结束"><el-input v-model="form.night_end" placeholder="23:30" /></el-form-item>
        <el-form-item label="说明"><el-input v-model="form.remark" /></el-form-item>
        <el-form-item label="排序"><el-input-number v-model="form.sort_order" :min="0" style="width:100%" /></el-form-item>
        <el-form-item label="启用">
          <el-switch v-model="form.is_active" :active-value="1" :inactive-value="0" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showDialog = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submit">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="copyVisible" title="复制定价到其他门店" width="420px">
      <el-form label-width="100px">
        <el-form-item label="源门店">
          <el-input :model-value="stores.find(s => s.id === storeId)?.name || ''" disabled />
        </el-form-item>
        <el-form-item label="目标门店">
          <el-select v-model="copyTargetId" style="width:100%">
            <el-option
              v-for="s in stores.filter(x => x.id !== storeId)"
              :key="s.id"
              :label="s.name"
              :value="s.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="覆盖已有">
          <el-switch v-model="copyOverwrite" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="copyVisible = false">取消</el-button>
        <el-button type="primary" :loading="copying" @click="submitCopy">确认复制</el-button>
      </template>
    </el-dialog>
  </el-card>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import http from '../api/http'

const billTypes = [
  { value: 'hourly', label: '按小时' },
  { value: 'daily', label: '天卡' },
  { value: 'weekly', label: '周卡' },
  { value: 'monthly', label: '月卡' },
  { value: 'quarterly', label: '季卡' },
  { value: 'session', label: '次卡' },
  { value: 'night', label: '夜读' },
  { value: 'night_monthly', label: '夜读月卡' },
]

const billLabelMap = Object.fromEntries(billTypes.map((b) => [b.value, b.label]))

const stores = ref<any[]>([])
const storeId = ref<number | null>(null)
const list = ref<any[]>([])
const loading = ref(false)
const saving = ref(false)
const showDialog = ref(false)
const editingId = ref<number | null>(null)
const copyVisible = ref(false)
const copyTargetId = ref<number | null>(null)
const copyOverwrite = ref(false)
const copying = ref(false)
const form = reactive<any>({})

const dialogTitle = computed(() => (editingId.value ? '编辑价格规则' : '新增价格规则'))

function billLabel(v: string) {
  return billLabelMap[v] || v
}

function resetForm() {
  Object.assign(form, {
    bill_type: 'hourly',
    seat_type: 'standard',
    price: 0,
    min_hours: null,
    max_hours: null,
    valid_days: null,
    night_start: '',
    night_end: '',
    remark: '',
    sort_order: 0,
    is_active: 1,
  })
}

async function loadStores() {
  const res = await http.get('/admin/stores')
  stores.value = res.data
  if (!storeId.value && stores.value.length) {
    storeId.value = stores.value[0].id
  }
}

async function load() {
  if (!storeId.value) return
  loading.value = true
  try {
    const res = await http.get(`/admin/stores/${storeId.value}/pricing`)
    list.value = res.data
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
  Object.assign(form, {
    bill_type: row.bill_type,
    seat_type: row.seat_type,
    price: row.price,
    min_hours: row.min_hours,
    max_hours: row.max_hours,
    valid_days: row.valid_days,
    night_start: row.night_start || '',
    night_end: row.night_end || '',
    remark: row.remark || '',
    sort_order: row.sort_order,
    is_active: row.is_active,
  })
  showDialog.value = true
}

async function submit() {
  if (!storeId.value) return
  saving.value = true
  try {
    const payload = {
      price: form.price,
      min_hours: form.min_hours,
      max_hours: form.max_hours,
      valid_days: form.valid_days,
      night_start: form.night_start || null,
      night_end: form.night_end || null,
      remark: form.remark,
      sort_order: form.sort_order,
      is_active: form.is_active,
    }
    if (editingId.value) {
      await http.patch(`/admin/pricing/${editingId.value}`, payload)
    } else {
      await http.post(`/admin/stores/${storeId.value}/pricing`, {
        bill_type: form.bill_type,
        seat_type: form.seat_type,
        ...payload,
      })
    }
    ElMessage.success('已保存')
    showDialog.value = false
    load()
  } finally {
    saving.value = false
  }
}

function openCopy() {
  if (!storeId.value) return
  copyTargetId.value = stores.value.find((s) => s.id !== storeId.value)?.id || null
  copyOverwrite.value = false
  copyVisible.value = true
}

async function submitCopy() {
  if (!storeId.value || !copyTargetId.value) {
    ElMessage.warning('请选择目标门店')
    return
  }
  copying.value = true
  try {
    const res = await http.post(
      `/admin/stores/${storeId.value}/pricing/copy-to/${copyTargetId.value}`,
      { overwrite: copyOverwrite.value },
    )
    ElMessage.success(`复制完成：新增 ${res.data.added}，更新 ${res.data.updated}`)
    copyVisible.value = false
  } finally {
    copying.value = false
  }
}

async function removeRule(row: any) {
  await ElMessageBox.confirm(`确定删除「${billLabel(row.bill_type)} / ${row.seat_type}」价格规则吗？`, '删除确认', { type: 'warning' })
  await http.delete(`/admin/pricing/${row.id}`)
  ElMessage.success('已删除')
  load()
}

onMounted(async () => {
  await loadStores()
  await load()
})
</script>

<style scoped>
.header-row { display: flex; justify-content: space-between; align-items: center; }
.left, .right-actions { display: flex; align-items: center; gap: 8px; }
.field-hint { margin-top: 6px; font-size: 12px; color: #909399; }
</style>
