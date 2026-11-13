const { request } = require('../../utils/request')
const { getLayout } = require('../../utils/seat-layout')
const { seatDisplayImage } = require('../../utils/seat-map-image')
const { resolveStaticUrl } = require('../../config')

Page({
  data: {
    storeId: null,
    seats: [],
    selectedId: null,
    selectedCode: '',
    selectedLabel: '',
    selectedZone: '',
    startTime: '',
    endTime: '',
    billType: 'hourly',
    planSeatCount: 27,
    availableSeatCount: 0,
    seatMapMode: 'legacy',
    seatMapImage: '',
    seatMapMarkers: [],
    seatMapAspect: 1.4,
    seatMapReady: true,
    seatMapError: '',
  },

  onLoad(options) {
    this.setData({
      storeId: options.storeId,
      startTime: decodeURIComponent(options.start || ''),
      endTime: decodeURIComponent(options.end || ''),
      billType: options.billType || 'hourly',
      seats: [],
      seatMapReady: false,
    })
    this._layout = getLayout()
    this.setData({ planSeatCount: this._layout.planSeatCount })
    this._loadSeatMap().then(() => this.loadSeats())
  },

  _loadSeatMap() {
    const { storeId } = this.data
    return request({ url: `/store/${storeId}/seat-map`, silent: true, force: true })
      .then((data) => {
        const mode = (data && data.mode) || 'legacy'
        if (mode === 'image') {
          const published = !!(data && data.published && data.image_url && (data.markers || []).length)
          this.setData({
            seatMapMode: 'image',
            seatMapImage: published ? resolveStaticUrl(data.image_url) : '',
            seatMapMarkers: published ? (data.markers || []) : [],
            seatMapAspect: Number(data.aspect_ratio) || 1.4,
            seatMapReady: published,
            planSeatCount: published ? (data.markers || []).length : 0,
            seatMapError: published ? '' : '本店座位图尚未发布，暂不可选座',
          })
        } else {
          this.setData({
            seatMapMode: 'legacy',
            seatMapReady: true,
            planSeatCount: this._layout.planSeatCount,
            seatMapError: '',
          })
        }
      })
      .catch(() => {
        this.setData({ seatMapMode: 'legacy', seatMapReady: true })
      })
  },

  loadSeats() {
    const { storeId, startTime, endTime, seatMapMode, seatMapReady } = this.data
    if (seatMapMode === 'image' && !seatMapReady) {
      this.setData({ seats: [], availableSeatCount: 0 })
      return
    }
    const url = startTime && endTime
      ? `/store/${storeId}/availability?start_time=${encodeURIComponent(startTime)}&end_time=${encodeURIComponent(endTime)}`
      : `/store/${storeId}/seats`
    request({ url }).then((seats) => {
      const applied = seatMapMode === 'image'
        ? (seats || []).map((s) => ({ ...s, map_label: s.seat_code, map_slot: s.id }))
        : this._layout.applySeats(seats)
      this.setData({
        seats: applied,
        availableSeatCount: applied.filter((s) => s.status === 'available').length,
      })
    })
  },

  selectSeat(e) {
    const { id, code, status } = e.detail
    if (!id || status === 'empty') {
      wx.showToast({ title: '该座位暂未开放', icon: 'none' })
      return
    }
    if (status !== 'available') {
      wx.showToast({ title: '该座位不可选', icon: 'none' })
      return
    }
    const seat = this.data.seats.find((s) => s.id === Number(id))
    const display = this.data.seatMapMode === 'image'
      ? seatDisplayImage(seat, this.data.seatMapMarkers)
      : this._layout.seatDisplay(seat)
    this.setData({
      selectedId: Number(id),
      selectedCode: code,
      selectedLabel: display.mapLabel,
      selectedZone: display.zoneName,
    })
  },

  confirm() {
    const { selectedId, selectedCode, selectedLabel, selectedZone } = this.data
    if (!selectedId) {
      wx.showToast({ title: '请先选择座位', icon: 'none' })
      return
    }
    const pages = getCurrentPages()
    const prev = pages[pages.length - 2]
    if (prev) {
      prev.setData({
        seatId: selectedId,
        seatCode: selectedCode,
        selectedId,
        selectedLabel,
        selectedZone,
      })
      prev.refreshPreview && prev.refreshPreview()
    }
    wx.navigateBack()
  },
})
