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
        >
          <div class="code">{{ seat.seat_code }}</div>
          <template v-if="seat.info">
            <div class="who">{{ shortName(seat.info.user) }}</div>
            <div class="time">{{ seat.info.is_hourly ? seat.info.today_hours : seat.info.bill_type }}</div>
          </template>
          <div v-if="seat.info" class="pop">
            <div class="pop-row"><span class="lbl">座位号</span>{{ seat.seat_code }} · {{ seat.zone_name }}</div>
            <div class="pop-row"><span class="lbl">用户昵称</span>{{ seat.info.user }}</div>
            <div class="pop-row"><span class="lbl">手机号码</span>{{ seat.info.phone || '未绑定' }}</div>
            <div class="pop-row"><span class="lbl">预约类型</span>{{ seat.info.bill_type }}</div>
            <div class="pop-row"><span class="lbl">有效期</span>{{ seat.info.period }}</div>
            <div v-if="!seat.info.is_hourly" class="pop-row"><span class="lbl">今日可用</span>{{ seat.info.today_hours }}</div>
            <div v-if="seat.info.check_in" class="pop-row"><span class="lbl">到店时间</span>{{ seat.info.check_in }}</div>
            <div class="pop-row"><span class="lbl">当前状态</span>{{ seat.info.checked_in ? '已入座' : '已预约未到店' }}</div>
            <div class="pop-row"><span class="lbl">订单编号</span>{{ seat.info.order_no }}</div>
          </div>
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
  (data.value?.seats || []).filter((s: any) => s.left_pct != null && s.top_pct != null)
)

function seatStyle(seat: any) {
  return { left: `${seat.left_pct}%`, top: `${seat.top_pct}%` }
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

.stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 12px; }
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
  bottom: calc(100% + 8px);
  left: 50%;
  transform: translateX(-50%);
  background: #1a1f2a;
  border: 1px solid #FFD000;
  border-radius: 8px;
  padding: 10px 12px;
  min-width: clamp(240px, 26cqw, 300px);
  font-size: clamp(11px, 1.1cqw, 13px);
  color: #e6edf3;
  text-align: left;
  box-shadow: 0 12px 32px rgba(0,0,0,0.7);
  opacity: 0;
  pointer-events: none;
  transition: opacity 0.15s;
  z-index: 10;
  white-space: nowrap;
}
.seat:hover .pop { opacity: 1; }
.seat .pop::after {
  content: '';
  position: absolute;
  top: 100%; left: 50%;
  transform: translateX(-50%);
  border: 6px solid transparent;
  border-top-color: #FFD000;
}
.pop-row { padding: 3px 0; }
.pop-row .lbl {
  display: inline-block;
  min-width: 68px;
  color: #8b95a1;
  margin-right: 10px;
}

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
