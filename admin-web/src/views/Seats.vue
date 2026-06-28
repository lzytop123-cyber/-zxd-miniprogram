<template>
  <el-card>
    <template #header>
      <div class="header">
        <div class="left">
          <span>座位管理</span>
          <el-select v-model="storeId" style="width: 200px; margin-left: 12px" @change="onStoreChange">
            <el-option v-for="s in stores" :key="s.id" :label="s.name" :value="s.id" />
          </el-select>
        </div>
        <div class="right">
          <el-button @click="openCreate">新增座位</el-button>
          <el-button :loading="ensuring" type="primary" @click="ensureSeats">补全标准座位</el-button>
        </div>
      </div>
    </template>

    <el-alert
      v-if="summary && !summary.is_complete"
      type="warning"
      :closable="false"
      show-icon
      class="summary-alert"
      :title="`座位不完整：当前 ${summary.actual_count}/${summary.expected_count}，缺少 ${summary.missing_codes.join('、')}`"
      description="点击右上角「补全标准座位」可一键创建 A/B/C/D 共 27 个标准座位（含 D01–D03）。"
    />
    <el-alert
      v-else-if="summary && summary.is_complete"
      type="success"
      :closable="false"
      show-icon
      class="summary-alert"
      :title="`座位齐全：${summary.enabled_count}/${summary.actual_count} 个启用`"
    />

    <el-card v-if="layoutSeats.length" shadow="never" class="map-card">
      <template #header>平面图预览</template>
      <div class="floor-map">
        <div
          v-for="seat in layoutSeats"
          :key="seat.id"
          class="map-seat"
          :class="{ disabled: seat.status !== 1 }"
          :style="{ left: (seat.pos_x || 0) + 'px', top: (seat.pos_y || 0) + 'px' }"
          :title="seat.seat_code"
        >
          {{ seat.seat_code }}
        </div>
      </div>
    </el-card>

    <el-table :data="list" v-loading="loading" stripe>
      <el-table-column prop="seat_code" label="编号" width="90" />
      <el-table-column prop="zone_name" label="区域" width="80" />
      <el-table-column prop="seat_type" label="类型" width="90">
        <template #default="{ row }">
          {{ seatTypeLabel(row.seat_type) }}
        </template>
      </el-table-column>
      <el-table-column label="设施" width="120">
        <template #default="{ row }">
          <el-tag v-if="row.has_outlet" size="small">插座</el-tag>
          <el-tag v-if="row.has_curtain" size="small" type="warning">帘位</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="pos_x" label="X" width="60" />
      <el-table-column prop="pos_y" label="Y" width="60" />
      <el-table-column prop="status" label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="row.status === 1 ? 'success' : 'info'">
            {{ row.status === 1 ? '启用' : '停用' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="220">
        <template #default="{ row }">
          <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
          <el-button
            link
            :type="row.status === 1 ? 'danger' : 'success'"
            @click="toggle(row)"
          >
            {{ row.status === 1 ? '停用' : '启用' }}
          </el-button>
          <el-button link type="danger" @click="removeSeat(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="showDialog" :title="editingId ? '编辑座位' : '新增座位'" width="480px">
      <el-form :model="form" label-width="90px">
        <el-form-item label="编号"><el-input v-model="form.seat_code" :disabled="!!editingId" /></el-form-item>
        <el-form-item label="区域">
          <el-select v-model="form.zone_id" style="width:100%">
            <el-option v-for="z in zones" :key="z.id" :label="z.name" :value="z.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="类型">
          <el-select v-model="form.seat_type" style="width:100%">
            <el-option label="标准" value="standard" />
            <el-option label="靠窗" value="window" />
          </el-select>
        </el-form-item>
        <el-form-item label="坐标 X"><el-input-number v-model="form.pos_x" :min="0" style="width:100%" /></el-form-item>
        <el-form-item label="坐标 Y"><el-input-number v-model="form.pos_y" :min="0" style="width:100%" /></el-form-item>
        <el-form-item label="插座"><el-switch v-model="form.has_outlet" :active-value="1" :inactive-value="0" /></el-form-item>
        <el-form-item label="帘位"><el-switch v-model="form.has_curtain" :active-value="1" :inactive-value="0" /></el-form-item>
        <el-form-item label="启用"><el-switch v-model="form.status" :active-value="1" :inactive-value="0" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showDialog = false">取消</el-button>
        <el-button type="primary" @click="submitSeat">保存</el-button>
      </template>
    </el-dialog>
  </el-card>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import http from '../api/http'

const list = ref<any[]>([])
const layoutSeats = ref<any[]>([])
const zones = ref<any[]>([])
const stores = ref<any[]>([])
const loading = ref(false)
const ensuring = ref(false)
const storeId = ref<number | null>(null)
const summary = ref<any>(null)
const showDialog = ref(false)
const editingId = ref<number | null>(null)
const form = reactive({
  seat_code: '',
  zone_id: null as number | null,
  seat_type: 'standard',
  pos_x: 30,
  pos_y: 40,
  has_outlet: 1,
  has_curtain: 0,
  status: 1,
})

const seatTypeLabels: Record<string, string> = { standard: '标准', window: '靠窗' }
function seatTypeLabel(t: string) {
  return seatTypeLabels[t] || t
}

async function loadSummary() {
  if (!storeId.value) return
  const res = await http.get(`/admin/stores/${storeId.value}/seats/summary`)
  summary.value = res.data
}

async function loadLayout() {
  if (!storeId.value) return
  const res = await http.get(`/admin/stores/${storeId.value}/seats/layout`)
  zones.value = res.data.zones || []
  layoutSeats.value = (res.data.seats || []).filter((s: any) => s.pos_x != null && s.pos_y != null)
}

async function load() {
  if (!storeId.value) return
  loading.value = true
  try {
    const seatsRes = await http.get('/admin/seats', { params: { store_id: storeId.value } })
    list.value = seatsRes.data
    await Promise.all([loadSummary(), loadLayout()])
  } finally {
    loading.value = false
  }
}

async function onStoreChange() {
  await load()
}

async function ensureSeats() {
  if (!storeId.value) return
  await ElMessageBox.confirm('将按标准布局补全 A/B/C/D 区座位（已有编号不会重复创建）。', '补全标准座位', { type: 'info' })
  ensuring.value = true
  try {
    const res = await http.post(`/admin/stores/${storeId.value}/ensure-seats`)
    ElMessage.success(res.message || '补全成功')
    await load()
  } finally {
    ensuring.value = false
  }
}

function openCreate() {
  editingId.value = null
  Object.assign(form, {
    seat_code: '',
    zone_id: zones.value[0]?.id || null,
    seat_type: 'standard',
    pos_x: 30,
    pos_y: 40,
    has_outlet: 1,
    has_curtain: 0,
    status: 1,
  })
  showDialog.value = true
}

function openEdit(row: any) {
  editingId.value = row.id
  const zone = zones.value.find((z) => z.name === row.zone_name)
  Object.assign(form, {
    seat_code: row.seat_code,
    zone_id: zone?.id || null,
    seat_type: row.seat_type || 'standard',
    pos_x: row.pos_x ?? 30,
    pos_y: row.pos_y ?? 40,
    has_outlet: row.has_outlet,
    has_curtain: row.has_curtain,
    status: row.status,
  })
  showDialog.value = true
}

async function submitSeat() {
  if (!storeId.value || !form.seat_code.trim() || !form.zone_id) {
    ElMessage.warning('请填写座位编号并选择区域')
    return
  }
  if (editingId.value) {
    await http.patch(`/admin/seats/${editingId.value}`, { ...form })
    ElMessage.success('座位已更新')
  } else {
    await http.post('/admin/seats', { store_id: storeId.value, ...form })
    ElMessage.success('座位已创建')
  }
  showDialog.value = false
  load()
}

async function toggle(row: any) {
  const status = row.status === 1 ? 0 : 1
  await http.patch(`/admin/seats/${row.id}/status`, null, { params: { status } })
  ElMessage.success(status === 1 ? '已启用' : '已停用')
  load()
}

async function removeSeat(row: any) {
  await ElMessageBox.confirm(`确定删除座位 ${row.seat_code} 吗？有关联订单的座位无法删除。`, '删除确认', { type: 'warning' })
  try {
    await http.delete(`/admin/seats/${row.id}`)
    ElMessage.success('已删除')
    load()
  } catch (e: any) {
    ElMessage.error(e?.message || '删除失败')
  }
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
.header { display: flex; justify-content: space-between; align-items: center; gap: 12px; flex-wrap: wrap; }
.left, .right { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.summary-alert { margin-bottom: 16px; }
.map-card { margin-bottom: 16px; }
.floor-map {
  position: relative;
  min-height: 620px;
  background: #fafafa;
  border: 1px dashed #ddd;
  border-radius: 8px;
  overflow: auto;
}
.map-seat {
  position: absolute;
  width: 44px;
  height: 44px;
  border-radius: 8px;
  background: #409eff;
  color: #fff;
  font-size: 11px;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 2px 6px rgba(0,0,0,0.12);
}
.map-seat.disabled { background: #c0c4cc; }
</style>
