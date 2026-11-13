<template>
  <div class="seat-map-editor" v-loading="loading">
    <el-alert
      type="info"
      :closable="false"
      show-icon
      class="mb"
      :title="statusTitle"
      :description="statusDesc"
    />

    <div class="toolbar">
      <el-upload
        :show-file-list="false"
        accept="image/jpeg,image/png,image/webp,image/gif"
        :http-request="uploadImage"
        :disabled="uploading"
      >
        <el-button type="primary" plain :loading="uploading">上传/替换平面图</el-button>
      </el-upload>
      <el-button :disabled="!draftImage" :loading="saving" @click="saveDraft">保存草稿</el-button>
      <el-button type="success" :disabled="loading || saving || !draftImagePath || !draftBookableCount || !!missingSeats.length" :loading="publishing" @click="publish">
        发布
      </el-button>
      <el-button
        v-if="archived.length"
        :loading="restoring"
        @click="restoreLatest"
      >
        恢复上一版
      </el-button>
    </div>
    <el-alert
      v-if="draftImagePath && !loading"
      class="mb"
      :type="missingSeats.length ? 'warning' : 'info'"
      :closable="false"
      :title="`可订座位：已发布 ${publishedBookableCount} 座 → 草稿 ${draftBookableCount} 座，共 ${enabledSeats.length} 座启用`"
      :description="missingSeats.length ? `发布前请补标：${missingSeats.map(s => s.seat_code).join('、')}` : undefined"
    />

    <div class="layout">
      <div class="canvas-wrap">
        <div
          v-if="draftImage"
          ref="canvasRef"
          class="canvas"
          :style="{ aspectRatio: String(aspectRatio || 1.4) }"
          @click="onCanvasClick"
        >
          <img :src="draftImage" class="floor-img" alt="座位平面图" draggable="false" />
          <div
            v-for="m in markers"
            :key="m.seat_id"
            class="marker"
            :class="{ active: m.seat_id === selectedSeatId }"
            :style="{ left: m.x_pct + '%', top: m.y_pct + '%' }"
            @mousedown.stop.prevent="startDrag($event, m)"
            @click.stop="selectedSeatId = m.seat_id"
          >
            {{ seatLabel(m.seat_id) }}
          </div>
        </div>
        <el-empty v-else description="请先上传平面图" />
      </div>

      <div class="side">
        <el-card shadow="never" class="side-card">
          <template #header>区域</template>
          <div class="row">
            <el-input v-model="newZoneName" placeholder="新区域名" size="small" />
            <el-button size="small" type="primary" @click="createZone">添加</el-button>
          </div>
          <div v-for="z in zones" :key="z.id" class="zone-row">
            <span>{{ z.name }}</span>
            <el-button link type="danger" size="small" @click="removeZone(z)">删</el-button>
          </div>
        </el-card>

        <el-card shadow="never" class="side-card">
          <template #header>座位标记</template>
          <p class="hint">点选下方座位后在图上点击放置；可拖动调整。坐标为 0–100%。</p>
          <el-select v-model="selectedSeatId" placeholder="选择座位" filterable style="width:100%" class="mb">
            <el-option
              v-for="s in seatOptions"
              :key="s.id"
              :label="`${s.seat_code} · ${s.zone_name || ''}${markerSeatIds.has(s.id) ? '（已标）' : ''}`"
              :value="s.id"
            />
          </el-select>
          <el-button
            size="small"
            :disabled="!selectedSeatId || !draftImage"
            @click="placeSelectedAtCenter"
          >
            放到图中心
          </el-button>
          <el-button
            size="small"
            type="danger"
            plain
            :disabled="!selectedSeatId || !markerSeatIds.has(selectedSeatId)"
            @click="removeMarker(selectedSeatId)"
          >
            移除标记
          </el-button>
          <div class="marker-list">
            <div v-for="m in markers" :key="'list-' + m.seat_id" class="marker-row">
              <el-button link @click="selectedSeatId = m.seat_id">{{ seatLabel(m.seat_id) }}</el-button>
              <span class="muted">{{ m.x_pct.toFixed(1) }}%, {{ m.y_pct.toFixed(1) }}%</span>
            </div>
          </div>
        </el-card>

        <el-card v-if="published" shadow="never" class="side-card">
          <template #header>已发布（顾客可见）</template>
          <el-image v-if="published.image_url" :src="published.image_url" fit="contain" class="pub-img" />
          <div class="muted">标记 {{ published.marker_count || 0 }} 个 · 版本 v{{ published.version }}</div>
        </el-card>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { UploadRequestOptions } from 'element-plus'
import http from '../api/http'

const props = defineProps<{ storeId: number; storeName?: string }>()
const emit = defineEmits<{ published: [] }>()

type Marker = { seat_id: number; x_pct: number; y_pct: number; orient: string }

