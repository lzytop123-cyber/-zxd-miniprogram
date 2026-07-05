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

function formatSeatNum(seatCode) {
  const display = seatDisplay({ seat_code: seatCode || '' })
  return display.mapLabel ? `${display.mapLabel}号` : (seatCode || '-')
}

function zoneTone(zoneName) {
  if (zoneName === '沉浸区') return 'immersion'
  if (zoneName === '工位区') return 'workspace'
  if (zoneName === '标准区') return 'standard'
  return 'default'
}

function sourceTone(paySourceLabel) {
  const s = paySourceLabel || ''
  if (s.includes('美团') || s.includes('点评')) return 'meituan'
  if (s.includes('抖音')) return 'douyin'
  if (s.includes('微信')) return 'wechat'
  if (s.includes('余额')) return 'balance'
  if (s.includes('期限') || s.includes('发放') || s.includes('赠送')) return 'card'
  if (s === '待支付') return 'pending'
  return 'default'
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
  const canPay = item.pay_status !== 1 && item.status === 0 && parseDate(item.end_time) > new Date()

  const display = seatDisplay({ seat_code: item.seat_code || '' })
  const zoneName = item.zone_name || display.zoneName || ''
  const seatNum = formatSeatNum(item.seat_code)
  const seatLine = zoneName ? `${seatNum} · ${zoneName}` : seatNum

  const usageLabel = item.usage_label || item.bill_type_label || item.bill_type || '预约'
  const paySourceLabel = item.pay_source_label || (item.pay_status !== 1 ? '待支付' : '—')
  const priceText =
    item.final_price != null && Number(item.final_price) > 0
      ? `¥${item.final_price}`
      : '期限卡抵扣'

  return {
    ...item,
    timeRange: formatRange(item.start_time, item.end_time),
    seatNum,
    zoneName,
    seatLine,
    zoneTone: zoneTone(zoneName),
    usageLabel,
    paySourceLabel,
    sourceTone: sourceTone(paySourceLabel),
    priceText,
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
