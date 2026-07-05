const { request, formatRequestError, invalidateCache } = require('../../utils/request')
const { getLayout } = require('../../utils/seat-layout')
const { dailyPassDays, isOfficeNightMonthlyCard, OFFICE_NIGHT_BOOKING_HINT, cardValidUntil, withinCardValidity, weeklyPassDays, monthlyPassDays, officeNightPassDays } = require('../../utils/cardDisplay')
const { completeWechatPay, ensureReservationPaid } = require('../../utils/pay')

const BILL_LABELS = { hourly: '按小时', daily: '天卡', weekly: '周卡', session: '次卡', monthly: '月卡', quarterly: '季卡', night: '夜读' }

function countSessionDays(startIso, endIso) {
  const s = new Date(startIso.replace(' ', 'T'))
  const e = new Date(endIso.replace(' ', 'T'))
  return Math.floor((e - s) / 86400000) + 1
}

function bookingHours(startIso, endIso) {
  const s = new Date(startIso.replace(' ', 'T'))
  const e = new Date(endIso.replace(' ', 'T'))
  return Math.round((e - s) / 3600000 * 10) / 10
}

function withinCardPeriod(card, startIso, endIso) {
  const start = startIso.slice(0, 10)
  const end = endIso.slice(0, 10)
  if (card.start_date && start < card.start_date) return false
  if (card.end_date && end > card.end_date) return false
  return true
}

function bookingSpanDays(startIso, endIso) {
  return countSessionDays(startIso, endIso)
}

function cardTypeMatchesBill(card, billType) {
  if (isOfficeNightMonthlyCard(card) || card.card_type === 'night_monthly' || card.usage_rule) {
    return billType === 'night'
  }
  if (card.card_type === 'hourly') return billType === 'hourly'
  if (card.card_type === 'session') return billType === 'session'
  if (card.card_type === 'daily') return billType === 'daily'
  return card.card_type === billType
}

function explainCardMismatch(cards, ctx) {
  const { storeId, billType, startTime, endTime } = ctx
  const owned = (cards || []).filter((c) => {
    if (c.store_id && Number(c.store_id) !== storeId) return false
    return true
  })
  if (!owned.length) return '暂无可用期限卡'

  const typeMatched = owned.filter((c) => cardTypeMatchesBill(c, billType))
  if (!typeMatched.length) {
    return '期限卡类型与当前预约方式不匹配，请返回切换套餐'
  }

  const periodOk = typeMatched.find((c) => {
    if (isOfficeNightMonthlyCard(c) || c.card_type === 'night_monthly' || c.usage_rule) {
      return (
        billType === 'night'
        && bookingSpanDays(startTime, endTime) === officeNightPassDays(c)
        && withinCardPeriod(c, startTime, endTime)
      )
    }
    if (c.card_type === 'weekly') {
      return (
        billType === 'weekly'
        && bookingSpanDays(startTime, endTime) === weeklyPassDays(c)
        && withinCardPeriod(c, startTime, endTime)
      )
    }
    if (c.card_type === 'daily') {
      const span = dailyPassDays(c)
      if (span > 1 && c.start_date && c.end_date) {
        const window = Math.floor(
          (new Date(`${c.end_date}T00:00:00`) - new Date(`${c.start_date}T00:00:00`)) / 86400000
        ) + 1
        if (window > 7) {
          return (
            billType === 'daily'
            && bookingSpanDays(startTime, endTime) === span
            && withinCardPeriod(c, startTime, endTime)
          )
        }
      }
    }
    if (c.card_type === 'monthly' && !isOfficeNightMonthlyCard(c)) {
      return (
        billType === 'monthly'
        && bookingSpanDays(startTime, endTime) === monthlyPassDays(c)
        && withinCardPeriod(c, startTime, endTime)
      )
    }
    if (c.card_type === 'quarterly') {
      return withinCardValidity(c, startTime)
    }
    return withinCardPeriod(c, startTime, endTime)
  })
  if (periodOk) return ''

  const card = typeMatched[0]
  const start = startTime.slice(0, 10)
  const end = endTime.slice(0, 10)
  if (isOfficeNightMonthlyCard(card) || card.card_type === 'night_monthly' || card.usage_rule) {
    const span = officeNightPassDays(card)
    if (bookingSpanDays(startTime, endTime) !== span) {
      return `须预约连续 ${span} 天，请返回调整`
    }
    if (!withinCardPeriod(card, startTime, endTime)) {
      if (card.end_date && end > card.end_date) {
        return `预约须落在效期内（至 ${card.end_date}），请返回调整`
      }
    }
    return '当前无法使用该夜读月卡，请返回调整'
  }
  if (card.card_type === 'weekly') {
    const span = weeklyPassDays(card)
    if (bookingSpanDays(startTime, endTime) !== span) {
      return `须预约连续 ${span} 天，请返回调整`
    }
    if (!withinCardPeriod(card, startTime, endTime)) {
      if (card.end_date && end > card.end_date) {
        return `预约须落在效期内（至 ${card.end_date}），请返回调整`
      }
    }
    return '当前无法使用该周卡，请返回调整'
  }
  if (card.card_type === 'monthly' && !isOfficeNightMonthlyCard(card)) {
    const span = monthlyPassDays(card)
    if (bookingSpanDays(startTime, endTime) !== span) {
      return `须预约连续 ${span} 天，请返回调整`
    }
    if (!withinCardPeriod(card, startTime, endTime)) {
      if (card.end_date && end > card.end_date) {
        return `预约须落在效期内（至 ${card.end_date}），请返回调整`
      }
    }
    return '当前无法使用该月卡，请返回调整'
  }
  if (card.card_type === 'quarterly') {
    if (card.start_date && start < card.start_date) {
      return `预约开始日早于卡生效日（${card.start_date}），请返回调整`
    }
    const until = cardValidUntil(card)
    if (until && start > until) {
      return `须在 ${until} 前开始预约，请返回调整开始日期`
    }
    return '当前无法使用该期限卡，请返回调整'
  }
  if (card.start_date && start < card.start_date) {
    return `预约开始日早于卡生效日（${card.start_date}），请返回调整`
  }
  if (card.end_date && end > card.end_date) {
    return `预约结束日超出卡有效期（${card.end_date}），请返回调整结束日期`
  }
  return '当前预约时段无法使用该期限卡，请返回调整'
}