const loading = ref(false)
const uploading = ref(false)
const saving = ref(false)
const publishing = ref(false)
const restoring = ref(false)
const draftImage = ref('')
const draftImagePath = ref('')
const aspectRatio = ref(1.4)
const markers = ref<Marker[]>([])
const published = ref<any>(null)
const archived = ref<any[]>([])
const storeStatus = ref(0)
const zones = ref<any[]>([])
const seats = ref<any[]>([])
const selectedSeatId = ref<number | null>(null)
const newZoneName = ref('')
const canvasRef = ref<HTMLElement | null>(null)

const markerSeatIds = computed(() => new Set(markers.value.map((m) => m.seat_id)))
const enabledSeats = computed(() => seats.value.filter((s) => s.status === 1 && !s.is_buffer))
const missingSeats = computed(() => enabledSeats.value.filter((s) => !markerSeatIds.value.has(s.id)))
const draftBookableCount = computed(() => enabledSeats.value.length - missingSeats.value.length)
const publishedBookableCount = computed(() => {
  const ids = new Set((published.value?.markers || []).map((m: Marker) => Number(m.seat_id)))
  return enabledSeats.value.filter((s) => ids.has(s.id)).length
})
const storeLabel = computed(() => props.storeName || `门店 #${props.storeId}`)
const seatOptions = computed(() => seats.value.filter((s) => s.status === 1 || markerSeatIds.value.has(s.id)))
const statusTitle = computed(() => {
  const open = storeStatus.value === 1 ? '营业中' : '停业'
  const pub = published.value ? '已发布座位图' : '未发布座位图'
  return `${open} · ${pub}（发布不会自动开店）`
})
const statusDesc = computed(() =>
  draftImage.value
    ? '修改后请先「保存草稿」，顾客仍看已发布版本；确认无误再「发布」。'
    : '上传平面图后标注座位并发布，小程序才会显示本店布局。'
)

function seatLabel(id: number) {
  const s = seats.value.find((x) => x.id === id)
  return s?.seat_code || String(id)
}

let active = true
let loadRequest = 0
async function load() {
  if (!props.storeId) return
  const requestId = ++loadRequest
  loading.value = true
  try {
    const [mapRes, seatsRes, zonesRes] = await Promise.all([
      http.get(`/admin/stores/${props.storeId}/seat-map`),
      http.get('/admin/seats', { params: { store_id: props.storeId } }),
      http.get(`/admin/stores/${props.storeId}/zones`),
    ])
    if (!active || requestId !== loadRequest) return
    const data = mapRes.data || {}
    storeStatus.value = data.store_status ?? 0
    published.value = data.published
    archived.value = data.archived || []
    seats.value = seatsRes.data || []
    zones.value = zonesRes.data || []

    const draft = data.draft
    if (draft) {
      draftImage.value = draft.image_url || ''
      draftImagePath.value = draft.image_path || ''
      aspectRatio.value = draft.aspect_ratio || 1.4
      markers.value = (draft.markers || []).map((m: any) => ({
        seat_id: Number(m.seat_id),
        x_pct: Number(m.x_pct),
        y_pct: Number(m.y_pct),
        orient: m.orient || 'up',
      }))
    } else if (data.published) {
      draftImage.value = data.published.image_url || ''
      draftImagePath.value = data.published.image_path || ''
      aspectRatio.value = data.published.aspect_ratio || 1.4
      markers.value = (data.published.markers || []).map((m: any) => ({
        seat_id: Number(m.seat_id),
        x_pct: Number(m.x_pct),
        y_pct: Number(m.y_pct),
        orient: m.orient || 'up',
      }))
    } else {
      draftImage.value = ''
      draftImagePath.value = ''
      markers.value = []
    }
  } finally {
    if (requestId === loadRequest) loading.value = false
  }
}

