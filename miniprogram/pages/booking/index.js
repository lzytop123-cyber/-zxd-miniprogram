const { request, formatRequestError } = require('../../utils/request')
const auth = require('../../utils/auth')
const routes = require('../../utils/routes')
const { getLayout } = require('../../utils/seat-layout')
const { debounce } = require('./utils/debounce')
const {
  dailyPassDays,
  isOfficeNightMonthlyCard,
  isCardUsable,
  cardValidUntil,
  officeNightPassDays,
  monthlyPassDays,
  weeklyPassDays,
  quarterlyPassDays,
  periodPassSpan,
  formatPassDurationLabel,
  formatCard,
  cardValidityHint,
  OFFICE_NIGHT_USAGE_RULE,
  OFFICE_NIGHT_BOOKING_HINT,
} = require('../../utils/cardDisplay')
const {
  STORE_HOURS_LABEL,
  defaultHourlyStartClock,
  validateStoreTimeRange,
  clampHourlyClocks,
  STORE_OPEN,
  compareClock,
  storeRangeDateTimes,
  nightRangeDateTimes,
  clockRangeDateTimes,
  defaultDailyClocks,
} = require('../../utils/storeHours')
const {
  formatLocalDateTime,
  todayStr,
  addDays,
  combineDateTime,
  nowTimeStr,
  pad,
} = require('./utils/datetime')

const BILL_DEFAULTS = {
  hourly: { startClock: '07:30', endClock: '09:30', hours: 2 },
  daily: { endOffset: 0 },
  weekly: { endOffset: 6 },
  quarterly: { endOffset: 89 },
  monthly: { endOffset: 29 },
  session: { endOffset: 0 },
  night: { endOffset: 29 },
}

const QUICK_HOURS = [2, 4, 8]

function wholeHoursBetween(startClock, endClock) {
  const [sh, sm] = String(startClock).split(':').map(Number)
  const [eh, em] = String(endClock).split(':').map(Number)
  const mins = eh * 60 + em - (sh * 60 + sm)
  if (mins <= 0 || mins % 60 !== 0) return null
  return mins / 60
}

function matchQuickHours(hours) {
  return hours != null && QUICK_HOURS.includes(hours) ? hours : null
}

const QUICK_SESSION_DAYS = [1, 3, 7]

function daysBetweenDates(startDate, endDate) {
  const s = new Date(`${startDate}T00:00:00`)
  const e = new Date(`${endDate}T00:00:00`)
  const diff = Math.floor((e - s) / 86400000) + 1
  return diff > 0 ? diff : null
}

function matchQuickSessionDays(days) {
  return days != null && QUICK_SESSION_DAYS.includes(days) ? days : null
}

function matchDailyPreset(startClock, endClock) {
  if (startClock === STORE_OPEN.start && endClock === STORE_OPEN.end) return 'full'
  if (startClock === '08:00' && endClock === '18:00') return '8-18'
  if (startClock === '09:00' && endClock === '21:00') return '9-21'
  return null
}

const PERIOD_TYPES = ['weekly', 'monthly', 'quarterly']

const BILL_TYPE_LABELS = {
  hourly: '按小时',
  daily: '天卡',
  session: '次卡',
  weekly: '周卡',
  monthly: '月卡',
  quarterly: '季卡',
  night: '夜读',
}

const PRIMARY_GROUPS = [
  { key: 'hourly', label: '按小时' },
  { key: 'daily', label: '天卡' },
  { key: 'session', label: '次卡' },
  { key: 'period', label: '周期卡' },
]

const PERIOD_OPTIONS = [
  { type: 'weekly', label: '周卡', days: '7天' },
  { type: 'monthly', label: '月卡', days: '30天' },
  { type: 'quarterly', label: '季卡', days: '90天' },
]

