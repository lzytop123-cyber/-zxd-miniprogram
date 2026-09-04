<template>
  <el-card class="page-card" shadow="never">
    <template #header>
      <div class="header-row">
        <span>预约订单</span>
        <div>
          <el-button type="primary" @click="openCreate">代同学预约</el-button>
          <el-button @click="load">刷新</el-button>
        </div>
      </div>
    </template>

    <el-form inline class="filters" @submit.prevent>
      <el-form-item label="订单号">
        <el-input v-model="filters.order_no" placeholder="模糊搜索" clearable style="width:150px" />
      </el-form-item>
      <el-form-item label="用户ID">
        <el-input-number v-model="filters.user_id" :min="1" controls-position="right" style="width:110px" />
      </el-form-item>
      <el-form-item label="门店">
        <el-select v-model="filters.store_id" clearable placeholder="全部" style="width:130px">
          <el-option v-for="s in stores" :key="s.id" :label="s.name" :value="s.id" />
        </el-select>
      </el-form-item>
      <el-form-item label="支付">
        <el-select v-model="filters.pay_status" clearable placeholder="全部" style="width:100px">
          <el-option label="待付款" :value="0" />
          <el-option label="已付款" :value="1" />
          <el-option label="已退款" :value="2" />
        </el-select>
      </el-form-item>
      <el-form-item label="状态">
        <el-select v-model="filters.status" clearable placeholder="全部" style="width:100px">
          <el-option label="已预约" :value="0" />
          <el-option label="使用中" :value="1" />
          <el-option label="已完成" :value="2" />
          <el-option label="已取消" :value="3" />
        </el-select>
      </el-form-item>
      <el-form-item>
        <el-button type="primary" @click="search">查询</el-button>
        <el-button @click="filterUnpaid">待付款</el-button>
        <el-button @click="reset">重置</el-button>
      </el-form-item>
    </el-form>

    <el-alert
      type="info"
      :closable="true"
      show-icon
      title="预约时段内自动入座；到店开门也会标为使用中。已付款订单可在本页换座。"
      class="tip"
    />

    <el-table
      :data="list"
      v-loading="loading"
      stripe
      size="small"
      border
      :max-height="tableMaxHeight"
      class="order-table"
    >
      <el-table-column prop="order_no" label="订单号" width="158" fixed />
      <el-table-column label="用户" width="108">
        <template #default="{ row }">
          <div class="cell-main">{{ row.user_nickname || '-' }}</div>
          <div class="sub">ID {{ row.user_id }}</div>
        </template>
      </el-table-column>
      <el-table-column prop="store_name" label="门店" width="100" show-overflow-tooltip />
      <el-table-column label="座位" width="88">
        <template #default="{ row }">
          <div class="cell-main">{{ row.seat_code || '-' }}</div>
          <div v-if="row.zone_name" class="sub">{{ row.zone_name }}</div>
        </template>
      </el-table-column>
      <el-table-column label="套餐" min-width="100" show-overflow-tooltip>
        <template #default="{ row }">{{ row.usage_label || row.bill_type_label || billLabel(row.bill_type) }}</template>
      </el-table-column>
      <el-table-column label="来源" width="96" show-overflow-tooltip>
        <template #default="{ row }">{{ row.pay_source_label || payTypeLabel(row.pay_type) }}</template>
      </el-table-column>
      <el-table-column label="金额" width="86">
        <template #default="{ row }">{{ priceText(row) }}</template>
      </el-table-column>
      <el-table-column label="支付" width="78">
        <template #default="{ row }">
          <el-tag :type="row.pay_status === 1 ? 'success' : row.pay_status === 2 ? 'info' : 'warning'" size="small">
            {{ ['待付', '已付', '退款'][row.pay_status] || row.pay_status }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="78">
        <template #default="{ row }">
          <el-tag :type="statusTagType(row.status)" size="small">
            {{ row.status_label || statusLabel(row.status) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="预约时段" width="148">
        <template #default="{ row }">
          <div>{{ formatTime(row.start_time) }}</div>
          <div class="sub">至 {{ formatTime(row.end_time) }}</div>
        </template>
      </el-table-column>
      <el-table-column label="入座" width="132" show-overflow-tooltip>
        <template #default="{ row }">{{ formatTime(row.check_in_time) }}</template>
      </el-table-column>
      <el-table-column label="说明" min-width="120" show-overflow-tooltip>
        <template #default="{ row }">{{ row.status_hint || '-' }}</template>
      </el-table-column>
      <el-table-column label="操作" width="200" fixed="right">
        <template #default="{ row }">
          <el-button
            v-if="canChangeSeat(row)"
            link
            type="primary"
            @click="openChangeSeat(row)"
          >换座</el-button>
          <el-button
            v-if="row.status === 1"
            link
            type="warning"
            @click="forceCheckout(row)"
          >强制离座</el-button>
          <el-button
            v-if="canCancel(row)"
            link
            type="danger"
            @click="cancelOrder(row)"
          >取消</el-button>
          <el-button
            v-if="row.pay_status === 1"
            link
            type="info"
            @click="openRefund(row)"
          >登记退款</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="changeSeatVisible" title="换座" width="820px" destroy-on-close @closed="resetChangeSeat">
      <div v-if="changeSeatRow" class="change-seat-meta">
        <div>订单 <strong>{{ changeSeatRow.order_no }}</strong> · {{ changeSeatRow.user_nickname || '同学' }} ID {{ changeSeatRow.user_id }}</div>
        <div class="sub">
          当前座位 <strong>{{ seatOptions.current_seat_code || changeSeatRow.seat_code }}</strong>
          · {{ formatTime(seatOptions.start_time) }} 至 {{ formatTime(seatOptions.end_time) }}
        </div>
      </div>
      <el-alert v-if="seatOptions.hint" type="info" :closable="false" show-icon :title="seatOptions.hint" class="tip" />
      <div class="seat-legend">
        <span><i class="dot current"></i>当前</span>
        <span><i class="dot free"></i>空座</span>
        <span><i class="dot swap"></i>可对调</span>
        <span><i class="dot busy"></i>占用</span>
        <span><i class="dot off"></i>停用</span>
      </div>
      <div v-loading="seatOptionsLoading" class="floor-map">
        <div
          v-for="s in mappedSeats"
          :key="s.id"
          class="map-seat"
          :class="seatClass(s)"
          :style="mapSeatStyle(s)"
          :title="seatTitle(s)"
          @click="pickSeat(s)"
        >
          {{ s.seat_code }}
        </div>
      </div>
      <el-select
        v-if="!seatOptionsLoading && !mappedSeats.length && seatOptions.seats.length"
        v-model="changeSeatTargetId"
        filterable
        placeholder="选择座位"
        style="width:100%;margin-top:8px"
      >
        <el-option
          v-for="s in seatOptions.seats"
          :key="s.id"
          :label="`${s.seat_code} · ${s.zone_name}${s.reason ? '（' + s.reason + '）' : ''}`"
          :value="s.id"
          :disabled="!s.selectable && !s.can_swap"
        />
      </el-select>
      <div v-if="selectedSeat" class="seat-picked">
        <template v-if="selectedSeat.can_swap && selectedSeat.occupied_by">
          将与 <strong>{{ selectedSeat.occupied_by.nickname }}</strong>
          （ID {{ selectedSeat.occupied_by.user_id }} · {{ selectedSeat.seat_code }} · {{ selectedSeat.occupied_by.end_label }}）对调
        </template>
        <template v-else>
          换到空座 <strong>{{ selectedSeat.seat_code }}</strong>
          <span v-if="selectedSeat.zone_name"> · {{ selectedSeat.zone_name }}</span>
        </template>
      </div>
      <div v-else class="sub" style="margin-top:10px">点击空座换座，或点击橙色座位与对方对调。</div>
      <template #footer>
        <el-button @click="changeSeatVisible = false">取消</el-button>
        <el-button type="primary" :loading="changeSeatSubmitting" :disabled="!changeSeatTargetId" @click="submitChangeSeat">
          {{ selectedSeat?.can_swap ? '确认对调' : '确认换座' }}
        </el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="createVisible" title="代同学预约" width="640px" destroy-on-close @closed="resetCreate">
      <el-form label-width="88px">
        <el-form-item label="同学">
          <div class="create-user-row">
            <el-input v-model="createForm.keyword" placeholder="学号或手机号" clearable @keyup.enter="searchUser" />
            <el-button type="primary" :loading="userSearching" @click="searchUser">搜索</el-button>
          </div>
          <div v-if="createForm.user" class="create-user-picked">
            {{ createForm.user.nickname || '未设置昵称' }} · ID {{ createForm.user.id }}
            <span v-if="createForm.user.phone"> · {{ createForm.user.phone }}</span>
          </div>
        </el-form-item>
        <el-form-item label="门店">
          <el-select v-model="createForm.store_id" placeholder="选择门店" style="width:100%" @change="clearPreview">
            <el-option v-for="s in stores" :key="s.id" :label="s.name" :value="s.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="套餐">
          <el-select v-model="createForm.bill_type" style="width:100%" @change="clearPreview">
            <el-option v-for="item in createBillTypes" :key="item.value" :label="item.label" :value="item.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="开始">
          <el-date-picker
            v-model="createForm.start_time"
            type="datetime"
            placeholder="开始时间"
            format="YYYY-MM-DD HH:mm"
            value-format="YYYY-MM-DDTHH:mm:ss"
            style="width:100%"
            @change="clearPreview"
          />
        </el-form-item>
        <el-form-item label="结束">
          <el-date-picker
            v-model="createForm.end_time"
            type="datetime"
            placeholder="可空：按套餐自动算"
            format="YYYY-MM-DD HH:mm"
            value-format="YYYY-MM-DDTHH:mm:ss"
            style="width:100%"
            @change="clearPreview"
          />
        </el-form-item>
        <el-form-item>
          <el-button :loading="previewLoading" @click="previewCreate">预览价格和空座</el-button>
        </el-form-item>
        <template v-if="createPreview">
          <el-form-item label="时段">
            <span>{{ formatTime(createPreview.start_time) }} 至 {{ formatTime(createPreview.end_time) }}</span>
          </el-form-item>
          <el-form-item label="系统价">¥{{ createPreview.original_price }}</el-form-item>
          <el-form-item label="座位">
            <el-select v-model="createForm.seat_id" filterable placeholder="选择空座" style="width:100%">
              <el-option
                v-for="s in createPreview.seats"
                :key="s.id"
                :label="`${s.seat_code}${s.zone_name ? ' · ' + s.zone_name : ''}${s.available ? '' : '（已被占）'}`"
                :value="s.id"
                :disabled="!s.available"
              />
            </el-select>
          </el-form-item>
          <el-form-item label="实收金额">
            <el-input-number v-model="createForm.final_price" :min="0" :precision="2" :step="1" />
            <el-button link type="primary" @click="createForm.final_price = 0">免单</el-button>
          </el-form-item>
        </template>
      </el-form>
      <template #footer>
        <el-button @click="createVisible = false">取消</el-button>
        <el-button type="primary" :loading="createSubmitting" :disabled="!canSubmitCreate" @click="submitCreate">
          确认预约（前台收款）
        </el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="refundVisible" title="登记退款" width="420px">
      <p v-if="refundRow" class="sub">订单 {{ refundRow.order_no }} · ¥{{ refundRow.final_price ?? 0 }}</p>
      <el-input v-model="refundRemark" type="textarea" :rows="3" placeholder="退款原因/备注（人工登记，非微信自动退款）" />
      <template #footer>
        <el-button @click="refundVisible = false">取消</el-button>
        <el-button type="primary" :loading="refundSubmitting" @click="submitRefund">确认登记</el-button>
      </template>
    </el-dialog>

    <div class="pager">
      <el-pagination
        v-model:current-page="page"
        v-model:page-size="pageSize"
        :total="total"
        :page-sizes="[10, 20, 50]"
        layout="total, sizes, prev, pager, next"
        @current-change="load"
        @size-change="onPageSizeChange"
      />
    </div>
  </el-card>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, reactive, ref } from 'vue'
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
  admin: '前台收款',
}

function billLabel(v: string) {
  return billTypeMap[v] || v
}

function payTypeLabel(v: string) {
  return payTypeMap[v] || v || '-'
}

function priceText(row: any) {
  if (row.pay_type === 'admin') {
    return Number(row.final_price) === 0 ? '前台免单' : `¥${row.final_price ?? 0}`
  }
  if (row.pay_type === 'period_card' || (Number(row.final_price) === 0 && row.pay_status === 1)) {
    return row.card_name ? `期限卡 · ${row.card_name}` : '期限卡抵扣'
  }
  return `¥${row.final_price ?? 0}`
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
const viewportH = ref(typeof window !== 'undefined' ? window.innerHeight : 900)
const tableMaxHeight = computed(() => Math.max(320, viewportH.value - 310))

function onResize() {
  viewportH.value = window.innerHeight
}

const filters = reactive<{ order_no: string; user_id: number | null; store_id: number | null; pay_status: number | null; status: number | null }>({
  order_no: '',
  user_id: null,
  store_id: null,
  pay_status: null,
  status: null,
})
const stores = ref<any[]>([])

const createBillTypes = [
  { value: 'hourly', label: '按小时' },
  { value: 'daily', label: '天卡' },
  { value: 'weekly', label: '周卡' },
  { value: 'monthly', label: '月卡' },
  { value: 'quarterly', label: '季卡' },
  { value: 'session', label: '次卡' },
  { value: 'night', label: '夜读' },
]

const createVisible = ref(false)
const userSearching = ref(false)
const previewLoading = ref(false)
const createSubmitting = ref(false)
const createPreview = ref<any>(null)
const createForm = reactive({
  keyword: '',
  user: null as any,
  store_id: null as number | null,
  bill_type: 'daily',
  start_time: '',
  end_time: '',
  seat_id: null as number | null,
  final_price: 0,
})

const canSubmitCreate = computed(() => {
  return !!(createForm.user && createForm.store_id && createForm.seat_id && createPreview.value)
})

function resetCreate() {
  createForm.keyword = ''
  createForm.user = null
  createForm.store_id = stores.value[0]?.id || null
  createForm.bill_type = 'daily'
  createForm.start_time = ''
  createForm.end_time = ''
  createForm.seat_id = null
  createForm.final_price = 0
  createPreview.value = null
}

function openCreate() {
  resetCreate()
  createVisible.value = true
}

function clearPreview() {
  createPreview.value = null
  createForm.seat_id = null
}

async function searchUser() {
  const keyword = createForm.keyword.trim()
  if (!keyword) {
    ElMessage.warning('请输入学号或手机号')
    return
  }
  userSearching.value = true
  try {
    const res = await http.get('/admin/users', { params: { keyword, page: 1, page_size: 8 } })
    const items = res.data?.items || []
    if (!items.length) {
      createForm.user = null
      ElMessage.warning('没有找到已注册用户')
      return
    }
    createForm.user = items[0]
    if (items.length > 1) {
      ElMessage.success(`已选中 ${createForm.user.nickname || createForm.user.id}，共 ${items.length} 条匹配，默认取第一条`)
    }
  } finally {
    userSearching.value = false
  }
}

async function previewCreate() {
  if (!createForm.store_id || !createForm.start_time) {
    ElMessage.warning('请选择门店和开始时间')
    return
  }
  previewLoading.value = true
  try {
    const res = await http.post('/admin/reservations/preview', {
      store_id: createForm.store_id,
      bill_type: createForm.bill_type,
      start_time: createForm.start_time,
      end_time: createForm.end_time || null,
    })
    createPreview.value = res.data
    createForm.final_price = Number(res.data.original_price || 0)
    const first = (res.data.seats || []).find((s: any) => s.available)
    createForm.seat_id = first ? first.id : null
  } catch (e: any) {
    createPreview.value = null
    ElMessage.error(e?.response?.data?.detail || e?.message || '预览失败')
  } finally {
    previewLoading.value = false
  }
}

async function submitCreate() {
  if (!canSubmitCreate.value) return
  createSubmitting.value = true
  try {
    const res = await http.post('/admin/reservations/create', {
      user_id: createForm.user.id,
      store_id: createForm.store_id,
      bill_type: createForm.bill_type,
      start_time: createForm.start_time,
      end_time: createForm.end_time || null,
      seat_id: createForm.seat_id,
      final_price: createForm.final_price,
    })
    ElMessage.success(res.message || '已预约')
    createVisible.value = false
    load()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || e?.message || '下单失败')
  } finally {
    createSubmitting.value = false
  }
}

async function load() {
  loading.value = true
  try {
    const params: Record<string, unknown> = { page: page.value, page_size: pageSize.value }
    if (filters.order_no) params.order_no = filters.order_no
    if (filters.user_id) params.user_id = filters.user_id
    if (filters.store_id) params.store_id = filters.store_id
    if (filters.pay_status !== null && filters.pay_status !== undefined) params.pay_status = filters.pay_status
    if (filters.status !== null && filters.status !== undefined) params.status = filters.status
    const res = await http.get('/admin/reservations', { params })
    list.value = res.data.items || []
    total.value = res.data.total || 0
  } catch (e: any) {
    list.value = []
    total.value = 0
    ElMessage.error(e?.response?.data?.detail || e?.message || '加载订单失败')
  } finally {
    loading.value = false
  }
}

function search() {
  page.value = 1
  load()
}

function onPageSizeChange() {
  page.value = 1
  load()
}

function reset() {
  filters.order_no = ''
  filters.user_id = null
  filters.store_id = null
  filters.pay_status = null
  filters.status = null
  search()
}

function filterUnpaid() {
  filters.pay_status = 0
  filters.status = 0
  search()
}

function canCancel(row: any) {
  if (row.status === 3 || row.status === 2) return false
  if (row.status === 1) return false
  return row.status === 0
}

async function cancelOrder(row: any) {
  const msg = row.pay_status === 0
    ? `确定取消未支付订单 ${row.order_no} 吗？座位将立即释放。`
    : row.pay_type === 'admin'
      ? `确定取消订单 ${row.order_no} 吗？前台收款不退款，仅释放座位。`
      : `确定取消订单 ${row.order_no} 吗？已付款将尝试退款。`
  await ElMessageBox.confirm(msg, '取消订单', { type: 'warning' })
  await http.post(`/admin/reservations/${row.id}/cancel`)
  ElMessage.success('已取消')
  load()
}

async function forceCheckout(row: any) {
  await ElMessageBox.confirm(`确定强制结束订单 ${row.order_no} 吗？`, '强制离座', { type: 'warning' })
  const res = await http.post(`/admin/reservations/${row.id}/force-checkout`)
  ElMessage.success(res.message || '已离座')
  load()
}

const changeSeatVisible = ref(false)
const changeSeatRow = ref<any>(null)
const changeSeatTargetId = ref<number | null>(null)
const changeSeatSubmitting = ref(false)
const seatOptionsLoading = ref(false)
type SeatOption = {
  id: number
  seat_code: string
  zone_name: string
  pos_x?: number | null
  pos_y?: number | null
  selectable: boolean
  can_swap?: boolean
  reason: string | null
  occupied_by?: { reservation_id: number; user_id: number; nickname: string; end_label: string } | null
}

const seatOptions = reactive<{
  current_seat_code: string | null
  current_seat_id: number | null
  start_time: string
  end_time: string
  hint: string
  seats: SeatOption[]
}>({
  current_seat_code: null,
  current_seat_id: null,
  start_time: '',
  end_time: '',
  hint: '',
  seats: [],
})

const selectedSeat = computed(() => seatOptions.seats.find((s) => s.id === changeSeatTargetId.value) || null)
const mappedSeats = computed(() => seatOptions.seats.filter((s) => s.pos_x != null && s.pos_y != null))

function mapSeatStyle(seat: { pos_x?: number | null; pos_y?: number | null }) {
  const x = Number(seat.pos_x) || 0
  const y = Number(seat.pos_y) || 0
  const left = x <= 100 ? x : x / 9
  const top = y <= 100 ? y : y / 7
  return { left: `${left}%`, top: `${top}%` }
}

function seatClass(s: SeatOption) {
  return {
    current: s.id === seatOptions.current_seat_id,
    free: s.selectable,
    swap: !!s.can_swap,
    busy: !s.selectable && !s.can_swap && s.reason !== '座位已停用' && s.id !== seatOptions.current_seat_id,
    off: s.reason === '座位已停用',
    on: s.id === changeSeatTargetId.value,
  }
}

function seatTitle(s: SeatOption) {
  if (s.id === seatOptions.current_seat_id) return `${s.seat_code} 当前座位`
  if (s.selectable) return `${s.seat_code} 空座`
  return `${s.seat_code} ${s.reason || ''}`
}

function pickSeat(s: SeatOption) {
  if (s.id === seatOptions.current_seat_id) return
  if (s.selectable || s.can_swap) {
    changeSeatTargetId.value = s.id
    return
  }
  ElMessage.warning(s.reason || '该座位不可选')
}

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
  seatOptions.current_seat_id = null
  seatOptions.start_time = ''
  seatOptions.end_time = ''
  seatOptions.hint = ''
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
    seatOptions.current_seat_id = res.data.current_seat_id
    seatOptions.start_time = res.data.start_time
    seatOptions.end_time = res.data.end_time
    seatOptions.hint = res.data.hint || ''
    seatOptions.seats = res.data.seats || []
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '加载座位失败')
    changeSeatVisible.value = false
  } finally {
    seatOptionsLoading.value = false
  }
}

