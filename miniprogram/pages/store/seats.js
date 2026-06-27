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
    planSeatCount: 27,
    availableSeatCount: 0,
  },

  onLoad(options) {
    this.setData({
      storeId: options.storeId,
      startTime: decodeURIComponent(options.start || ''),
      endTime: decodeURIComponent(options.end || ''),
      billType: options.billType || 'hourly',
    })
    this._layout = getLayout()
    this.setData({ planSeatCount: this._layout.planSeatCount })
    this.loadSeats()
  },

  loadSeats() {
    const { storeId, startTime, endTime } = this.data
    const url = startTime && endTime
      ? `/store/${storeId}/availability?start_time=${encodeURIComponent(startTime)}&end_time=${encodeURIComponent(endTime)}`
      : `/store/${storeId}/seats`
    request({ url }).then((seats) => {
      const applied = this._layout.applySeats(seats)
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
    const display = this._layout.seatDisplay(seat)
    this.setData({
      selectedId: Number(id),
      selectedCode: code,
      selectedLabel: display.mapLabel,
      selectedZone: display.zoneName,
    })
  },

  zoneName(seatCode) {
    return this._layout.seatDisplay({ seat_code: seatCode }).zoneName
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
