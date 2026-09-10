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

    <div class="stats">
      <div class="stat">
        <div class="label">在座</div>
        <div class="value hot">{{ data?.counts?.occupied ?? 0 }}</div>
      </div>
      <div class="stat">
        <div class="label">已预约未到</div>
        <div class="value warn">{{ data?.counts?.booked ?? 0 }}</div>
      </div>
      <div class="stat">
        <div class="label">空闲</div>
        <div class="value ok">{{ data?.counts?.free ?? 0 }}</div>
      </div>
      <div class="stat">
        <div class="label">停用</div>
        <div class="value mute">{{ data?.counts?.disabled ?? 0 }}</div>
      </div>
      <div class="stat main">
        <div class="label">入座率</div>
        <div class="value big">{{ data?.occupancy_rate ?? 0 }}%</div>
      </div>
    </div>

    <div class="map-wrap">
      <div class="floor-map">
        <div
          v-for="seat in seats"
          :key="seat.id"
          class="seat"
          :class="['s-' + seat.state, { 'not-checked': seat.info && !seat.info.checked_in }]"
          :style="seatStyle(seat)"
          :title="seatTip(seat)"
        >
          <div class="code">{{ seat.seat_code }}</div>
          <div v-if="seat.info" class="who">{{ shortName(seat.info.user) }}</div>
        </div>
      </div>
    </div>

    <div class="legend">
      <span><i class="dot s-occupied" />在座</span>
      <span><i class="dot s-booked" />已预约未到</span>
      <span><i class="dot s-free" />空闲</span>
      <span><i class="dot s-disabled" />停用</span>
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
  (data.value?.seats || []).filter((s: any) => s.pos_x != null && s.pos_y != null)
)

function seatStyle(seat: any) {
  const x = Number(seat.pos_x) || 0
  const y = Number(seat.pos_y) || 0
  const left = x <= 100 ? x : x / 9
  const top = y <= 100 ? y : y / 7
  return { left: `${left}%`, top: `${top}%` }
}

function seatTip(s: any) {
  if (!s.info) return `${s.seat_code} · ${labelOf(s.state)}`
  return `${s.seat_code} · ${s.info.user} · ${s.info.start}-${s.info.end}`
}

function shortName(name: string) {
  if (!name) return ''
  // 手机号中段脱敏后仍偏长，截前 4 个可见字符
  const s = name.replace(/\*+/, '*')
  return s.length > 5 ? s.slice(0, 4) + '…' : s
}

function labelOf(state: string) {
  return (
    { free: '空闲', booked: '已预约未到', occupied: '在座', disabled: '停用' }[
      state
    ] || state
  )
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
.top-bar { display: flex; justify-content: space-between; align-items: center; }
.brand { font-size: 22px; font-weight: 700; letter-spacing: 1px; color: #FFD000; }
.tools { display: flex; align-items: center; gap: 12px; }
.clock { font-variant-numeric: tabular-nums; font-size: 18px; color: #9aa5b1; }

.stats { display: grid; grid-template-columns: repeat(5, 1fr); gap: 12px; }
.stat {
  background: linear-gradient(180deg, #171c24 0%, #12161d 100%);
  border: 1px solid #232a35;
  border-radius: 10px;
  padding: 14px 18px;
}
.stat.main { background: linear-gradient(180deg, #1f1a0a 0%, #171205 100%); border-color: #3a2f10; }
.label { color: #8b95a1; font-size: 13px; }
.value { font-size: 30px; font-weight: 700; margin-top: 6px; font-variant-numeric: tabular-nums; }
.value.big { font-size: 40px; color: #FFD000; }
.value.hot { color: #ff6b6b; }
.value.warn { color: #f5a623; }
.value.ok { color: #7ed957; }
.value.mute { color: #6b7280; }

.map-wrap { flex: 1; display: flex; justify-content: center; align-items: flex-start; }
.floor-map {
  position: relative;
  width: 100%;
  max-width: 1200px;
  aspect-ratio: 900 / 700;
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
  width: 48px;
  height: 44px;
  margin-left: -24px;
  margin-top: -22px;
  border-radius: 6px;
  color: #fff;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  box-shadow: 0 3px 8px rgba(0, 0, 0, 0.5);
  transition: transform 0.15s;
  overflow: hidden;
}
.seat:hover { transform: scale(1.25); z-index: 3; box-shadow: 0 8px 20px rgba(0,0,0,0.7); }
.seat .code { font-weight: 700; font-size: 13px; line-height: 1.1; }
.seat .who { font-size: 10px; opacity: 0.85; margin-top: 1px; max-width: 42px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

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
