const { request } = require('../../utils/request')

Page({
  data: {
    storeId: null,
    seats: [],
    selectedId: null,
    selectedCode: '',
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
    this.loadSeats()
  },

  loadSeats() {
    const { storeId, startTime, endTime } = this.data
    const url = startTime && endTime
      ? `/store/${storeId}/availability?start_time=${encodeURIComponent(startTime)}&end_time=${encodeURIComponent(endTime)}`
      : `/store/${storeId}/seats`
    request({ url }).then((seats) => {
      this.setData({ seats })
    })
  },

  selectSeat(e) {
    const { id, code, status } = e.currentTarget.dataset
    if (status !== 'available') {
      wx.showToast({ title: '该座位不可选', icon: 'none' })
      return
    }
    this.setData({ selectedId: Number(id), selectedCode: code })
  },

  confirm() {
    const { selectedId, selectedCode, storeId, startTime, endTime, billType } = this.data
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
