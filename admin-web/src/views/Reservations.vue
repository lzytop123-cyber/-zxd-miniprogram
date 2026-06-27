<template>
  <el-card>
    <template #header>
      <div class="header-row">
        <span>预约订单</span>
        <el-button @click="load">刷新</el-button>
      </div>
    </template>

    <el-form inline class="filters">
      <el-form-item label="订单号">
        <el-input v-model="filters.order_no" placeholder="模糊搜索" clearable style="width:160px" />
      </el-form-item>
      <el-form-item label="用户ID">
        <el-input-number v-model="filters.user_id" :min="1" controls-position="right" style="width:120px" />
      </el-form-item>
      <el-form-item label="支付">
        <el-select v-model="filters.pay_status" clearable placeholder="全部" style="width:110px">
          <el-option label="待付款" :value="0" />
          <el-option label="已付款" :value="1" />
          <el-option label="已退款" :value="2" />
        </el-select>
      </el-form-item>
      <el-form-item label="状态">
        <el-select v-model="filters.status" clearable placeholder="全部" style="width:110px">
          <el-option label="已预约" :value="0" />
          <el-option label="使用中" :value="1" />
          <el-option label="已完成" :value="2" />
          <el-option label="已取消" :value="3" />
        </el-select>
      </el-form-item>
      <el-form-item>
        <el-button type="primary" @click="search">查询</el-button>
        <el-button @click="reset">重置</el-button>
      </el-form-item>
    </el-form>

    <el-alert
      type="info"
      :closable="false"
      show-icon
      title="预约时段内系统自动入座；用户到店开门也会自动标记为使用中。已付款订单可在本页「换座」调整座位。"
      style="margin-bottom: 12px"
    />

    <el-table :data="list" v-loading="loading" stripe>
      <el-table-column prop="order_no" label="订单号" width="170" />
      <el-table-column label="用户" width="120">
        <template #default="{ row }">
          <div>{{ row.user_nickname || '-' }}</div>
          <div class="sub">ID {{ row.user_id }}</div>
        </template>
      </el-table-column>
      <el-table-column prop="store_name" label="门店" width="120" />
      <el-table-column prop="seat_code" label="座位" width="70" />
      <el-table-column label="类型" width="90">
        <template #default="{ row }">{{ billLabel(row.bill_type) }}</template>
      </el-table-column>
      <el-table-column label="支付" width="90">
        <template #default="{ row }">{{ payTypeLabel(row.pay_type) }}</template>
      </el-table-column>
      <el-table-column prop="final_price" label="金额" width="70">
        <template #default="{ row }">¥{{ row.final_price ?? 0 }}</template>
      </el-table-column>
      <el-table-column prop="pay_status" label="支付状态" width="90">
        <template #default="{ row }">
          <el-tag :type="row.pay_status === 1 ? 'success' : row.pay_status === 2 ? 'info' : 'warning'" size="small">
            {{ ['待付款', '已付款', '已退款'][row.pay_status] || row.pay_status }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="订单状态" width="100">
        <template #default="{ row }">
          <el-tag :type="statusTagType(row.status)" size="small">
            {{ row.status_label || statusLabel(row.status) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="说明" min-width="160" show-overflow-tooltip>
        <template #default="{ row }">{{ row.status_hint || '-' }}</template>
      </el-table-column>
      <el-table-column label="入座时间" width="160">
        <template #default="{ row }">{{ formatTime(row.check_in_time) }}</template>
      </el-table-column>
      <el-table-column label="预约时段" width="200">
        <template #default="{ row }">
          <div>{{ formatTime(row.start_time) }}</div>
          <div class="sub">至 {{ formatTime(row.end_time) }}</div>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="140" fixed="right">
        <template #default="{ row }">
          <el-button
            v-if="canChangeSeat(row)"
            link
            type="primary"
            @click="openChangeSeat(row)"
          >换座</el-button>
          <el-button
            v-if="row.status === 0 && row.pay_status === 1"
            link
            type="danger"
            @click="cancelOrder(row)"
          >取消</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="changeSeatVisible" title="换座" width="480px" destroy-on-close @closed="resetChangeSeat">
      <div v-if="changeSeatRow" class="change-seat-meta">
        <div>订单 <strong>{{ changeSeatRow.order_no }}</strong></div>
        <div class="sub">
          当前座位 <strong>{{ seatOptions.current_seat_code || changeSeatRow.seat_code }}</strong>
          · {{ formatTime(seatOptions.start_time) }} 至 {{ formatTime(seatOptions.end_time) }}
        </div>
      </div>
      <el-form label-width="88px" style="margin-top: 16px">
        <el-form-item label="新座位">
          <el-select
            v-model="changeSeatTargetId"
            filterable
            placeholder="选择可用座位"
            style="width: 100%"
            :loading="seatOptionsLoading"
          >
            <el-option
              v-for="s in seatOptions.seats"
              :key="s.id"
              :label="`${s.seat_code} · ${s.zone_name}${s.reason ? '（' + s.reason + '）' : ''}`"
              :value="s.id"
              :disabled="!s.selectable"
            />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="changeSeatVisible = false">取消</el-button>
        <el-button type="primary" :loading="changeSeatSubmitting" :disabled="!changeSeatTargetId" @click="submitChangeSeat">
          确认换座
        </el-button>
      </template>
    </el-dialog>

    <div class="pager">
      <el-pagination
        v-model:current-page="page"
        v-model:page-size="pageSize"
        :total="total"
        layout="total, prev, pager, next"
        @current-change="load"
      />
    </div>
  </el-card>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import http from '../api/http'

const billTypeMap: Record<string, string> = {
  hourly: '按小时',
  daily: '天卡',
  weekly: '周卡',
  monthly: '月卡',
  quarterly: '季卡',
  session: '次卡',
  night: '夜读',
  night_monthly: '夜读月卡',
}

const payTypeMap: Record<string, string> = {
  wechat: '微信',
  balance: '余额',
  period_card: '期限卡',
}

function billLabel(v: string) {
  return billTypeMap[v] || v
}

function payTypeLabel(v: string) {
  return payTypeMap[v] || v || '-'
}

function statusLabel(status: number) {
  return ['已预约', '使用中', '已完成', '已取消'][status] || String(status)
}

function statusTagType(status: number) {
  if (status === 1) return 'success'
  if (status === 2) return 'info'
  if (status === 3) return 'info'
  return 'warning'
}

function formatTime(v: string | null | undefined) {
  if (!v) return '-'
  return String(v).replace('T', ' ').slice(0, 16)
}

const list = ref<any[]>([])
const loading = ref(false)
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)
const filters = reactive<{ order_no: string; user_id: number | null; pay_status: number | null; status: number | null }>({
  order_no: '',
  user_id: null,
  pay_status: null,
  status: null,
})

async function load() {
  loading.value = true
  try {
    const params: Record<string, unknown> = { page: page.value, page_size: pageSize.value }
    if (filters.order_no) params.order_no = filters.order_no
    if (filters.user_id) params.user_id = filters.user_id
    if (filters.pay_status !== null && filters.pay_status !== undefined) params.pay_status = filters.pay_status
    if (filters.status !== null && filters.status !== undefined) params.status = filters.status
    const res = await http.get('/admin/reservations', { params })
    list.value = res.data.items
    total.value = res.data.total
  } finally {
    loading.value = false
  }
}

function search() {
  page.value = 1
  load()
}

function reset() {
  filters.order_no = ''
  filters.user_id = null
  filters.pay_status = null
  filters.status = null
  search()
}

async function cancelOrder(row: any) {
  await ElMessageBox.confirm(`确定取消订单 ${row.order_no} 吗？已付款将尝试退款。`, '取消订单', { type: 'warning' })
  await http.post(`/admin/reservations/${row.id}/cancel`)
  ElMessage.success('已取消')
  load()
}

const changeSeatVisible = ref(false)
const changeSeatRow = ref<any>(null)
const changeSeatTargetId = ref<number | null>(null)
const changeSeatSubmitting = ref(false)
const seatOptionsLoading = ref(false)
const seatOptions = reactive<{
  current_seat_code: string | null
  start_time: string
  end_time: string
  seats: Array<{ id: number; seat_code: string; zone_name: string; selectable: boolean; reason: string | null }>
}>({
  current_seat_code: null,
  start_time: '',
  end_time: '',
  seats: [],
})

function canChangeSeat(row: any) {
  if (row.pay_status !== 1) return false
  if (row.status !== 0 && row.status !== 1) return false
  if (!row.end_time) return true
  return new Date(row.end_time).getTime() > Date.now()
}

function resetChangeSeat() {
  changeSeatRow.value = null
  changeSeatTargetId.value = null
  seatOptions.current_seat_code = null
  seatOptions.start_time = ''
  seatOptions.end_time = ''
  seatOptions.seats = []
}

async function openChangeSeat(row: any) {
  changeSeatRow.value = row
  changeSeatTargetId.value = null
  changeSeatVisible.value = true
  seatOptionsLoading.value = true
  try {
    const res = await http.get(`/admin/reservations/${row.id}/seat-options`)
    seatOptions.current_seat_code = res.data.current_seat_code
    seatOptions.start_time = res.data.start_time
    seatOptions.end_time = res.data.end_time
    seatOptions.seats = res.data.seats || []
    const first = seatOptions.seats.find((s) => s.selectable)
    if (first) changeSeatTargetId.value = first.id
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '加载座位失败')
    changeSeatVisible.value = false
  } finally {
    seatOptionsLoading.value = false
  }
}

async function submitChangeSeat() {
  if (!changeSeatRow.value || !changeSeatTargetId.value) return
  const target = seatOptions.seats.find((s) => s.id === changeSeatTargetId.value)
  await ElMessageBox.confirm(
    `确定将订单 ${changeSeatRow.value.order_no} 从 ${changeSeatRow.value.seat_code} 换到 ${target?.seat_code || changeSeatTargetId.value} 吗？`,
    '确认换座',
    { type: 'warning' },
  )
  changeSeatSubmitting.value = true
  try {
    const res = await http.post(`/admin/reservations/${changeSeatRow.value.id}/change-seat`, {
      seat_id: changeSeatTargetId.value,
    })
    ElMessage.success(res.message || '换座成功')
    changeSeatVisible.value = false
    load()
  } finally {
    changeSeatSubmitting.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.header-row { display: flex; justify-content: space-between; align-items: center; }
.filters { margin-bottom: 12px; }
.sub { font-size: 12px; color: #999; }
.change-seat-meta { line-height: 1.8; }
.pager { margin-top: 16px; display: flex; justify-content: flex-end; }
</style>
