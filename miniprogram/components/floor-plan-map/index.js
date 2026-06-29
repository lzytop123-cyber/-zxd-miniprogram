import { buildSeatMarkers } from '../../utils/seat-layout'

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
