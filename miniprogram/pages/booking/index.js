const { request } = require('../../utils/request')
const {
  formatLocalDateTime,
  todayStr,
  addDays,
  combineDateTime,
  roundUp15min,
  nowTimeStr,
  pad,
} = require('../../utils/datetime')

const BILL_DEFAULTS = {
  hourly: { startClock: '09:00', endClock: '11:00', hours: 2 },
  daily: { endOffset: 0 },
  weekly: { endOffset: 6 },
  quarterly: { endOffset: 89 },
  monthly: { endOffset: 29 },
  session: { endOffset: 0 },
  night: { startClock: '18:00', endClock: '23:59' },
}

Page({
  data: {
    storeId: null,
    storeName: '',
    billType: 'hourly',
    billTypes: [
      { type: 'hourly', label: '按小时' },
      { type: 'daily', label: '天卡' },
      { type: 'weekly', label: '周卡' },
      { type: 'session', label: '次卡' },
      { type: 'monthly', label: '月卡' },
      { type: 'quarterly', label: '季卡' },
      { type: 'night', label: '夜读' },
    ],
    today: todayStr(),
    startDate: '',
    endDate: '',
    startClock: '09:00',
    endClock: '11:00',
    hours: 2,
    seatId: null,
    seatCode: '',
    preview: null,
    startTime: '',
    endTime: '',
    timeSummary: '',
    nightHint: '18:00 - 次日 00:00',
    pricingMap: {},
  },

  onLoad(options) {
    const today = todayStr()
    this.setData({
      storeId: options.storeId,
      startDate: today,
      endDate: today,
      startClock: nowTimeStr(),
      endClock: this._addHoursToClock(nowTimeStr(), 2),
    })
    request({ url: `/store/${options.storeId}` }).then((s) => {
      this.setData({ storeName: s.name })
    })
    request({ url: `/store/${options.storeId}/pricing` }).then((rules) => {
      const pricingMap = {}
      rules.forEach((r) => {
        pricingMap[r.bill_type] = r
      })
      const night = pricingMap.night
      if (night && night.night_start) {
        const start = String(night.night_start).slice(0, 5)
        const end = night.night_end ? String(night.night_end).slice(0, 5) : '24:00'
        this.setData({
          pricingMap,
          startClock: start,
          endClock: end === '00:00' ? '23:59' : end,
          nightHint: `${start} - ${end === '00:00' ? '次日 00:00' : end}`,
        })
      } else {
        this.setData({ pricingMap })
      }
      this.refreshPreview()
    }).catch(() => this.refreshPreview())
  },

  switchType(e) {
    const billType = e.currentTarget.dataset.type
    const { startDate } = this.data
    const defaults = BILL_DEFAULTS[billType]
    const patch = { billType, seatId: null, seatCode: '', preview: null }

    if (billType === 'hourly') {
      const startClock = startDate === todayStr() ? nowTimeStr() : '09:00'
      Object.assign(patch, {
        startClock,
        endClock: this._addHoursToClock(startClock, defaults.hours),
        hours: defaults.hours,
      })
    } else if (billType === 'session') {
      Object.assign(patch, { endDate: startDate })
    } else if (billType === 'daily') {
      Object.assign(patch, { endDate: startDate })
    } else if (billType === 'weekly') {
      Object.assign(patch, { endDate: addDays(startDate, defaults.endOffset) })
    } else if (billType === 'monthly') {
      Object.assign(patch, { endDate: addDays(startDate, defaults.endOffset) })
    } else if (billType === 'quarterly') {
      Object.assign(patch, { endDate: addDays(startDate, defaults.endOffset) })
    } else if (billType === 'night') {
      const night = this.data.pricingMap.night
      const startClock = night?.night_start ? String(night.night_start).slice(0, 5) : defaults.startClock
      let endClock = night?.night_end ? String(night.night_end).slice(0, 5) : defaults.endClock
      if (endClock === '00:00') endClock = '23:59'
      Object.assign(patch, { startClock, endClock })
    }

    this.setData(patch, () => this.refreshPreview())
  },

  onStartDateChange(e) {
    const startDate = e.detail.value
    const patch = { startDate }
    if (this.data.billType === 'daily') {
      patch.endDate = startDate
    } else if (this.data.billType === 'session') {
      patch.endDate = startDate
    } else if (this.data.billType === 'weekly') {
      patch.endDate = addDays(startDate, 6)
    } else if (this.data.billType === 'monthly') {
      patch.endDate = addDays(startDate, 29)
    } else if (this.data.billType === 'quarterly') {
      patch.endDate = addDays(startDate, 89)
    }
    if (this.data.billType === 'hourly' && startDate === todayStr()) {
      patch.startClock = nowTimeStr()
      patch.endClock = this._addHoursToClock(patch.startClock, this.data.hours)
    }
    this.setData(patch, () => this.refreshPreview())
  },

  onEndDateChange(e) {
    this.setData({ endDate: e.detail.value }, () => this.refreshPreview())
  },

  onStartClockChange(e) {
    const startClock = e.detail.value
    const patch = { startClock }
    if (this.data.billType === 'hourly') {
      patch.endClock = this._addHoursToClock(startClock, this.data.hours)
    }
    this.setData(patch, () => this.refreshPreview())
  },

  onEndClockChange(e) {
    this.setData({ endClock: e.detail.value }, () => this.refreshPreview())
  },

  setHours(e) {
    const hours = Number(e.currentTarget.dataset.h)
    this.setData({
      hours,
      endClock: this._addHoursToClock(this.data.startClock, hours),
    }, () => this.refreshPreview())
  },

  setSessionDays(e) {
    const days = Number(e.currentTarget.dataset.d)
    this.setData({
      endDate: addDays(this.data.startDate, days - 1),
    }, () => this.refreshPreview())
  },

  _addHoursToClock(clock, hours) {
    const [h, m] = clock.split(':').map(Number)
    const d = new Date()
    d.setHours(h, m, 0, 0)
    d.setTime(d.getTime() + hours * 3600000)
    return `${pad(d.getHours())}:${pad(d.getMinutes())}`
  },

  _clockToDate(dateStr, clock) {
    return new Date(combineDateTime(dateStr, clock))
  },

  _calcTimes() {
    const { billType, startDate, endDate, startClock, endClock } = this.data
    let start
    let end

    if (billType === 'hourly') {
      start = this._clockToDate(startDate, startClock)
      end = this._clockToDate(startDate, endClock)
      if (end <= start) {
        end.setDate(end.getDate() + 1)
      }
      const diffH = (end - start) / 3600000
      if (diffH < 2) throw new Error('按小时预约最少2小时')
      if (diffH > 24) throw new Error('按小时预约最长24小时')
    } else if (billType === 'session') {
      start = new Date(`${startDate}T00:00:00`)
      end = new Date(`${endDate}T23:59:59`)
      if (end < start) throw new Error('结束日期不能早于开始日期')
      const days = Math.floor((end - start) / 86400000) + 1
      if (days > 30) throw new Error('次卡单次最多连续预约30天')
    } else if (billType === 'daily') {
      start = new Date(`${startDate}T00:00:00`)
      end = new Date(`${endDate}T23:59:59`)
      if (end < start) throw new Error('结束日期不能早于开始日期')
    } else if (billType === 'weekly') {
      start = new Date(`${startDate}T00:00:00`)
      end = new Date(`${endDate}T23:59:59`)
      if (end <= start) throw new Error('结束日期须晚于开始日期')
    } else if (billType === 'monthly') {
      start = new Date(`${startDate}T00:00:00`)
      end = new Date(`${endDate}T23:59:59`)
      if (end <= start) throw new Error('结束日期须晚于开始日期')
    } else if (billType === 'quarterly') {
      start = new Date(`${startDate}T00:00:00`)
      end = new Date(`${endDate}T23:59:59`)
      if (end <= start) throw new Error('结束日期须晚于开始日期')
    } else if (billType === 'night') {
      start = this._clockToDate(startDate, startClock)
      end = this._clockToDate(startDate, endClock)
      if (end <= start) {
        end.setDate(end.getDate() + 1)
      }
    }

    return {
      start: formatLocalDateTime(start),
      end: formatLocalDateTime(end),
    }
  },

  _formatSummary(start, end) {
    const fmt = (s) => {
      const d = new Date(s.replace(' ', 'T'))
      const w = ['日', '一', '二', '三', '四', '五', '六'][d.getDay()]
      return `${s.slice(0, 10)} 周${w} ${s.slice(11, 16)}`
    }
    return `${fmt(start)}  →  ${fmt(end)}`
  },

  refreshPreview() {
    const { storeId, billType, seatId } = this.data
    if (!storeId) return
    let start
    let end
    try {
      const times = this._calcTimes()
      start = times.start
      end = times.end
    } catch (err) {
      this.setData({ preview: null, timeSummary: '', startTime: '', endTime: '' })
      return
    }

    this.setData({
      startTime: start,
      endTime: end,
      timeSummary: this._formatSummary(start, end),
    })

    const body = {
      store_id: Number(storeId),
      bill_type: billType,
      start_time: start,
      end_time: end,
    }
    if (seatId) body.seat_id = seatId

    request({ url: '/reservation/preview', method: 'POST', data: body })
      .then((preview) => this.setData({ preview, seatCode: preview.seat_code }))
      .catch(() => this.setData({ preview: null }))
  },

  goSeats() {
    const { storeId, startTime, endTime, billType } = this.data
    if (!startTime || !endTime) {
      wx.showToast({ title: '请先选择有效时间', icon: 'none' })
      return
    }
    wx.navigateTo({
      url: `/pages/store/seats?storeId=${storeId}&start=${encodeURIComponent(startTime)}&end=${encodeURIComponent(endTime)}&billType=${billType}`,
    })
  },

  goOrder() {
    const { storeId, preview, billType } = this.data
    if (!preview) {
      wx.showToast({ title: '请检查时间并等待价格计算', icon: 'none' })
      return
    }
    wx.navigateTo({
      url: `/pages/booking/order?storeId=${storeId}&start=${encodeURIComponent(preview.start_time)}&end=${encodeURIComponent(preview.end_time)}&seatId=${preview.seat_id}&price=${preview.final_price}&seatCode=${preview.seat_code}&billType=${billType}`,
    })
  },
})