async function submitChangeSeat() {
  if (!changeSeatRow.value || !changeSeatTargetId.value) return
  const target = selectedSeat.value
  const occupiedBy = target?.occupied_by
  const swapping = !!(target?.can_swap && occupiedBy)
  const tip = swapping
    ? `确定将 ${changeSeatRow.value.seat_code} 与 ${target.seat_code}（${occupiedBy?.nickname} ID ${occupiedBy?.user_id}，${occupiedBy?.end_label}）对调吗？两人只换座位，订单还在各自名下。对方若是月卡，整段都会换到当前座位。`
    : `确定将订单 ${changeSeatRow.value.order_no} 从 ${changeSeatRow.value.seat_code} 换到 ${target?.seat_code || changeSeatTargetId.value} 吗？`
  await ElMessageBox.confirm(tip, swapping ? '确认对调' : '确认换座', { type: 'warning' })
  changeSeatSubmitting.value = true
  try {
    const res = swapping && occupiedBy
      ? await http.post(`/admin/reservations/${changeSeatRow.value.id}/swap-seats`, {
          other_reservation_id: occupiedBy.reservation_id,
        })
      : await http.post(`/admin/reservations/${changeSeatRow.value.id}/change-seat`, {
          seat_id: changeSeatTargetId.value,
        })
    ElMessage.success(res.message || '换座成功')
    changeSeatVisible.value = false
    load()
  } finally {
    changeSeatSubmitting.value = false
  }
}

