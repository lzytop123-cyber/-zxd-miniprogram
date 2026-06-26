const { request } = require('../../utils/request')
const { getLayout } = require('../../utils/seat-layout')

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
  },

  onLoad(options) {
    this.setData({
      storeId: options.storeId,
      startTime: decodeURIComponent(options.start || ''),
      endTime: decodeURIComponent(options.end || ''),
      billType: options.billType || 'hourly',
    })
    this._layout = getLayout()
    this.loadSeats()
  },

  loadSeats() {
    const { storeId, startTime, endTime } = this.data
    const url = startTime && endTime
      ? `/store/${storeId}/availability?start_time=${encodeURIComponent(startTime)}&end_time=${encodeURIComponent(endTime)}`
      : `/store/${storeId}/seats`
    request({ url }).then((seats) => {
      this.setData({ seats: this._layout.applySeats(seats) })
    })
  },

  selectSeat(e) {
    const { id, code, status } = e.detail
    if (status !== 'available') {
      wx.showToast({ title: '该座位不可选', icon: 'none' })
      return
    }
    const seat = this.data.seats.find((s) => s.id === Number(id))
    this.setData({
      selectedId: Number(id),
      selectedCode: code,
      selectedLabel: seat?.map_label || code,
      selectedZone: this.zoneName(seat?.seat_code),
    })
  },

  zoneName(seatCode) {
    if (!seatCode) return ''
    const prefix = String(seatCode).charAt(0).toUpperCase()
    if (prefix === 'A') return '标准区'
    if (prefix === 'B') return '沉浸区'
    if (prefix === 'C') return '入口区'
    return ''
  },

  confirm() {
    const { selectedId, selectedCode } = this.data
    if (!selectedId) {
      wx.showToast({ title: '请先选择座位', icon: 'none' })
      return
    }
    const pages = getCurrentPages()
    const prev = pages[pages.length - 2]
    if (prev) {
      prev.setData({ seatId: selectedId, seatCode: selectedCode })
      prev.refreshPreview && prev.refreshPreview()
    }
    wx.navigateBack()
  },
})