function isUsableCard(card, ctx) {
  const {
    storeId, billType, startTime, endTime, sessionDays, bookingH,
  } = ctx
  if (card.store_id && card.store_id !== storeId) return false

  if (card.card_type === 'hourly') {
    if (billType !== 'hourly') return false
    if (!(Number(card.remaining_hours) > 0)) return false
    if (card.end_date && startTime.slice(0, 10) > card.end_date) return false
    if (card.start_date && startTime.slice(0, 10) < card.start_date) return false
    return bookingH > 0 && bookingH <= Number(card.remaining_hours)
  }

  if (card.card_type === 'session') {
    if (billType !== 'session') return false
    if (!(Number(card.remaining_sessions) > 0)) return false
    return sessionDays >= 1 && sessionDays <= Number(card.remaining_sessions)
      && withinCardPeriod(card, startTime, endTime)
  }

  if (isOfficeNightMonthlyCard(card) || card.card_type === 'night_monthly' || card.usage_rule) {
    if (billType !== 'night') return false
    return (
      bookingSpanDays(startTime, endTime) === officeNightPassDays(card)
      && withinCardPeriod(card, startTime, endTime)
    )
  }

  if (card.card_type === 'daily') {
    if (billType !== 'daily') return false
    const span = dailyPassDays(card)
    if (span > 1 && card.start_date && card.end_date) {
      const window = Math.floor(
        (new Date(`${card.end_date}T00:00:00`) - new Date(`${card.start_date}T00:00:00`)) / 86400000
      ) + 1
      if (window > 7) {
        return (
          bookingSpanDays(startTime, endTime) === span
          && withinCardPeriod(card, startTime, endTime)
        )
      }
      const start = startTime.slice(0, 10)
      const end = endTime.slice(0, 10)
      return start === card.start_date && end === card.end_date
    }
    const start = startTime.slice(0, 10)
    const end = endTime.slice(0, 10)
    if (start !== end) return false
    return withinCardPeriod(card, startTime, endTime)
  }

  if (card.card_type === 'weekly') {
    if (billType !== 'weekly') return false
    return (
      bookingSpanDays(startTime, endTime) === weeklyPassDays(card)
      && withinCardPeriod(card, startTime, endTime)
    )
  }
  if (card.card_type === 'monthly' && !isOfficeNightMonthlyCard(card)) {
    if (billType !== 'monthly') return false
    return (
      bookingSpanDays(startTime, endTime) === monthlyPassDays(card)
      && withinCardPeriod(card, startTime, endTime)
    )
  }
  if (card.card_type === 'quarterly') {
    return billType === 'quarterly' && withinCardValidity(card, startTime)
  }

  return false
}