const refundVisible = ref(false)
const refundRow = ref<any>(null)
const refundRemark = ref('')
const refundSubmitting = ref(false)

function openRefund(row: any) {
  refundRow.value = row
  refundRemark.value = ''
  refundVisible.value = true
}

async function submitRefund() {
  if (!refundRow.value || !refundRemark.value.trim()) {
    ElMessage.warning('请填写退款备注')
    return
  }
  refundSubmitting.value = true
  try {
    await http.post(`/admin/reservations/${refundRow.value.id}/mark-refund`, {
      remark: refundRemark.value.trim(),
    })
    ElMessage.success('已登记退款')
    refundVisible.value = false
    load()
  } finally {
    refundSubmitting.value = false
  }
}

onMounted(async () => {
  window.addEventListener('resize', onResize)
  const res = await http.get('/admin/stores')
  stores.value = res.data || []
  load()
})

onUnmounted(() => {
  window.removeEventListener('resize', onResize)
})
</script>

<style scoped>
.page-card :deep(.el-card__body) { padding-top: 12px; }
.header-row { display: flex; justify-content: space-between; align-items: center; }
.filters { margin-bottom: 4px; }
.filters :deep(.el-form-item) { margin-bottom: 8px; margin-right: 12px; }
.tip { margin-bottom: 10px; }
.order-table { width: 100%; }
.cell-main { line-height: 1.3; }
.sub { font-size: 12px; color: #999; line-height: 1.3; }
.change-seat-meta { line-height: 1.8; }
.seat-legend { display: flex; gap: 14px; margin: 10px 0 8px; font-size: 12px; color: #666; }
.seat-legend .dot {
  display: inline-block; width: 10px; height: 10px; border-radius: 3px; margin-right: 4px; vertical-align: -1px;
}
.seat-legend .dot.current { background: #2D6A4F; }
.seat-legend .dot.free { background: #409eff; }
.seat-legend .dot.swap { background: #e6a23c; }
.seat-legend .dot.busy { background: #f56c6c; }
.seat-legend .dot.off { background: #c0c4cc; }
.floor-map {
  position: relative;
  width: 100%;
  aspect-ratio: 900 / 700;
  background: #fafafa;
  border: 1px dashed #ddd;
  border-radius: 8px;
  overflow: hidden;
}
.map-seat {
  position: absolute;
  width: 36px;
  height: 36px;
  margin-left: -18px;
  margin-top: -18px;
  border-radius: 8px;
  background: #409eff;
  color: #fff;
  font-size: 11px;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 2px 6px rgba(0,0,0,0.12);
  cursor: pointer;
  user-select: none;
}
.map-seat.current { background: #2D6A4F; cursor: default; }
.map-seat.swap { background: #e6a23c; }
.map-seat.busy { background: #f56c6c; cursor: default; }
.map-seat.off { background: #c0c4cc; cursor: default; }
.map-seat.on { outline: 3px solid #1C2B20; outline-offset: 1px; }
.seat-picked { margin-top: 10px; font-size: 13px; color: #2D6A4F; }
.create-user-row { display: flex; gap: 8px; width: 100%; }
.create-user-picked { margin-top: 6px; color: #2D6A4F; font-size: 13px; }
.pager { margin-top: 12px; display: flex; justify-content: flex-end; }
</style>
