const { request } = require('../../../utils/request')
const routes = require('../../../utils/routes')
const { seatDisplay } = require('../../../utils/seat-layout')

function parseDate(iso) {
  return new Date(String(iso).replace(' ', 'T'))
}

function formatRange(start, end) {
  const s = parseDate(start)
  const e = parseDate(end)
  const pad = (n) => (n < 10 ? '0' + n : '' + n)
  const fmtDate = (d) => `${d.getMonth() + 1}月${d.getDate()}日`
  const fmtTime = (d) => `${pad(d.getHours())}:${pad(d.getMinutes())}`
  if (fmtDate(s) === fmtDate(e)) {
    return `${fmtDate(s)} ${fmtTime(s)} - ${fmtTime(e)}`
  }
  return `${fmtDate(s)} ${fmtTime(s)} ~ ${fmtDate(e)} ${fmtTime(e)}`
}

function formatSeat(item) {
  const display = seatDisplay({ seat_code: item.seat_code || '' })
  if (!display.mapLabel) return item.seat_code || '-'
  return display.zoneName ? `${display.mapLabel}号 · ${display.zoneName}` : `${display.mapLabel}号`
}

function enrichOrder(item) {
  const tone =
    item.status === 1
      ? 'active'
      : item.status === 3
        ? 'muted'
        : item.status === 2
          ? 'done'
          : item.pay_status !== 1
            ? 'warn'
            : 'booked'
  const canOpen =
    item.pay_status === 1 && [0, 1].includes(item.status) && parseDate(item.end_time) > new Date()
  // 待支付且未取消：可去支付 / 取消
  const canPay = item.pay_status !== 1 && item.status === 0 && parseDate(item.end_time) > new Date()
  return {
    ...item,
    timeRange: formatRange(item.start_time, item.end_time),
    seatDisplay: formatSeat(item),
    statusLabel: item.status_label || '未知',
    statusHint: item.status_hint || '',
    statusTone: tone,
    canOpen,
    canPay,
  }
}

Page({
  data: { orders: [] },

  onShow() {
    this.loadOrders({ silent: true })
  },

  onPullDownRefresh() {
    this.loadOrders({ force: true }).finally(() => wx.stopPullDownRefresh())
  },

  loadOrders(options = {}) {
    const { force = false } = options
    return request({ url: '/reservation/list', silent: true, force })
      .then((orders) => {
        this.setData({ orders: (orders || []).map(enrichOrder) })
      })
      .catch(() => {
        if (!this.data.orders.length) {
          this.setData({ orders: [] })
        }
      })
  },

  goOpen(e) {
    const id = Number(e.currentTarget.dataset.id)
    if (id) {
      wx.setStorageSync('checkin_selected_id', id)
    }
    wx.switchTab({ url: '/pages/checkin/index' })
  },

  goPay(e) {
    const id = Number(e.currentTarget.dataset.id)
    const o = this.data.orders.find((x) => x.id === id)
    if (!o) return
    const url =
      `${routes.bookingOrder}?storeId=${o.store_id}` +
      `&start=${encodeURIComponent(o.start_time)}&end=${encodeURIComponent(o.end_time)}` +
      `&seatId=${o.seat_id}&price=${o.final_price}` +
      `&seatCode=${encodeURIComponent(o.seat_code || '')}&billType=${o.bill_type}`
    wx.navigateTo({ url })
  },

  cancelOrder(e) {
    const id = Number(e.currentTarget.dataset.id)
    if (!id) return
    wx.showModal({
      title: '取消预约',
      content: '确定取消该待支付订单吗？',
      confirmColor: '#52B788',
      success: (res) => {
        if (!res.confirm) return
        request({ url: `/reservation/${id}/cancel`, method: 'POST' })
          .then(() => {
            wx.showToast({ title: '已取消', icon: 'success' })
            this.loadOrders({ force: true })
          })
          .catch(() => {})
      },
    })
  },
})
