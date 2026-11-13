const { buildSeatMarkers } = require('../../utils/seat-layout')
const { buildImageMarkers } = require('../../utils/seat-map-image')
const { isLigongdaFloor, lines, labels } = require('../../utils/ligongda-floor')

const SCALE_MIN = 1
const SCALE_MAX = 4
const SCALE_STEP = 0.6

Component({
  properties: {
    seats: { type: Array, value: [] },
    selectedId: { type: Number, value: null },
    mode: { type: String, value: 'legacy' },
    imageUrl: { type: String, value: '' },
    aspectRatio: { type: Number, value: 1.4 },
    mapMarkers: { type: Array, value: [] },
  },
  data: {
    markers: [],
    scale: 1,
    scaleValue: 1,
    floorStyle: '',
    drawnFloor: false,
    lines,
    labels,
  },
  observers: {
    'mode, seats, mapMarkers, imageUrl, aspectRatio'() {
      this.refreshMarkers()
    },
  },
  lifetimes: {
    attached() {
      this.refreshMarkers()
    },
    ready() {
      this.fitImageFloor()
    },
  },
  pageLifetimes: {
    show() {
      this.fitImageFloor()
    },
    resize() {
      this.fitImageFloor()
    },
  },
  methods: {
    refreshMarkers() {
      const mode = this.data.mode || 'legacy'
      if (mode === 'image') {
        const markers = buildImageMarkers(this.data.mapMarkers || [], this.data.seats || [])
        this.setData({ markers, drawnFloor: isLigongdaFloor(this.data.imageUrl) }, () => this.fitImageFloor())
        return
      }
      this.setData({
        markers: buildSeatMarkers(this.data.seats || []),
        floorStyle: '',
        drawnFloor: false,
      })
    },

    fitImageFloor() {
      if (this.data.mode !== 'image') return
      this.createSelectorQuery().select('.plan-area').boundingClientRect((area) => {
        if (!area || !area.width || !area.height || this.data.mode !== 'image') return
        const ratio = this.data.aspectRatio > 0 ? this.data.aspectRatio : 1.4
        const height = this.data.drawnFloor ? area.height : Math.min(area.height, area.width / ratio)
        const width = this.data.drawnFloor ? area.width : height * ratio
        const floorStyle = `width:${width}px;height:${height}px;left:${(area.width - width) / 2}px;top:${(area.height - height) / 2}px;`
        if (floorStyle !== this.data.floorStyle) this.setData({ floorStyle })
      }).exec()
    },

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

  },
})