async function uploadImage(options: UploadRequestOptions) {
  uploading.value = true
  try {
    const fd = new FormData()
    fd.append('file', options.file)
    const res = await http.post(`/admin/stores/${props.storeId}/seat-map/image`, fd, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    draftImagePath.value = res.data.path
    draftImage.value = res.data.url
    const img = new Image()
    img.onload = () => {
      if (img.width && img.height) aspectRatio.value = img.width / img.height
    }
    img.src = res.data.url
    ElMessage.success('平面图已上传，记得保存草稿')
  } finally {
    uploading.value = false
  }
}

function upsertMarker(seatId: number, x: number, y: number) {
  const x_pct = Math.min(100, Math.max(0, Number(x.toFixed(2))))
  const y_pct = Math.min(100, Math.max(0, Number(y.toFixed(2))))
  const idx = markers.value.findIndex((m) => m.seat_id === seatId)
  if (idx >= 0) {
    markers.value[idx] = { ...markers.value[idx], x_pct, y_pct }
  } else {
    markers.value.push({ seat_id: seatId, x_pct, y_pct, orient: 'up' })
  }
}

function onCanvasClick(e: MouseEvent) {
  if (!selectedSeatId.value || !canvasRef.value) return
  const rect = canvasRef.value.getBoundingClientRect()
  if (!rect.width || !rect.height) return
  const x = ((e.clientX - rect.left) / rect.width) * 100
  const y = ((e.clientY - rect.top) / rect.height) * 100
  upsertMarker(selectedSeatId.value, x, y)
}

function placeSelectedAtCenter() {
  if (!selectedSeatId.value) return
  upsertMarker(selectedSeatId.value, 50, 50)
}

function removeMarker(seatId: number | null) {
  if (!seatId) return
  markers.value = markers.value.filter((m) => m.seat_id !== seatId)
}

let drag: { seatId: number; move: (e: MouseEvent) => void; up: () => void } | null = null

function startDrag(e: MouseEvent, m: Marker) {
  selectedSeatId.value = m.seat_id
  const move = (ev: MouseEvent) => {
    if (!canvasRef.value) return
    const rect = canvasRef.value.getBoundingClientRect()
    if (!rect.width || !rect.height) return
    const x = ((ev.clientX - rect.left) / rect.width) * 100
    const y = ((ev.clientY - rect.top) / rect.height) * 100
    upsertMarker(m.seat_id, x, y)
  }
  const up = () => {
    window.removeEventListener('mousemove', move)
    window.removeEventListener('mouseup', up)
    drag = null
  }
  drag = { seatId: m.seat_id, move, up }
  window.addEventListener('mousemove', move)
  window.addEventListener('mouseup', up)
}

onBeforeUnmount(() => {
  active = false
  if (drag) {
    window.removeEventListener('mousemove', drag.move)
    window.removeEventListener('mouseup', drag.up)
  }
})

async function saveDraft() {
  if (!draftImagePath.value) {
    ElMessage.warning('请先上传平面图')
    return
  }
  saving.value = true
  try {
    await http.put(`/admin/stores/${props.storeId}/seat-map/draft`, {
      image_path: draftImagePath.value,
      aspect_ratio: aspectRatio.value || 1.4,
      markers: markers.value,
    })
    ElMessage.success('草稿已保存')
    await load()
  } finally {
    saving.value = false
  }
}

async function publish() {
  if (!draftImagePath.value || !draftBookableCount.value || missingSeats.value.length) return
  await ElMessageBox.confirm(`「${storeLabel.value}」发布后可订座位将从 ${publishedBookableCount.value} 座变为 ${draftBookableCount.value} 座。门店营业状态不变。`, '发布座位图', {
    type: 'warning',
  })
  if (!active) return
  publishing.value = true
  try {
    await saveDraft()
    if (!active) return
    await http.post(`/admin/stores/${props.storeId}/seat-map/publish`)
    if (!active) return
    ElMessage.success('已发布')
    emit('published')
    await load()
  } finally {
    publishing.value = false
  }
}

async function restoreLatest() {
  const target = archived.value[0]
  if (!target) return
  await ElMessageBox.confirm(`将「${storeLabel.value}」恢复到 v${target.version}？`, '恢复上一版', { type: 'warning' })
  if (!active) return
  restoring.value = true
  try {
    await http.post(`/admin/stores/${props.storeId}/seat-map/restore/${target.id}`)
    if (!active) return
    ElMessage.success('已恢复')
    emit('published')
    await load()
  } finally {
    restoring.value = false
  }
}

async function createZone() {
  const name = newZoneName.value.trim()
  if (!name) return
  await http.post(`/admin/stores/${props.storeId}/zones`, { name })
  newZoneName.value = ''
  ElMessage.success('区域已添加')
  await load()
}

async function removeZone(z: any) {
  await ElMessageBox.confirm(`删除区域「${z.name}」？有座位时无法删除。`, '删除区域', { type: 'warning' })
  await http.delete(`/admin/stores/${props.storeId}/zones/${z.id}`)
  ElMessage.success('已删除')
  await load()
}

onMounted(load)

defineExpose({ reload: load })
</script>

<style scoped>
.mb { margin-bottom: 12px; }
.toolbar { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 16px; }
.layout { display: grid; grid-template-columns: 1fr 300px; gap: 16px; }
@media (max-width: 960px) { .layout { grid-template-columns: 1fr; } }
.canvas-wrap { min-height: 320px; }
.canvas {
  position: relative;
  width: 100%;
  max-width: 900px;
  border: 1px dashed #dcdfe6;
  border-radius: 8px;
  overflow: hidden;
  background: #f5f7fa;
  user-select: none;
}
.floor-img { width: 100%; height: 100%; object-fit: contain; display: block; pointer-events: none; }
.marker {
  position: absolute;
  width: 32px;
  height: 32px;
  margin-left: -16px;
  margin-top: -16px;
  border-radius: 8px;
  background: #409eff;
  color: #fff;
  font-size: 11px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: grab;
  box-shadow: 0 2px 6px rgba(0,0,0,.15);
}
.marker.active { background: #67c23a; outline: 2px solid #fff; }
.side-card { margin-bottom: 12px; }
.row { display: flex; gap: 6px; margin-bottom: 8px; }
.zone-row, .marker-row { display: flex; justify-content: space-between; align-items: center; padding: 4px 0; }
.hint { font-size: 12px; color: #909399; margin: 0 0 8px; }
.muted { color: #909399; font-size: 12px; }
.pub-img { width: 100%; max-height: 120px; margin-bottom: 8px; }
.marker-list { margin-top: 10px; max-height: 220px; overflow: auto; }
</style>
