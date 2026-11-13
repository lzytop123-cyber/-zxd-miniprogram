const { request, invalidateCache } = require('../../../utils/request')
const { getLayout } = require('../../../utils/seat-layout')
const { seatDisplayImage } = require('../../../utils/seat-map-image')
const { resolveStaticUrl } = require('../../../config')

function mapOptionToSeat(opt) {
  let status = 'reserved'
  if (opt.selectable) {
    status = 'available'
  } else if (opt.reason === '当前座位') {
    status = 'occupied'
  }
  return {
    id: opt.id,
    seat_code: opt.seat_code,
    status,
    zone_name: opt.zone_name,
    _reason: opt.reason,
  }
}

Page({
  data: {
    reservationId: null,
    currentSeatCode: '',
    orderNo: '',
    seats: [],
    selectedId: null,
    selectedCode: '',
    selectedLabel: '',
    selectedZone: '',
    planSeatCount: 27,
    availableSeatCount: 0,
    pageLoading: true,
    submitting: false,
    seatMapMode: 'legacy',
    seatMapImage: '',
    seatMapMarkers: [],
    seatMapAspect: 1.4,
    seatMapReady: true,
    seatMapError: '',
  },

  onLoad(options) {
    const reservationId = Number(options.id)
    if (!reservationId) {
      wx.showToast({ title: '订单无效', icon: 'none' })
      setTimeout(() => wx.navigateBack(), 1500)
      return
    }
    this._layout = getLayout()
    this.setData({ reservationId, planSeatCount: this._layout.planSeatCount })
    this.loadOptions()
  },

  _loadSeatMap(storeId) {
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
            seatMapError: published ? '' : '本店座位图尚未发布',
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

  loadOptions() {
    const { reservationId } = this.data
    this.setData({ pageLoading: true })
    return request({ url: `/reservation/${reservationId}/seat-options`, silent: true })
      .then(async (data) => {
        if (data.store_id) {
          await this._loadSeatMap(data.store_id)
        }
        const seats = (data.seats || []).map(mapOptionToSeat)
        const imageMode = this.data.seatMapMode === 'image'
        const applied = imageMode
          ? seats.map((seat) => ({ ...seat, map_label: seat.seat_code, map_slot: seat.id }))
          : this._layout.applySeats(seats).map((seat) => {
            if (seat._reason === '当前座位') {
              return { ...seat, status: 'occupied' }
            }
            if (seat._reason === '时段冲突') {
              return { ...seat, status: 'reserved' }
            }
            return seat
          })
        this.setData({
          currentSeatCode: data.current_seat_code || '',
          orderNo: data.order_no || '',
          seats: applied,
          availableSeatCount: applied.filter((s) => s.status === 'available').length,
          pageLoading: false,
        })
      })
      .catch(() => {
        this.setData({ pageLoading: false })
        setTimeout(() => wx.navigateBack(), 1500)
      })
  },

  selectSeat(e) {
    const { id, code, status } = e.detail
    if (!id || status === 'empty') {
      wx.showToast({ title: '该座位暂未开放', icon: 'none' })
      return
    }
    if (status !== 'available') {
      const seat = this.data.seats.find((s) => s.id === Number(id))
      const reason = seat && seat._reason
      wx.showToast({ title: reason || '该座位不可选', icon: 'none' })
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
    const {
      reservationId, selectedId, selectedLabel, currentSeatCode, submitting,
    } = this.data
    if (!selectedId || submitting) return

    wx.showModal({
      title: '确认换座',
      content: `确定从 ${currentSeatCode} 换到 ${selectedLabel}号 吗？`,
      confirmColor: '#52B788',
      success: (res) => {
        if (!res.confirm) return
        this.submitChange(reservationId, selectedId)
      },
    })
  },

  submitChange(reservationId, seatId) {
    this.setData({ submitting: true })
    request({
      url: `/reservation/${reservationId}/change-seat`,
      method: 'POST',
      data: { seat_id: seatId },
    })
      .then(() => {
        invalidateCache('/reservation/list')
        invalidateCache('/reservation/active/list')
        wx.showToast({ title: '换座成功', icon: 'success' })
        setTimeout(() => wx.navigateBack(), 1500)
      })
      .catch(() => {
        this.setData({ submitting: false })
      })
  },
})
