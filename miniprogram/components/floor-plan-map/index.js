const { buildSeatMarkers } = require('../../utils/seat-layout')
const { FLOOR_PLAN } = require('../../utils/assets')

const SCALE_MIN = 1
const SCALE_MAX = 4
const SCALE_STEP = 0.6

Component({
  properties: {
    seats: { type: Array, value: [] },
    selectedId: { type: Number, value: null },
  },
  data: {
    markers: [],
    scale: 1,
    scaleValue: 1,
    floorPlanSrc: FLOOR_PLAN,
  },
  observers: {
    seats(seats) {
      this.setData({ markers: buildSeatMarkers(seats) })
    },
  },
  methods: {
    onTap(e) {
      const { id, code, status } = e.currentTarget.dataset
      if (!id || status === 'empty') return
      this.triggerEvent('select', { id, code, status })
    },

    onScale(e) {
      this.data.scale = e.detail.scale
    },

    applyScale(next) {
      const scale = Math.min(SCALE_MAX, Math.max(SCALE_MIN, next))
      this.data.scale = scale
      // 手势缩放后 scale-value 不会同步，叠加极小抖动确保按钮每次都触发更新
      this._jitter = this._jitter ? 0 : 0.0002
      this.setData({ scaleValue: scale + this._jitter })
    },

    zoomIn() {
      this.applyScale((this.data.scale || 1) + SCALE_STEP)
    },

    zoomOut() {
      this.applyScale((this.data.scale || 1) - SCALE_STEP)
    },

    zoomReset() {
      this.applyScale(1)
    },
  },
})
