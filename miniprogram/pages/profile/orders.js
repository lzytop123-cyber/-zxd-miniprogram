const { request } = require('../../utils/request')

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
  return {
    ...item,
    timeRange: formatRange(item.start_time, item.end_time),
    statusLabel: item.status_label || '未知',
    statusHint: item.status_hint || '',
    statusTone: tone,
    canOpen,
  }
}

Page({
  data: { orders: [] },

  onShow() {
    request({ url: '/reservation/list' })
      .then((orders) => {
        this.setData({ orders: (orders || []).map(enrichOrder) })
      })
      .catch(() => this.setData({ orders: [] }))
  },

  goOpen(e) {
    const id = Number(e.currentTarget.dataset.id)
    if (id) {
      wx.setStorageSync('checkin_selected_id', id)
    }
    wx.switchTab({ url: '/pages/checkin/index' })
  },
})
