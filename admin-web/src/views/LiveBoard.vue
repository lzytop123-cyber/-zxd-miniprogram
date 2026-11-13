<template>
  <div class="board" :class="{ fullscreen: isFull }" ref="boardEl">
    <div class="top-bar">
      <div class="brand">实时占座<span v-if="storeName"> · {{ storeName }}</span></div>
      <div class="tools">
        <el-select
          v-model="storeId"
          size="small"
          style="width: 180px"
          placeholder="选择门店"
          :disabled="!isHq || !stores.length"
          @change="pickStore"
        >
          <el-option v-for="s in stores" :key="s.id" :label="s.name" :value="s.id" />
        </el-select>
        <el-button
          size="small"
          :type="expiring.length ? 'danger' : ''"
          @click="showExpiring = !showExpiring"
        >
          即将到期 {{ expiring.length }}
        </el-button>
        <span class="clock">{{ clock }}</span>
        <el-button size="small" @click="toggleFull">
          {{ isFull ? '退出全屏' : '全屏' }}
        </el-button>
      </div>
    </div>

    <div v-if="showExpiring && expiring.length" class="expire-panel">
      <div class="expire-head">
        <span>{{ expiring.length }} 张卡即将到期 · 7 天内 / 剩余次数/时长临近</span>
        <el-button link @click="showExpiring = false">收起</el-button>
      </div>
      <el-table :data="expiring" size="small" stripe max-height="240">
        <el-table-column label="用户" min-width="120">
          <template #default="{ row }">
            {{ row.user_name }}
            <span class="phone">{{ row.phone }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="card_name" label="卡种" min-width="110" />
        <el-table-column label="到期情况" min-width="180">
          <template #default="{ row }">
            <span v-if="row.reason === 'date'">
              {{ row.end_date }}
              <el-tag :type="row.days_left <= 2 ? 'danger' : 'warning'" size="small" round>
                剩 {{ row.days_left }} 天
              </el-tag>
            </span>
            <span v-else-if="row.reason === 'sessions'">
              <el-tag type="warning" size="small" round>剩 {{ row.remaining_sessions }} 次</el-tag>
            </span>
            <span v-else-if="row.reason === 'hours'">
              <el-tag type="warning" size="small" round>剩 {{ row.remaining_hours }} 小时</el-tag>
            </span>
          </template>
        </el-table-column>
        <el-table-column label="上次提醒" width="130">
          <template #default="{ row }">
            {{ row.reminded_at || '未提醒' }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="120">
          <template #default="{ row }">
            <el-button
              size="small"
              type="primary"
              :loading="remindingId === row.card_id"
              @click="sendRemind(row)"
            >
              发送提醒
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <div v-if="data" class="stat-bar">
      <div class="rate">
        <div class="rate-num">{{ data?.occupancy_rate ?? 0 }}<span class="rate-suffix">%</span></div>
        <div class="rate-lbl">占用率</div>
      </div>
      <div class="bar-wrap">
        <div class="bar">
          <div
            v-for="seg in segments"
            :key="seg.key"
            :class="'seg s-' + seg.key"
            :style="{ width: seg.width }"
            :title="`${seg.name} ${seg.count}`"
          />
        </div>
        <div class="chips">
          <span class="chip"><i class="dot s-occupied" />在座 <b>{{ data?.counts?.occupied ?? 0 }}</b></span>
          <span class="chip"><i class="dot s-booked" />已预约未到 <b>{{ data?.counts?.booked ?? 0 }}</b></span>
          <span class="chip"><i class="dot s-free" />空闲 <b>{{ data?.counts?.free ?? 0 }}</b></span>
          <span class="chip"><i class="dot s-disabled" />停用 <b>{{ data?.counts?.disabled ?? 0 }}</b></span>
          <span class="chip total">共 <b>{{ totalSeats }}</b> 座</span>
        </div>
      </div>
    </div>

    <div v-if="boardError" class="board-notice" role="status">
      <span>{{ boardError }}</span>
      <el-button size="small" @click="reload">重试</el-button>
    </div>
    <div v-if="!data && !boardError" class="board-notice" role="status">正在加载门店座位…</div>
    <div v-if="seats.length" class="map-wrap">
      <div
        class="floor-map"
        :class="{ 'floor-map--image': isImageMap }"
        :style="floorMapStyle"
      >
        <img v-if="mapImageUrl && !imageFailed" class="floor-bg" :src="mapImageUrl" alt="门店平面图" @error="imageFailed = true" />
        <svg v-else-if="data?.map_mode === 'legacy'" class="floor-bg legacy-plan" viewBox="0 0 900 700" preserveAspectRatio="none" aria-label="固定布局平面图">
          <path d="M48 656V44H852V597H665 M48 656H604 M665 597V656 M295 44V324 M295 374V656 M549 44V324 M549 374V656 M48 324H221 M300 324H428 M510 324H549 M48 374H191 M270 374H366 M448 374H549" />
          <g>
            <text x="176" y="161">沉浸区 A</text>
            <text x="433" y="161">沉浸区 B</text>
            <text x="694" y="334">标准区</text>
            <text x="171" y="515">沉浸区 C</text>
            <text x="599" y="604">入口</text>
          </g>
        </svg>
        <div
          v-for="seat in seats"
          :key="seat.id"
          class="seat"
          :class="[
            's-' + seat.state,
            { 'not-checked': seat.info && !seat.info.checked_in },
            popSide(seat),
          ]"
          :style="seatStyle(seat)"
        >
          <div class="code">{{ seat.seat_code }}</div>
          <template v-if="seat.info">
            <div class="who">{{ shortName(seat.info.user) }}</div>
            <div class="time">{{ seat.info.is_hourly ? seat.info.today_hours : seat.info.bill_type }}</div>
          </template>
          <div v-if="seat.info" class="pop">
            <div class="pop-head">
              <span class="pop-user">{{ seat.info.user }}</span>
              <span class="pop-badge" :class="'b-' + seat.state">
                {{ seat.info.checked_in ? '已入座' : '已预约未到店' }}
              </span>
            </div>
            <div class="pop-grid">
              <span class="lbl">座位</span><span>{{ seat.seat_code }} · {{ seat.zone_name }}</span>
              <span class="lbl">手机</span><span>{{ seat.info.phone || '未绑定' }}</span>
              <span class="lbl">类型</span><span>{{ seat.info.bill_type }}</span>
              <span class="lbl">有效期</span><span>{{ seat.info.period }}</span>
              <template v-if="!seat.info.is_hourly">
                <span class="lbl">预计离场</span><span>今日 {{ seat.info.leave_at }}</span>
              </template>
              <template v-if="seat.info.check_in">
                <span class="lbl">到店</span><span>{{ seat.info.check_in }}</span>
              </template>
              <span class="lbl">订单</span><span class="mono">{{ seat.info.order_no }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
    <div v-if="imageFailed && mapImageUrl" class="board-notice">
      平面图图片加载失败，座位状态仍按已发布坐标显示。
      <el-button size="small" @click="reload">重试</el-button>
    </div>
    <div v-if="data && !seats.length" class="board-notice">
      {{ data.map_mode === 'image' ? '暂无可显示的已发布座位图，请到座位管理检查发布状态。' : '该门店暂无带坐标的座位，请到座位管理检查布局。' }}
    </div>
    <div v-if="unplacedSeats.length" class="unplaced">
      <div>未定位座位</div>
      <span v-for="seat in unplacedSeats" :key="seat.id" :class="'s-' + seat.state">
        {{ seat.seat_code }} · {{ stateLabels[seat.state] || seat.state }}
      </span>
    </div>

    <div class="legend">
      <span class="refresh">每 10 秒自动刷新 · 服务器 {{ data?.server_time || '-' }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import http from '../api/http'
import { useRequiredStoreId } from '../composables/useWorkingStore'
import { resolveRequiredStoreId, setWorkingStoreId } from '../utils/workingStore'
import { isHqAdmin } from '../utils/adminAuth'

const stores = ref<any[]>([])
const storeId = ref<number | null>(null)
const data = ref<any>(null)
const boardError = ref('')
const imageFailed = ref(false)
const isHq = isHqAdmin()
const storeName = computed(() => stores.value.find((store) => store.id === storeId.value)?.name || data.value?.store_name || '')
const stateLabels: Record<string, string> = { free: '空闲', occupied: '在座', booked: '已预约未到', disabled: '停用' }
const isFull = ref(false)
const boardEl = ref<HTMLElement | null>(null)
const clock = ref('')
let timer: number | undefined
let clockTimer: number | undefined

const seats = computed<any[]>(() =>
  (data.value?.seats || []).filter((s: any) => s.left_pct != null && s.top_pct != null)
)
const unplacedSeats = computed<any[]>(() =>
  (data.value?.seats || []).filter((s: any) => s.left_pct == null || s.top_pct == null)
)

const isImageMap = computed(() => data.value?.map_mode === 'image' && !!data.value?.map_image_url)
const mapImageUrl = computed(() => data.value?.map_image_url || '')
const floorMapStyle = computed(() => {
  const ratio = Number(data.value?.map_aspect_ratio)
  if (isImageMap.value && ratio > 0) {
    return { aspectRatio: String(ratio) }
  }
  return {}
})

const totalSeats = computed(() => {
  const c = data.value?.counts
  return c ? c.occupied + c.booked + c.free + c.disabled : 0
})

const segments = computed(() => {
  const c = data.value?.counts
  if (!c) return []
  const total = c.occupied + c.booked + c.free + c.disabled || 1
  const pct = (n: number) => `${(n / total * 100).toFixed(1)}%`
  return [
    { key: 'occupied', name: '在座', count: c.occupied, width: pct(c.occupied) },
    { key: 'booked', name: '已预约未到', count: c.booked, width: pct(c.booked) },
    { key: 'free', name: '空闲', count: c.free, width: pct(c.free) },
    { key: 'disabled', name: '停用', count: c.disabled, width: pct(c.disabled) },
  ].filter((s) => s.count > 0)
})

function seatStyle(seat: any) {
  return { left: `${seat.left_pct}%`, top: `${seat.top_pct}%` }
}

function popSide(seat: any) {
  // 顶部座位往下弹，左右边缘座位气泡对齐边缘避免溢出
  const cls: string[] = []
  cls.push(seat.top_pct < 35 ? 'pop-below' : 'pop-above')
  if (seat.left_pct < 20) cls.push('pop-left')
  else if (seat.left_pct > 80) cls.push('pop-right')
  return cls
}

function shortName(name: string) {
  if (!name) return ''
  const s = name.replace(/\*+/, '*')
  return s.length > 5 ? s.slice(0, 4) + '…' : s
}


const expiring = ref<any[]>([])
const showExpiring = ref(false)
const remindingId = ref<number | null>(null)

let boardRequest = 0
let expiringRequest = 0
async function load() {
  const id = storeId.value
  if (!id || !stores.value.some((store) => store.id === id)) return
  const requestId = ++boardRequest
  if (data.value?.store_id !== id) {
    data.value = null
    expiring.value = []
    showExpiring.value = false
    imageFailed.value = false
  }
  try {
    const res = await http.get(`/admin/stores/${id}/live-board`)
    if (requestId !== boardRequest || id !== storeId.value) return
    if (data.value?.map_image_url !== res.data.map_image_url) imageFailed.value = false
    data.value = res.data
    boardError.value = ''
    void loadExpiring()
  } catch (e: any) {
    if (requestId !== boardRequest || id !== storeId.value) return
    boardError.value = e?.response?.data?.detail || '实时占座加载失败，请重试'
  }
}

async function loadExpiring() {
  const id = storeId.value
  if (!id) return
  const requestId = ++expiringRequest
  try {
    const res = await http.get(`/admin/stores/${id}/expiring-cards`, { params: { days: 7 } })
    if (requestId === expiringRequest && id === storeId.value) expiring.value = res.data.items || []
  } catch {
    if (requestId === expiringRequest && id === storeId.value) expiring.value = []
  }
}

async function sendRemind(row: any) {
  remindingId.value = row.card_id
  try {
    await http.post(`/admin/period-cards/${row.card_id}/remind`)
    ElMessage.success(`已提醒 ${row.user_name}`)
    await loadExpiring()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || e?.message || '发送失败')
  } finally {
    remindingId.value = null
  }
}

async function onStoreChange() {
  boardError.value = ''
  await load()
}

function pickStore(id: number) {
  setWorkingStoreId(id)
  void onStoreChange()
}

function tickClock() {
  const d = new Date()
  const pad = (n: number) => String(n).padStart(2, '0')
  clock.value = `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
}

function toggleFull() {
  const el = boardEl.value
  if (!el) return
  if (!document.fullscreenElement) {
    el.requestFullscreen?.()
    isFull.value = true
  } else {
    document.exitFullscreen?.()
    isFull.value = false
  }
}

function onFsChange() {
  isFull.value = !!document.fullscreenElement
}

useRequiredStoreId(storeId, () => stores.value[0]?.id, onStoreChange)

async function reload() {
  boardError.value = ''
  if (!stores.value.length) {
    try {
      const res = await http.get('/admin/stores')
      stores.value = res.data || []
    } catch (e: any) {
      boardError.value = e?.response?.data?.detail || '门店列表加载失败，请重试'
      return
    }
    if (!stores.value.length) {
      boardError.value = '当前账号没有可查看的门店，请核对门店绑定。'
      return
    }
    const preferred = resolveRequiredStoreId(stores.value[0].id)
    storeId.value = stores.value.some((store) => store.id === preferred) ? preferred : stores.value[0].id
  }
  imageFailed.value = false
  await load()
}

onMounted(() => {
  void reload()
  timer = window.setInterval(load, 10000)
  clockTimer = window.setInterval(tickClock, 1000)
  tickClock()
  document.addEventListener('fullscreenchange', onFsChange)
})

onUnmounted(() => {
  if (timer) clearInterval(timer)
  if (clockTimer) clearInterval(clockTimer)
  document.removeEventListener('fullscreenchange', onFsChange)
})
</script>

<style scoped>
.board {
  background: #0e1116;
  color: #e6edf3;
  min-height: calc(100vh - 88px);
  margin: -16px;
  padding: 20px 24px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.board.fullscreen { min-height: 100vh; margin: 0; }
.top-bar { display: flex; justify-content: space-between; align-items: center; gap: 12px; flex-wrap: wrap; }
.brand { font-size: 22px; font-weight: 700; letter-spacing: 1px; color: #FFD000; }
.tools { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
.clock { font-variant-numeric: tabular-nums; font-size: 18px; color: #9aa5b1; }

.stat-bar {
  display: flex;
  align-items: center;
  gap: 24px;
  flex-wrap: wrap;
  background: linear-gradient(180deg, #171c24 0%, #12161d 100%);
  border: 1px solid #232a35;
  border-radius: 12px;
  padding: 16px 22px;
}
.rate { display: flex; flex-direction: column; align-items: center; min-width: 120px; }
.rate-num { font-size: 44px; font-weight: 800; color: #FFD000; line-height: 1; font-variant-numeric: tabular-nums; }
.rate-suffix { font-size: 22px; margin-left: 2px; opacity: 0.8; }
.rate-lbl { color: #8b95a1; font-size: 13px; margin-top: 6px; letter-spacing: 2px; }
.bar-wrap { flex: 1; display: flex; flex-direction: column; gap: 10px; min-width: 0; }
.bar {
  display: flex;
  height: 14px;
  border-radius: 999px;
  overflow: hidden;
  background: #1a1f2a;
  border: 1px solid #232a35;
}
.seg { height: 100%; transition: width 0.4s ease; }
.seg.s-occupied { background: linear-gradient(90deg, #ff6b6b, #b13d3d); }
.seg.s-booked { background: linear-gradient(90deg, #f5a623, #c58a1e); }
.seg.s-free { background: linear-gradient(90deg, #7ed957, #4a7a2d); }
.seg.s-disabled { background: #333944; }
.chips { display: flex; flex-wrap: wrap; gap: 6px 18px; font-size: 13px; color: #c1c9d3; }
.chip { display: inline-flex; align-items: center; }
.chip b { font-weight: 700; margin-left: 6px; font-variant-numeric: tabular-nums; }
.chip.total { color: #8b95a1; margin-left: auto; }
.chip .dot { width: 10px; height: 10px; border-radius: 3px; margin-right: 6px; }
.chip .dot.s-occupied { background: #ff6b6b; }
.chip .dot.s-booked { background: #f5a623; }
.chip .dot.s-free { background: #7ed957; }
.chip .dot.s-disabled { background: #4b5563; }

.map-wrap { flex: 1; display: flex; justify-content: center; align-items: flex-start; }
.board-notice { display: flex; align-items: center; gap: 12px; padding: 16px; border: 1px solid #303946; border-radius: 8px; color: #d2dae4; }
.unplaced { display: flex; align-items: center; flex-wrap: wrap; gap: 8px; color: #c1c9d3; }
.unplaced span { padding: 4px 8px; border-radius: 5px; }
.floor-map {
  position: relative;
  width: 100%;
  max-width: 1200px;
  aspect-ratio: 900 / 700;
  container-type: inline-size;
  background:
    linear-gradient(#161b22 1px, transparent 1px) 0 0 / 40px 40px,
    linear-gradient(90deg, #161b22 1px, transparent 1px) 0 0 / 40px 40px,
    #0b0e13;
  border: 1px solid #232a35;
  border-radius: 12px;
  overflow: hidden;
}
.floor-map--image {
  background: #111;
  max-width: 880px;
}
.floor-map--image .seat {
  width: clamp(22px, 5.5cqw, 50px);
  height: clamp(18px, 4.6cqw, 42px);
  padding: 2px;
}
.floor-map--image .seat .time {
  display: none;
}
.floor-bg {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: contain;
  pointer-events: none;
}
.legacy-plan path { fill: none; stroke: #52636f; stroke-width: 4px; stroke-linecap: round; }
.legacy-plan text { fill: #aebdc9; font-size: 17px; text-anchor: middle; }
.seat {
  position: absolute;
  width: clamp(40px, 5.5cqw, 66px);
  height: clamp(38px, 5.2cqw, 62px);
  transform: translate(-50%, -50%);
  border-radius: 8px;
  color: #fff;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  font-size: clamp(9px, 1cqw, 11px);
  padding: 3px 2px;
  box-shadow: 0 3px 8px rgba(0, 0, 0, 0.5);
  transition: transform 0.15s;
  cursor: default;
}
.seat:hover { transform: translate(-50%, -50%) scale(1.08); z-index: 3; box-shadow: 0 8px 20px rgba(0,0,0,0.7); }
.seat .code { font-weight: 700; font-size: clamp(11px, 1.35cqw, 15px); line-height: 1.1; }
.seat .who { font-size: clamp(9px, 1.05cqw, 12px); opacity: 0.92; margin-top: 2px; max-width: 92%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.seat .time { font-size: clamp(8px, 0.95cqw, 11px); opacity: 0.75; font-variant-numeric: tabular-nums; }

.seat .pop {
  position: absolute;
  left: 50%;
  transform: translateX(-50%);
  background: #1a1f2a;
  border: 1px solid #FFD000;
  border-radius: 10px;
  padding: 12px 14px;
  min-width: clamp(260px, 26cqw, 320px);
  font-size: 13px;
  color: #e6edf3;
  text-align: left;
  box-shadow: 0 16px 40px rgba(0,0,0,0.7);
  opacity: 0;
  pointer-events: none;
  transition: opacity 0.12s;
  z-index: 10;
  white-space: nowrap;
}
.seat.pop-above .pop { bottom: calc(100% + 10px); }
.seat.pop-below .pop { top: calc(100% + 10px); }
.seat.pop-left .pop { left: 0; transform: none; }
.seat.pop-right .pop { left: auto; right: 0; transform: none; }
.seat:hover .pop { opacity: 1; }
.seat .pop::after {
  content: '';
  position: absolute;
  left: 50%;
  transform: translateX(-50%);
  border: 6px solid transparent;
}
.seat.pop-above .pop::after { top: 100%; border-top-color: #FFD000; }
.seat.pop-below .pop::after { bottom: 100%; border-bottom-color: #FFD000; }
.seat.pop-left .pop::after { left: 20px; transform: none; }
.seat.pop-right .pop::after { left: auto; right: 20px; transform: none; }

.pop-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-bottom: 8px;
  margin-bottom: 8px;
  border-bottom: 1px solid #2a2f3a;
}
.pop-user { font-size: 15px; font-weight: 700; color: #FFD000; }
.pop-badge {
  padding: 2px 8px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 600;
}
.pop-badge.b-occupied { background: rgba(255,107,107,0.15); color: #ff8080; border: 1px solid #7a1b1b; }
.pop-badge.b-booked { background: rgba(245,166,35,0.15); color: #ffb84d; border: 1px solid #7a5a10; }
.pop-grid {
  display: grid;
  grid-template-columns: max-content 1fr;
  column-gap: 12px;
  row-gap: 4px;
}
.pop-grid .lbl { color: #8b95a1; font-size: 12px; }
.pop-grid .mono { font-family: 'Consolas', 'Menlo', monospace; font-size: 12px; opacity: 0.85; }

.s-free { background: #1e2a1e; border: 1px solid #2b4a2b; color: #7ed957; }
.s-occupied { background: linear-gradient(180deg, #7a1b1b, #4a0f0f); border: 1px solid #b13d3d; }
.s-occupied::after {
  content: '';
  position: absolute;
  inset: 0;
  border-radius: 6px;
  box-shadow: inset 0 0 0 1px rgba(255,107,107,0.5);
  animation: pulse 2.4s ease-in-out infinite;
  pointer-events: none;
}
.s-booked { background: linear-gradient(180deg, #7a5a10, #4a3708); border: 1px solid #c58a1e; }
.s-booked.not-checked { animation: dashSpin 8s linear infinite; }
.s-disabled { background: #14171d; border: 1px dashed #2a303a; color: #4b5563; opacity: 0.55; box-shadow: none; }

@keyframes pulse {
  0%, 100% { opacity: 0.4; }
  50% { opacity: 1; }
}
@keyframes dashSpin {
  to { background-position: 40px 0; }
}

.legend {
  display: flex;
  gap: 20px;
  align-items: center;
  color: #8b95a1;
  font-size: 13px;
  flex-wrap: wrap;
}
.legend .dot {
  display: inline-block;
  width: 12px; height: 12px;
  border-radius: 3px;
  margin-right: 6px;
  vertical-align: middle;
}
.legend .refresh { margin-left: auto; }

.expire-panel {
  background: linear-gradient(180deg, #201a0a 0%, #12160e 100%);
  border: 1px solid #7a5a10;
  border-radius: 10px;
  padding: 12px 16px;
}
.expire-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  color: #ffb84d;
  font-size: 13px;
  margin-bottom: 10px;
}
.expire-panel :deep(.el-table) { background: transparent; color: #e6edf3; }
.expire-panel :deep(.el-table tr), .expire-panel :deep(.el-table td),
.expire-panel :deep(.el-table th.el-table__cell) { background: transparent !important; }
.expire-panel :deep(.el-table--enable-row-hover .el-table__body tr:hover > td) {
  background: rgba(255,208,0,0.06) !important;
}
.expire-panel :deep(.el-table__inner-wrapper::before) { display: none; }
.expire-panel .phone { color: #8b95a1; margin-left: 8px; font-size: 12px; }
</style>