Page({
  data: {
    storeId: null,
    storeName: '',
    billType: 'hourly',
    primaryGroups: PRIMARY_GROUPS,
    periodOptions: PERIOD_OPTIONS,
    activePrimaryKey: 'hourly',
    selectedTypeLabel: '按小时',
    showPeriodSubs: false,
    showNightType: false,
    today: todayStr(),
    startDate: '',
    endDate: '',
    startClock: '07:30',
    endClock: '09:30',
    hours: 2,
    quickHours: 2,
    quickDailyPreset: null,
    quickSessionDays: 1,
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
    storeHoursHint: `营业 ${STORE_HOURS_LABEL}`,
    nightHint: OFFICE_NIGHT_BOOKING_HINT,
    activeNightCard: null,
    nightCardHint: '',
    nightDateMin: '',
    nightDateMax: '',
    pricingMap: {},
    hourlyMinHours: 2,
    hourlyMaxHours: 24,
    hourlyHint: '最少2小时，最长24小时',
    previewError: '',
    seatsLoading: false,
    previewLoading: false,
    showSeatMap: false,
    userCards: [],
    activePeriodCard: null,
    periodCardHint: '',
    periodCardChoices: [],
    periodCardChoiceIndex: 0,
    selectedPeriodCardId: null,
    periodDateMin: '',
    periodUseDeadline: '',
    periodEndMax: '',
    hasMultiDayDailyCard: false,
    dailyUseMode: 'single',
    multiDayDailyCard: null,
  },

  onLoad(options) {
    const redirect = `${routes.bookingIndex}?storeId=${options.storeId || ''}`
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
    this.setData({
      storeId: options.storeId,
      startDate: today,
      endDate: today,
      startClock: defaultHourlyStartClock(today, today, nowTimeStr()),
      endClock: this._addHoursToClock(
        defaultHourlyStartClock(today, today, nowTimeStr()),
        2,
      ),
      quickHours: 2,
      planSeatCount: this._layout.planSeatCount,
      showSeatMap: true,
      ...this._typeUiPatch(options.billType || 'hourly', false),
    }, () => {
      const billType = options.billType || this.data.billType || 'hourly'
      if (billType !== 'hourly') {
        this.switchType({ currentTarget: { dataset: { type: billType } } })
      } else {
        this.refreshPreview({ immediate: true })
      }
    })

    request({ url: `/store/${options.storeId}`, silent: true }).then((s) => {
      this.setData({ storeName: s.name })
    })

    this._fetchPricing(options.storeId).then(() => {
      this.refreshPreview({ immediate: true })
    })
    this.loadUserCards({ force: !!options.billType })
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
    const hourly = pricingMap.hourly || {}
    const minH = hourly.min_hours || 2
    const maxH = hourly.max_hours || 24
    return {
      pricingMap,
      hourlyMinHours: minH,
      hourlyMaxHours: maxH,
      hourlyHint: `最少${minH}小时，最长${maxH}小时`,
    }
  },

  _hourlyLimits() {
    return {
      min: this.data.hourlyMinHours || 2,
      max: this.data.hourlyMaxHours || 24,
    }
  },

  loadUserCards(options = {}) {
    const { force = false } = options
    return request({ url: '/user/cards', silent: true, force })
      .then((cards) => {
        const list = (cards || []).filter(isCardUsable).map(formatCard)
        const patch = {
          userCards: list,
          hasMultiDayDailyCard: !!this._findMultiDayDailyCard(list),
        }
        const officeNight = this._findActiveNightCard(list)
        patch.activeNightCard = officeNight
        if (officeNight) {
          patch.nightDateMin = officeNight.start_date || todayStr()
          patch.nightDateMax = officeNight.end_date || ''
        }
        if (officeNight && this.data.billType === 'hourly') {
          Object.assign(patch, { billType: 'night' }, this._applyNightPeriod(this.data.startDate, officeNight))
        } else if (this.data.billType === 'night') {
          Object.assign(patch, this._applyNightPeriod(this.data.startDate, officeNight || this.data.activeNightCard))
        } else if (PERIOD_TYPES.includes(this.data.billType)) {
          Object.assign(
            patch,
            this._periodCardPatch(
              this.data.billType,
              list,
              this.data.selectedPeriodCardId,
              this.data.startDate,
            ),
          )
        }
        Object.assign(patch, this._typeUiPatch(patch.billType || this.data.billType, !!officeNight))
        patch.periodOptions = this._buildPeriodOptions(list)
        this.setData(patch, () => {
          if (patch.billType === 'night') this.refreshPreview({ immediate: true })
        })
      })
      .catch(() => {})
  },

  _nightMaxEnd(startDate, card) {
    let end = addDays(startDate, BILL_DEFAULTS.night.endOffset)
    if (card && card.end_date && end > card.end_date) end = card.end_date
    return end
  },

  _findPeriodCards(cards, billType) {
    if (!PERIOD_TYPES.includes(billType)) return []
    const storeId = Number(this.data.storeId)
    return (cards || []).filter((c) => {
      if (c.card_type !== billType) return false
      if (isOfficeNightMonthlyCard(c)) return false
      if (!isCardUsable(c)) return false
      if (c.store_id && Number(c.store_id) !== storeId) return false
      return true
    })
  },

  _findPeriodCard(cards, billType, cardId) {
    const list = this._findPeriodCards(cards, billType)
    if (!list.length) return null
    if (cardId) {
      return list.find((c) => c.id === cardId) || list[0]
    }
    return list[0]
  },

  _formatPeriodCardChoice(card, billType) {
    const span = periodPassSpan(billType, card)
    const name = (card.card_name || '').trim() || BILL_TYPE_LABELS[billType] || '期限卡'
    const durationLabel = formatPassDurationLabel(span)
    const label = durationLabel ? `${name} · ${durationLabel}` : name
    return { id: card.id, label, span, name, durationLabel }
  },

  _resolvePeriodCardState(billType, cards, preferredId) {
    const list = this._findPeriodCards(cards, billType)
    const choices = list.map((c) => this._formatPeriodCardChoice(c, billType))
    let selectedId = preferredId
    if (!selectedId || !list.some((c) => c.id === selectedId)) {
      selectedId = list[0] ? list[0].id : null
    }
    const card = selectedId ? list.find((c) => c.id === selectedId) || null : null
    const choiceIndex = Math.max(0, choices.findIndex((c) => c.id === selectedId))
    return {
      card,
      choices,
      selectedId,
      choiceIndex,
    }
  },

  _buildPeriodOptions(cards) {
    return PERIOD_OPTIONS.map((opt) => {
      const list = this._findPeriodCards(cards || this.data.userCards, opt.type)
      let days = opt.days
      if (list.length === 1) {
        const span = periodPassSpan(opt.type, list[0])
        const durationLabel = formatPassDurationLabel(span)
        if (durationLabel) days = durationLabel
        else if (span > 0) days = `连续${span}天`
      } else if (list.length > 1) {
        days = '多规格'
      }
      return {
        ...opt,
        label: opt.label,
        days,
      }
    })
  },

  _periodRequiredSpan(billType, card) {
    return periodPassSpan(billType, card)
  },

  _periodMaxEnd(startDate, billType, card) {
    const span = this._periodRequiredSpan(billType, card)
    const offset = span > 0 ? span - 1 : (BILL_DEFAULTS[billType]?.endOffset ?? 0)
    let end = addDays(startDate, offset)
    if (card && card.end_date && end > card.end_date) end = card.end_date
    return end
  },

  _latestPeriodStart(card, billType) {
    if (!card || !card.end_date) return null
    const span = this._periodRequiredSpan(billType, card)
    if (!span) return null
    const latest = addDays(card.end_date, -(span - 1))
    const today = todayStr()
    const min = card.start_date && card.start_date > today ? card.start_date : today
    return latest < min ? null : latest
  },

  _periodCardSuffix(billType, card) {
    const span = this._periodRequiredSpan(billType, card)
    if (span > 0) {
      const durationLabel = formatPassDurationLabel(span)
      if (billType === 'monthly') {
        return durationLabel
          ? `卡面效期 180 天，${durationLabel}须一次约满`
          : `卡面效期 180 天，须连续 ${span} 天`
      }
      return durationLabel ? `${durationLabel}须一次约满` : `须连续 ${span} 天`
    }
    if (billType === 'quarterly') return '效期内预约一次即核销'
    return ''
  },

  _applyPeriodDates(startDate, billType, card) {
    const today = todayStr()
    let start = startDate || today
    let min = today
    let useDeadline = ''
    if (card && card.start_date && card.end_date) {
      min = card.start_date > today ? card.start_date : today
      useDeadline = card.end_date
      const latestStart = this._latestPeriodStart(card, billType)
      if (latestStart && start > latestStart) start = latestStart
      if (start < min) start = min
      if (start > useDeadline) start = min
    }
    const span = this._periodRequiredSpan(billType, card)
    let end = this._periodMaxEnd(start, billType, card)
    if (span > 0) {
      end = addDays(start, span - 1)
      if (card && card.end_date && end > card.end_date) {
        end = card.end_date
        const latestStart = this._latestPeriodStart(card, billType)
        if (latestStart) start = latestStart
      }
    }
    let periodCardHint = card ? cardValidityHint(card, this._periodCardSuffix(billType, card)) : ''
    if (card && span > 0 && daysBetweenDates(start, end) !== span) {
      periodCardHint = cardValidityHint(
        card,
        `须连续 ${span} 天，请将开始日期调至 ${this._latestPeriodStart(card, billType) || min} 前`,
      )
    }
    return {
      startDate: start,
      endDate: end,
      periodDateMin: min,
      periodUseDeadline: useDeadline,
      periodEndMax: end,
      activePeriodCard: card,
      periodCardHint,
    }
  },

  _periodCardPatch(billType, cards, preferredId, startDate) {
    const resolved = this._resolvePeriodCardState(billType, cards, preferredId)
    return {
      ...this._applyPeriodDates(startDate || this.data.startDate, billType, resolved.card),
      periodCardChoices: resolved.choices,
      periodCardChoiceIndex: resolved.choiceIndex,
      selectedPeriodCardId: resolved.selectedId,
    }
  },

  onPeriodCardPick(e) {
    const index = Number(e.detail.value)
    const choice = (this.data.periodCardChoices || [])[index]
    if (!choice) return
    const card = this._findPeriodCard(this.data.userCards, this.data.billType, choice.id)
    const patch = {
      periodCardChoiceIndex: index,
      selectedPeriodCardId: choice.id,
      ...this._applyPeriodDates(this.data.startDate, this.data.billType, card),
    }
    this.setData(patch, () => this.refreshPreview())
  },

  _applyNightPeriod(startDate, card) {
    const today = todayStr()
    let start = startDate || today
    let min = today
    let max = ''
    if (card && card.start_date && card.end_date) {
      min = card.start_date > today ? card.start_date : today
      max = card.end_date
      if (start < min) start = min
      if (start > max) start = min
    }
    const end = this._nightMaxEnd(start, card)
    return {
      startDate: start,
      endDate: end,
      nightDateMin: min,
      nightDateMax: max,
      nightHint: OFFICE_NIGHT_BOOKING_HINT,
      nightCardHint: card ? cardValidityHint(card, '须连续 30 天') : OFFICE_NIGHT_BOOKING_HINT,
    }
  },

  _findActiveNightCard(cards) {
    return (cards || []).find((c) => isOfficeNightMonthlyCard(c) && isCardUsable(c)) || null
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

  _typeUiPatch(billType, showNight) {
    const period = PERIOD_TYPES.includes(billType)
    let activePrimaryKey = billType
    if (period) activePrimaryKey = 'period'
    else if (billType === 'night') activePrimaryKey = 'night'

    let selectedTypeLabel = BILL_TYPE_LABELS[billType] || billType

    return {
      activePrimaryKey,
      showPeriodSubs: period,
      showNightType: showNight !== undefined ? showNight : !!this.data.activeNightCard,
      selectedTypeLabel,
    }
  },

  switchPrimary(e) {
    const key = e.currentTarget.dataset.key
    if (key === 'period') {
      const type = PERIOD_TYPES.includes(this.data.billType) ? this.data.billType : 'weekly'
      this.switchType({ currentTarget: { dataset: { type } } })
      return
    }
    const map = { hourly: 'hourly', daily: 'daily', session: 'session' }
    if (map[key]) {
      this.switchType({ currentTarget: { dataset: { type: map[key] } } })
    }
  },

  switchType(e) {
    const billType = e.currentTarget.dataset.type
    const { startDate } = this.data
    const defaults = BILL_DEFAULTS[billType]
    const patch = { billType, seatId: null, seatCode: '', selectedId: null, selectedLabel: '', selectedZone: '', preview: null }

    if (billType === 'hourly') {
      const startClock = defaultHourlyStartClock(startDate, todayStr(), nowTimeStr())
      Object.assign(patch, {
        startClock,
        endClock: this._addHoursToClock(startClock, defaults.hours),
        hours: defaults.hours,
        quickHours: matchQuickHours(defaults.hours),
        quickDailyPreset: null,
        quickSessionDays: null,
      })
    } else if (billType === 'session') {
      Object.assign(patch, { endDate: startDate, quickSessionDays: 1, quickDailyPreset: null, quickHours: null })
    } else if (billType === 'daily') {
      const clocks = defaultDailyClocks(startDate, todayStr(), nowTimeStr())
      Object.assign(patch, {
        endDate: startDate,
        dailyUseMode: 'single',
        multiDayDailyCard: null,
        startClock: clocks.startClock,
        endClock: clocks.endClock,
        quickDailyPreset: matchDailyPreset(clocks.startClock, clocks.endClock),
        quickHours: null,
        quickSessionDays: null,
      })
    } else if (PERIOD_TYPES.includes(billType)) {
      const preferredId = billType === this.data.billType ? this.data.selectedPeriodCardId : null
      Object.assign(patch, this._periodCardPatch(billType, this.data.userCards, preferredId, startDate))
    } else if (billType === 'night') {
      Object.assign(patch, this._applyNightPeriod(startDate, this.data.activeNightCard))
    }

    Object.assign(patch, this._typeUiPatch(billType))
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
      patch.quickSessionDays = 1
    } else if (PERIOD_TYPES.includes(this.data.billType)) {
      Object.assign(
        patch,
        this._periodCardPatch(
          this.data.billType,
          this.data.userCards,
          this.data.selectedPeriodCardId,
          startDate,
        ),
      )
    } else if (this.data.billType === 'night') {
      Object.assign(patch, this._applyNightPeriod(startDate, this.data.activeNightCard))
    }
    if (this.data.billType === 'hourly' && startDate === todayStr()) {
      const startClock = defaultHourlyStartClock(startDate, todayStr(), nowTimeStr())
      patch.startClock = startClock
      patch.endClock = this._addHoursToClock(startClock, this.data.hours)
      patch.quickHours = matchQuickHours(this.data.hours)
    } else if (
      this.data.billType === 'daily'
      && this.data.dailyUseMode === 'single'
      && patch.endDate === startDate
    ) {
      const clocks = defaultDailyClocks(startDate, todayStr(), nowTimeStr())
      patch.startClock = clocks.startClock
      patch.endClock = clocks.endClock
      patch.quickDailyPreset = matchDailyPreset(clocks.startClock, clocks.endClock)
    }
    this.setData(patch, () => this.refreshPreview())
  },

  onEndDateChange(e) {
    if (this.data.billType === 'daily' && this.data.dailyUseMode === 'multi_pass') return
    const endDate = e.detail.value
    const patch = { endDate }
    if (this.data.billType === 'night') {
      const maxEnd = this._nightMaxEnd(this.data.startDate, this.data.activeNightCard)
      if (endDate > maxEnd) {
        wx.showToast({ title: `结束日期不能晚于 ${maxEnd}`, icon: 'none' })
        return
      }
      if (endDate < this.data.startDate) {
        wx.showToast({ title: '结束日期不能早于开始日期', icon: 'none' })
        return
      }
      if (this.data.activeNightCard) {
        const span = officeNightPassDays(this.data.activeNightCard)
        const days = daysBetweenDates(this.data.startDate, endDate)
        if (days !== span) {
          wx.showToast({ title: `须连续 ${span} 天`, icon: 'none' })
          return
        }
      }
    }
    if (PERIOD_TYPES.includes(this.data.billType)) {
      const card = this.data.activePeriodCard
      const span = this._periodRequiredSpan(this.data.billType, card)
      const maxEnd = this._periodMaxEnd(this.data.startDate, this.data.billType, card)
      if (endDate > maxEnd) {
        wx.showToast({ title: `结束日期不能晚于 ${maxEnd}`, icon: 'none' })
        return
      }
      if (endDate < this.data.startDate) {
        wx.showToast({ title: '结束日期不能早于开始日期', icon: 'none' })
        return
      }
      if (span > 0) {
        const days = daysBetweenDates(this.data.startDate, endDate)
        if (days !== span) {
          patch.endDate = addDays(this.data.startDate, span - 1)
          wx.showToast({ title: `须连续 ${span} 天，已自动调整`, icon: 'none' })
        }
      }
    }
    if (this.data.billType === 'session') {
      patch.quickSessionDays = matchQuickSessionDays(
        daysBetweenDates(this.data.startDate, endDate),
      )
    }
    this.setData(patch, () => this.refreshPreview())
  },

  _isDailySingleDay() {
    return (
      this.data.billType === 'daily'
      && this.data.dailyUseMode === 'single'
      && this.data.startDate === this.data.endDate
    )
  },

  onStartClockChange(e) {
    let startClock = e.detail.value
    const patch = { startClock }
    if (this.data.billType === 'hourly') {
      const clamped = clampHourlyClocks(this.data.startDate, startClock, this.data.endClock)
      patch.startClock = clamped.startClock
      patch.endClock = this._addHoursToClock(clamped.startClock, this.data.hours)
      patch.quickHours = matchQuickHours(this.data.hours)
      const err = validateStoreTimeRange(this.data.startDate, patch.startClock, patch.endClock)
      if (err) {
        wx.showToast({ title: err, icon: 'none' })
        return
      }
    } else if (this._isDailySingleDay()) {
      const clamped = clampHourlyClocks(this.data.startDate, startClock, this.data.endClock)
      patch.startClock = clamped.startClock
      patch.endClock = clamped.endClock
      patch.quickDailyPreset = matchDailyPreset(patch.startClock, patch.endClock)
      const err = validateStoreTimeRange(this.data.startDate, patch.startClock, patch.endClock)
      if (err) {
        wx.showToast({ title: err, icon: 'none' })
        return
      }
    }
    this.setData(patch, () => this.refreshPreview())
  },

  onEndClockChange(e) {
    let endClock = e.detail.value
    const patch = { endClock }
    if (this.data.billType === 'hourly' || this._isDailySingleDay()) {
      const clamped = clampHourlyClocks(this.data.startDate, this.data.startClock, endClock)
      patch.endClock = clamped.endClock
      const err = validateStoreTimeRange(this.data.startDate, this.data.startClock, patch.endClock)
      if (err) {
        wx.showToast({ title: err, icon: 'none' })
        return
      }
      if (this.data.billType === 'hourly') {
        const span = wholeHoursBetween(this.data.startClock, patch.endClock)
        if (span) patch.hours = span
        patch.quickHours = matchQuickHours(span)
      } else if (this._isDailySingleDay()) {
        patch.quickDailyPreset = matchDailyPreset(this.data.startClock, patch.endClock)
      }
    }
    this.setData(patch, () => this.refreshPreview())
  },

  setDailyFullDay() {
    const startClock = STORE_OPEN.start
    const endClock = STORE_OPEN.end
    this.setData({
      startClock,
      endClock,
      quickDailyPreset: 'full',
    }, () => this.refreshPreview())
  },

  setDailyPreset(e) {
    const { start, end } = e.currentTarget.dataset
    const err = validateStoreTimeRange(this.data.startDate, start, end)
    if (err) {
      wx.showToast({ title: err, icon: 'none' })
      return
    }
    this.setData({
      startClock: start,
      endClock: end,
      quickDailyPreset: matchDailyPreset(start, end),
    }, () => this.refreshPreview())
  },

  setHours(e) {
    const hours = Number(e.currentTarget.dataset.h)
    let endClock = this._addHoursToClock(this.data.startClock, hours)
    if (this.data.billType === 'hourly') {
      if (compareClock(endClock, STORE_OPEN.end) > 0) {
        wx.showToast({ title: `结束时间不能晚于 ${STORE_OPEN.end}`, icon: 'none' })
        endClock = STORE_OPEN.end
      }
    }
    const span = wholeHoursBetween(this.data.startClock, endClock)
    this.setData({
      hours: span || hours,
      endClock,
      quickHours: matchQuickHours(span),
    }, () => this.refreshPreview())
  },

  setSessionDays(e) {
    const days = Number(e.currentTarget.dataset.d)
    this.setData({
      endDate: addDays(this.data.startDate, days - 1),
      quickSessionDays: matchQuickSessionDays(days),
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
      const err = validateStoreTimeRange(startDate, startClock, endClock)
      if (err) throw new Error(err)
      if (end <= start) {
        throw new Error('结束时间须晚于开始时间')
      }
      const { min, max } = this._hourlyLimits()
      const diffH = (end - start) / 3600000
      if (diffH < min) throw new Error(`按小时预约最少${min}小时`)
      if (diffH > max) throw new Error(`按小时预约最长${max}小时`)
    } else if (billType === 'night') {
      ;({ start, end } = nightRangeDateTimes(startDate, endDate))
      if (end <= start) throw new Error('结束日期须晚于开始日期')
      const days = Math.floor((end - start) / 86400000) + 1
      if (this.data.activeNightCard) {
        const span = officeNightPassDays(this.data.activeNightCard)
        if (days !== span) throw new Error(`夜读月卡须连续预约 ${span} 天`)
      } else if (days > 30) {
        throw new Error('夜读单次最多预约30天')
      }
    } else if (billType === 'daily') {
      const multi = this.data.dailyUseMode === 'multi_pass' ? this.data.multiDayDailyCard : null
      if (multi) {
        ;({ start, end } = storeRangeDateTimes(startDate, endDate))
        const span = dailyPassDays(multi)
        const days = Math.floor((end - start) / 86400000) + 1
        if (startDate !== multi.start_date || endDate !== multi.end_date || days !== span) {
          throw new Error(`该卡须连续预约 ${multi.start_date} 至 ${multi.end_date}`)
        }
      } else if (startDate === endDate) {
        ;({ start, end } = clockRangeDateTimes(startDate, startClock, endDate, endClock))
        const err = validateStoreTimeRange(startDate, startClock, endClock)
        if (err) throw new Error(err)
        if (end <= start) throw new Error('结束时间须晚于开始时间')
      } else {
        ;({ start, end } = storeRangeDateTimes(startDate, endDate))
      }
      if (end < start) throw new Error('结束日期不能早于开始日期')
    } else {
      ;({ start, end } = storeRangeDateTimes(startDate, endDate))
      if (end < start) throw new Error('结束日期不能早于开始日期')
      if (billType === 'monthly' && this.data.activePeriodCard) {
        const span = monthlyPassDays(this.data.activePeriodCard)
        const days = daysBetweenDates(startDate, endDate)
        if (days !== span) {
          throw new Error(`月卡须连续预约 ${span} 天，请调整日期`)
        }
      } else if (billType === 'weekly' && this.data.activePeriodCard) {
        const span = weeklyPassDays(this.data.activePeriodCard)
        const days = daysBetweenDates(startDate, endDate)
        if (days !== span) {
          throw new Error(`周卡须连续预约 ${span} 天，请调整日期`)
        }
      } else if (billType === 'session') {
        const days = Math.floor((end - start) / 86400000) + 1
        if (days > 30) throw new Error('次卡单次最多连续预约30天')
      } else if (['weekly', 'monthly', 'quarterly'].includes(billType) && end <= start) {
        throw new Error('结束日期须晚于开始日期')
      }
    }

    return {
      start: formatLocalDateTime(start),
      end: formatLocalDateTime(end),
    }
  },

  _formatSummary(start, end) {
    if (this.data.billType === 'night') {
      const fmtDate = (s) => {
        const d = new Date(s.replace(' ', 'T'))
        const w = ['日', '一', '二', '三', '四', '五', '六'][d.getDay()]
        return `${s.slice(0, 10)} 周${w}`
      }
      const days = Math.floor((new Date(end.replace(' ', 'T')) - new Date(start.replace(' ', 'T'))) / 86400000) + 1
      return `${fmtDate(start)}  →  ${fmtDate(end)} · 共 ${days} 天`
    }
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
        previewError: err.message || '请检查使用时间',
      })
      return Promise.resolve()
    }

    this.setData({
      startTime: start,
      endTime: end,
      timeSummary: this._formatSummary(start, end),
      previewLoading: true,
      showSeatMap: true,
      previewError: '',
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
      .catch((e) => {
        this.setData({
          preview: null,
          previewLoading: false,
          previewError: formatRequestError(e),
        })
      })

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
      wx.showToast({ title: '更新中…', icon: 'none' })
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
    }, () => this.refreshPreview({ immediate: true }))
  },

  goOrder() {
    const { storeId, preview, billType, seatId } = this.data
    if (!auth.isLoggedIn()) {
      const redirect = `${routes.bookingIndex}?storeId=${storeId}`
      auth.requireLogin(redirect)
      return
    }
    if (!seatId) {
      wx.showToast({ title: '请先选座', icon: 'none' })
      return
    }
    if (this.data.previewLoading) {
      wx.showToast({ title: '价格计算中…', icon: 'none' })
      return
    }
    if (preview && preview.seat_id === seatId) {
      wx.navigateTo({
        url: `${routes.bookingOrder}?storeId=${storeId}&start=${encodeURIComponent(preview.start_time)}&end=${encodeURIComponent(preview.end_time)}&seatId=${preview.seat_id}&price=${preview.final_price}&seatCode=${preview.seat_code}&billType=${billType}`,
      })
      return
    }
    // 选座后预览尚未带上该座位，自动刷新一次再跳转
    this.refreshPreview({ immediate: true }).then(() => {
      const { preview: latest, seatId: sid } = this.data
      if (latest && latest.seat_id === sid) {
        wx.navigateTo({
          url: `${routes.bookingOrder}?storeId=${storeId}&start=${encodeURIComponent(latest.start_time)}&end=${encodeURIComponent(latest.end_time)}&seatId=${latest.seat_id}&price=${latest.final_price}&seatCode=${latest.seat_code}&billType=${billType}`,
        })
      } else {
        wx.showToast({ title: '价格计算失败，请重试', icon: 'none' })
      }
    })
  },
})