function formatDate(iso) {
  const d = new Date(String(iso).replace(' ', 'T'))
  const pad = (n) => (n < 10 ? '0' + n : '' + n)
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

function formatOrderRange(billType, startIso, endIso) {
  const pad = (n) => (n < 10 ? '0' + n : '' + n)
  const fmtDate = (iso) => {
    const d = new Date(String(iso).replace(' ', 'T'))
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
  }
  if (billType === 'night') {
    const start = fmtDate(startIso)
    const end = fmtDate(endIso)
    const days = countSessionDays(startIso, endIso)
    return { startDisplay: start, endDisplay: end, nightDays: days }
  }
  return {
    startDisplay: formatDate(startIso),
    endDisplay: formatDate(endIso),
    nightDays: 0,
  }
}

Page({
  data: {
    storeId: null,
    startTime: '',
    endTime: '',
    seatId: null,
    seatCode: '',
    seatDisplay: '',
    originalPrice: 0,
    discountPrice: 0,
    price: 0,
    payType: 'wechat',
    billType: 'hourly',
    billTypeLabel: '按小时',
    orderNo: '',
    reservationId: null,
    startDisplay: '',
    endDisplay: '',
    cards: [],
    usableCards: [],
    selectedCardId: null,
    selectedCardName: '',
    coupons: [],
    usableCoupons: [],
    selectedCouponId: null,
    sessionDays: 0,
    nightDays: 0,
    nightBookingHint: OFFICE_NIGHT_BOOKING_HINT,
    payOptionsError: '',
    cardMismatchHint: '',
    submitting: false,
  },

  onLoad(options) {
    this._payTypePinned = false
    const layout = getLayout()
    const display = layout.seatDisplay({ seat_code: options.seatCode || '' })
    const seatDisplay = display.mapLabel
      ? `${display.mapLabel} 号 · ${display.zoneName}`
      : (options.seatCode || '-')
    const startTime = decodeURIComponent(options.start)
    const endTime = decodeURIComponent(options.end)
    const billType = options.billType || 'hourly'
    const range = formatOrderRange(billType, startTime, endTime)
    this.setData({
      storeId: options.storeId,
      startTime,
      endTime,
      seatId: options.seatId,
      seatCode: options.seatCode,
      seatDisplay,
      originalPrice: options.price,
      price: options.price,
      billType,
      billTypeLabel: BILL_LABELS[billType] || '按小时',
      startDisplay: range.startDisplay,
      endDisplay: range.endDisplay,
      nightDays: range.nightDays,
      sessionDays: billType === 'session' ? countSessionDays(startTime, endTime) : 0,
    })
  },

  onShow() {
    this.loadPayOptions({ silent: true })
  },

  onPullDownRefresh() {
    this.loadPayOptions({ force: true }).finally(() => wx.stopPullDownRefresh())
  },

  async loadPayOptions(options = {}) {
    const { force = false } = options
    try {
      const [cards, coupons] = await Promise.all([
        request({ url: '/user/cards', silent: true, force }),
        request({ url: '/user/coupons', silent: true, force }),
      ])
      const storeId = Number(this.data.storeId)
      const billType = this.data.billType
      const { startTime, endTime } = this.data
      const sessionDays = billType === 'session' ? countSessionDays(startTime, endTime) : 0
      const bookingH = billType === 'hourly' ? bookingHours(startTime, endTime) : 0
      const ctx = { storeId, billType, startTime, endTime, sessionDays, bookingH }
      const usableCards = (cards || []).filter((c) => isUsableCard(c, ctx))
      const originalPrice = Number(this.data.originalPrice)
      const usableCoupons = (coupons || []).filter(
        (c) => c.status === 0 && originalPrice >= (c.min_amount || 0)
      )
      const patch = {
        cards,
        usableCards,
        coupons,
        usableCoupons,
        payOptionsError: '',
        cardMismatchHint: usableCards.length
          ? ''
          : explainCardMismatch(cards, ctx),
      }
      if (usableCards.length && !this._payTypePinned && this.data.payType !== 'balance') {
        const cur = usableCards.find((c) => c.id === this.data.selectedCardId) || usableCards[0]
        patch.payType = 'period_card'
        patch.selectedCardId = cur.id
        patch.selectedCardName = cur.card_name || cur.card_type
        patch.price = 0
        patch.discountPrice = 0
        patch.selectedCouponId = null
      } else if (this.data.payType === 'period_card') {
        const cur = usableCards.find((c) => c.id === this.data.selectedCardId) || usableCards[0]
        if (cur) {
          patch.selectedCardId = cur.id
          patch.selectedCardName = cur.card_name || cur.card_type
          patch.price = 0
          patch.discountPrice = 0
        } else {
          patch.payType = 'wechat'
          patch.selectedCardId = null
          patch.selectedCardName = ''
        }
      } else if (!usableCards.length) {
        patch.selectedCardId = null
        patch.selectedCardName = ''
      }
      this.setData(patch)
    } catch (e) {
      this.setData({ payOptionsError: formatRequestError(e) })
    }
  },

  setPay(e) {
    this._payTypePinned = true
    const payType = e.currentTarget.dataset.type
    const patch = { payType }
    if (payType === 'period_card' && this.data.usableCards.length) {
      const card = this.data.usableCards[0]
      patch.selectedCardId = card.id
      patch.selectedCardName = card.card_name || card.card_type
      patch.selectedCouponId = null
      patch.price = 0
      patch.discountPrice = 0
    } else if (payType !== 'period_card') {
      patch.selectedCardId = null
      patch.selectedCardName = ''
      this.refreshPrice(this.data.selectedCouponId)
    }
    this.setData(patch)
  },

  selectCard(e) {
    const idx = Number(e.detail.value)
    const card = this.data.usableCards[idx]
    if (!card) return
    this.setData({
      selectedCardId: card.id,
      selectedCardName: card.card_name || card.card_type,
      payType: 'period_card',
      selectedCouponId: null,
      price: 0,
      discountPrice: 0,
    })
  },

  selectCoupon(e) {
    const idx = e.detail.value === '' ? -1 : Number(e.detail.value)
    const coupon = idx >= 0 ? this.data.usableCoupons[idx] : null
    const couponId = coupon ? coupon.id : null
    this.setData({
      selectedCouponId: couponId,
      payType: this.data.payType === 'period_card' ? 'wechat' : this.data.payType,
      selectedCardId: null,
    })
    this.refreshPrice(couponId)
  },

  async refreshPrice(couponId) {
    if (this.data.payType === 'period_card') return
    const body = {
      store_id: Number(this.data.storeId),
      bill_type: this.data.billType,
      start_time: this.data.startTime,
      seat_id: Number(this.data.seatId),
      end_time: this.data.endTime,
    }
    if (couponId) body.coupon_id = couponId
    try {
      const preview = await request({ url: '/reservation/preview', method: 'POST', data: body })
      this.setData({
        price: preview.final_price,
        discountPrice: preview.discount_price || 0,
        originalPrice: preview.original_price,
      })
    } catch (e) {
      wx.showToast({ title: formatRequestError(e), icon: 'none' })
    }
  },

  async submitOrder() {
    if (this._submitting) return
    this._submitting = true
    this._payCompleted = false
    this.setData({ submitting: true })
    wx.showLoading({ title: '提交中' })
    try {
      const body = {
        store_id: Number(this.data.storeId),
        bill_type: this.data.billType,
        start_time: this.data.startTime,
        seat_id: Number(this.data.seatId),
        end_time: this.data.endTime,
      }
      if (this.data.selectedCouponId && this.data.payType !== 'period_card') {
        body.coupon_id = this.data.selectedCouponId
      }

      const created = await request({
        url: '/reservation/create',
        method: 'POST',
        data: body,
      })
      this.setData({ orderNo: created.order_no, reservationId: created.id })

      const payBody = {
        order_no: created.order_no,
        pay_type: this.data.payType,
      }
      if (this.data.payType === 'period_card') {
        if (!this.data.selectedCardId) {
          throw new Error('请选择期限卡')
        }
        payBody.period_card_id = this.data.selectedCardId
      } else if (this.data.selectedCouponId) {
        payBody.coupon_id = this.data.selectedCouponId
      }

      const payRes = await request({
        url: '/reservation/pay',
        method: 'POST',
        data: payBody,
      })

      if (this.data.payType === 'wechat') {
        await completeWechatPay(payRes.wechat_pay, () =>
          request({
            url: `/reservation/${created.id}/mock-pay${this.data.selectedCouponId ? '?coupon_id=' + this.data.selectedCouponId : ''}`,
            method: 'POST',
          })
        )
        await ensureReservationPaid(created.id, payRes.wechat_pay)
      } else if (this.data.payType === 'period_card') {
        const paid = await request({
          url: `/reservation/${created.id}`,
          silent: true,
          force: true,
        })
        if (!paid || paid.pay_status !== 1) {
          throw new Error('期限卡支付未完成，请重试')
        }
      }

      this._payCompleted = true
      invalidateCache('/reservation/')
      invalidateCache('/user/cards')
      wx.setStorageSync('checkin_selected_id', created.id)

      wx.hideLoading()
      wx.showToast({ title: '预约成功', icon: 'success' })
      setTimeout(() => wx.switchTab({ url: '/pages/checkin/index' }), 1200)
    } catch (e) {
      wx.hideLoading()
      if (this.data.reservationId && !this._payCompleted) {
        request({
          url: `/reservation/${this.data.reservationId}/cancel`,
          method: 'POST',
          silent: true,
        }).catch(() => {})
        this.setData({ reservationId: null, orderNo: '' })
      }
      wx.showToast({ title: formatRequestError(e), icon: 'none' })
    } finally {
      this._submitting = false
      this.setData({ submitting: false })
    }
  },
})
