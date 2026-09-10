<template>
  <div class="board" :class="{ fullscreen: isFull }" ref="boardEl">
    <div class="top-bar">
      <div class="brand">实时占座 · {{ data?.store_name || '' }}</div>
      <div class="tools">
        <el-select
          v-model="storeId"
          size="small"
          style="width: 180px"
          @change="load"
        >
          <el-option v-for="s in stores" :key="s.id" :label="s.name" :value="s.id" />
        </el-select>
        <span class="clock">{{ clock }}</span>
        <el-button size="small" @click="toggleFull">
          {{ isFull ? '退出全屏' : '全屏' }}
        </el-button>
      </div>
    </div>

    <div class="stat-bar">
      <div class="rate">
        <div class="rate-num">{{ data?.occupancy_rate ?? 0 }}<span class="rate-suffix">%</span></div>
        <div class="rate-lbl">入座率</div>
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

    <div class="map-wrap">
      <div class="floor-map">
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
                <span class="lbl">今日可用</span><span>{{ seat.info.today_hours }}</span>
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

    <div class="legend">
      <span class="refresh">每 10 秒自动刷新 · 服务器 {{ data?.server_time || '-' }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import http from '../api/http'

const stores = ref<any[]>([])
const storeId = ref<number | null>(null)
const data = ref<any>(null)
const isFull = ref(false)
const boardEl = ref<HTMLElement | null>(null)
const clock = ref('')
let timer: number | undefined
let clockTimer: number | undefined

const seats = computed<any[]>(() =>
  (data.value?.seats || []).filter((s: any) => s.left_pct != null && s.top_pct != null)
)

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


async function load() {
  if (!storeId.value) return
  const res = await http.get(`/admin/stores/${storeId.value}/live-board`)
  data.value = res.data
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

onMounted(async () => {
  const res = await http.get('/admin/stores')
  stores.value = res.data
  if (stores.value.length) {
    storeId.value = stores.value[0].id
    await load()
  }
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
.tools { display: flex; align-items: center; gap: 12px; }
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
</style>
