const { request } = require('../../utils/request')
const auth = require('../../utils/auth')
const { getLayout } = require('../../utils/seat-layout')
const { debounce } = require('../../utils/debounce')
const { dailyPassDays } = require('../../utils/cardDisplay')
const {
  formatLocalDateTime,
  todayStr,
  addDays,
  combineDateTime,
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
    selectedId: null,
    selectedLabel: '',
    selectedZone: '',
    seats: [],
    availableSeatCount: 0,
    planSeatCount: 27,
    preview: null,
    startTime: '',
    endTime: '',
    timeSummary: '',
    nightHint: '18:00 - 次日 00:00',
    pricingMap: {},
    seatsLoading: false,
    previewLoading: false,
    showSeatMap: false,
    userCards: [],
    hasMultiDayDailyCard: false,
    dailyUseMode: 'single',
    multiDayDailyCard: null,
  },

  onLoad(options) {
    const redirect = `/pages/booking/index?storeId=${options.storeId || ''}`
    if (!auth.isLoggedIn()) {
      auth.goLogin(redirect, { replace: true })
      return
    }

    if (!options.storeId) {
      wx.showToast({ title: '门店信息缺失', icon: 'none' })
      setTimeout(() => wx.navigateBack(), 1500)
      return
    }

    const today = todayStr()
    this._layout = getLayout()
    this._refreshPreviewDebounced = debounce(() => this._doRefreshPreview(), 450)
    wx.getImageInfo({ src: '/assets/floor-plan-clean.png' })

    this.setData({
      storeId: options.storeId,
      startDate: today,
      endDate: today,
      startClock: nowTimeStr(),
      endClock: this._addHoursToClock(nowTimeStr(), 2),
      planSeatCount: this._layout.planSeatCount,
      showSeatMap: true,
    }, () => {
      this.refreshPreview({ immediate: true })
    })

    request({ url: `/store/${options.storeId}`, silent: true }).then((s) => {
      this.setData({ storeName: s.name })
    })

    this._fetchPricing(options.storeId).then(() => {
      this.refreshPreview({ immediate: true })
    })
    this.loadUserCards()
  },

  onPullDownRefresh() {
    const { storeId } = this.data
    if (!storeId) {
      wx.stopPullDownRefresh()
      return
    }
    this._seatRange = null
    Promise.all([
      this.loadUserCards(),
      this._fetchPricing(storeId),
    ])
      .then(() => this._doRefreshPreview({ force: true }))
      .finally(() => wx.stopPullDownRefresh())
  },

  _fetchPricing(storeId) {
    return request({ url: `/store/${storeId}/pricing`, silent: true })
      .then((rules) => {
        this.setData(this._buildPricingPatch(rules))
      })
      .catch(() => {})
  },

  _buildPricingPatch(rules) {
    const pricingMap = {}
    ;(rules || []).forEach((r) => {
      pricingMap[r.bill_type] = r
    })
    const night = pricingMap.night
    if (night && night.night_start) {
      const start = String(night.night_start).slice(0, 5)
      const end = night.night_end ? String(night.night_end).slice(0, 5) : '24:00'
      return {
        pricingMap,
        startClock: start,
        endClock: end === '00:00' ? '23:59' : end,
        nightHint: `${start} - ${end === '00:00' ? '次日 00:00' : end}`,
      }
    }
    return { pricingMap }
  },

  loadUserCards() {
    return request({ url: '/user/cards', silent: true })
      .then((cards) => {
        const list = cards || []
        this.setData({
          userCards: list,
          hasMultiDayDailyCard: !!this._findMultiDayDailyCard(list),
        })
      })
      .catch(() => {})
  },

  _findMultiDayDailyCard(cards) {
    return (cards || []).find((c) => c.card_type === 'daily' && dailyPassDays(c) > 1)
  },

  _hasSeatAvailability() {
    return (this.data.seats || []).some((s) => s.id)
  },

  setDailyMode(e) {
    const mode = e.currentTarget.dataset.mode
    if (mode === 'multi_pass') {
      const card = this._findMultiDayDailyCard(this.data.userCards)
      if (!card) return
      this.setData({
        dailyUseMode: 'multi_pass',
        multiDayDailyCard: card,
        startDate: card.start_date,
        endDate: card.end_date,
      }, () => this.refreshPreview())
      return
    }
    const { startDate } = this.data
    this.setData({
      dailyUseMode: 'single',
      multiDayDailyCard: null,
      endDate: startDate,
    }, () => this.refreshPreview())
  },

  switchType(e) {
    const billType = e.currentTarget.dataset.type
    const { startDate } = this.data
    const defaults = BILL_DEFAULTS[billType]
    const patch = { billType, seatId: null, seatCode: '', selectedId: null, selectedLabel: '', selectedZone: '', preview: null }

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
      Object.assign(patch, {
        endDate: startDate,
        dailyUseMode: 'single',
        multiDayDailyCard: null,
      })
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
      if (this.data.dailyUseMode === 'multi_pass' && this.data.multiDayDailyCard) {
        patch.startDate = this.data.multiDayDailyCard.start_date
        patch.endDate = this.data.multiDayDailyCard.end_date
      } else {
        patch.endDate = startDate
      }
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
    if (this.data.billType === 'daily' && this.data.dailyUseMode === 'multi_pass') return
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
      const multi = this.data.dailyUseMode === 'multi_pass' ? this.data.multiDayDailyCard : null
      if (multi) {
        const span = dailyPassDays(multi)
        const days = Math.floor((end - start) / 86400000) + 1
        if (startDate !== multi.start_date || endDate !== multi.end_date || days !== span) {
          throw new Error(`该卡须连续预约 ${multi.start_date} 至 ${multi.end_date}`)
        }
      }
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

  refreshPreview(options = {}) {
    if (options.immediate || options.force) {
      return this._doRefreshPreview(options)
    }
    this._refreshPreviewDebounced()
    return Promise.resolve()
  },

  _doRefreshPreview(options = {}) {
    const { storeId, billType, seatId } = this.data
    if (!storeId) return Promise.resolve()
    let start
    let end
    try {
      const times = this._calcTimes()
      start = times.start
      end = times.end
    } catch (err) {
      this.setData({
        preview: null,
        timeSummary: '',
        startTime: '',
        endTime: '',
        previewLoading: false,
        showSeatMap: false,
      })
      return Promise.resolve()
    }

    this.setData({
      startTime: start,
      endTime: end,
      timeSummary: this._formatSummary(start, end),
      previewLoading: true,
      showSeatMap: true,
    })

    const seatPromise = this.loadSeats(start, end, options)
    const body = {
      store_id: Number(storeId),
      bill_type: billType,
      start_time: start,
      end_time: end,
    }
    if (seatId) body.seat_id = seatId

    const previewPromise = request({ url: '/reservation/preview', method: 'POST', data: body, silent: true })
      .then((preview) => {
        const patch = { preview, previewLoading: false }
        if (this.data.seatId && preview.seat_id === this.data.seatId) {
          patch.seatCode = preview.seat_code
        }
        this.setData(patch)
      })
      .catch(() => this.setData({ preview: null, previewLoading: false }))

    return Promise.all([seatPromise, previewPromise])
  },

  loadSeats(start, end, options = {}) {
    const { force = false } = options
    const { storeId } = this.data
    if (!storeId) return Promise.resolve()

    const range = `${start}~${end}`
    if (!force && range === this._seatRange && this._hasSeatAvailability()) {
      return Promise.resolve()
    }
    this._seatRange = range

    const showLoadingOverlay = force || !this._hasSeatAvailability()
    if (showLoadingOverlay) {
      this.setData({ seatsLoading: true })
    }

    return request({
      url: `/store/${storeId}/availability?start_time=${encodeURIComponent(start)}&end_time=${encodeURIComponent(end)}`,
      silent: true,
    })
      .then((seats) => {
        const applied = this._layout.applySeats(seats)
        const availableSeatCount = applied.filter((s) => s.status === 'available').length
        const patch = { seats: applied, availableSeatCount, seatsLoading: false }
        if (this.data.seatId) {
          const current = applied.find((s) => s.id === this.data.seatId)
          if (!current || current.status !== 'available') {
            Object.assign(patch, {
              seatId: null,
              seatCode: '',
              selectedId: null,
              selectedLabel: '',
              selectedZone: '',
            })
          }
        }
        this.setData(patch)
      })
      .catch(() => this.setData({ seatsLoading: false }))
  },

  selectSeat(e) {
    const { id, code, status } = e.detail
    if (this.data.seatsLoading) {
      wx.showToast({ title: '座位状态更新中', icon: 'none' })
      return
    }
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
      seatId: Number(id),
      seatCode: code,
      selectedId: Number(id),
      selectedLabel: display.mapLabel,
      selectedZone: display.zoneName,
    }, () => this.refreshPreview())
  },

  goOrder() {
    const { storeId, preview, billType, seatId } = this.data
    if (!auth.isLoggedIn()) {
      const redirect = `/pages/booking/index?storeId=${storeId}`
      auth.requireLogin(redirect)
      return
    }
    if (!seatId) {
      wx.showToast({ title: '请先点击平面图选座', icon: 'none' })
      return
    }
    if (!preview) {
      wx.showToast({ title: '请检查时间并等待价格计算', icon: 'none' })
      return
    }
    if (preview.seat_id !== seatId) {
      wx.showToast({ title: '座位信息同步中，请稍候', icon: 'none' })
      this.refreshPreview({ immediate: true })
      return
    }
    wx.navigateTo({
      url: `/pages/booking/order?storeId=${storeId}&start=${encodeURIComponent(preview.start_time)}&end=${encodeURIComponent(preview.end_time)}&seatId=${preview.seat_id}&price=${preview.final_price}&seatCode=${preview.seat_code}&billType=${billType}`,
    })
  },
})
