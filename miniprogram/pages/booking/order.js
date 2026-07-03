const { request, formatRequestError } = require('../../utils/request')
const { getLayout } = require('../../utils/seat-layout')
const { dailyPassDays, isOfficeNightMonthlyCard, OFFICE_NIGHT_BOOKING_HINT } = require('../../utils/cardDisplay')
const { completeWechatPay } = require('../../utils/pay')

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

function isUsableCard(card, ctx) {
  const {
    storeId, billType, startTime, endTime, sessionDays, bookingH,
  } = ctx
  if (card.store_id && card.store_id !== storeId) return false

  if (card.card_type === 'hourly') {
    if (billType !== 'hourly') return false
    if (!(Number(card.remaining_hours) > 0)) return false
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
    return withinCardPeriod(card, startTime, endTime)
  }

  if (card.card_type === 'daily') {
    if (billType !== 'daily') return false
    const span = dailyPassDays(card)
    const start = startTime.slice(0, 10)
    const end = endTime.slice(0, 10)
    if (span > 1) {
      return start === card.start_date && end === card.end_date
    }
    if (start !== end) return false
    return withinCardPeriod(card, startTime, endTime)
  }

  if (card.card_type === 'weekly') {
    return billType === 'weekly' && withinCardPeriod(card, startTime, endTime)
  }
  if (card.card_type === 'monthly') {
    return billType === 'monthly' && withinCardPeriod(card, startTime, endTime)
  }
  if (card.card_type === 'quarterly') {
    return billType === 'quarterly' && withinCardPeriod(card, startTime, endTime)
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
    submitting: false,
  },

  onLoad(options) {
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
      }
      if (this.data.payType === 'period_card') {
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
      }

      wx.hideLoading()
      wx.showToast({ title: '预约成功', icon: 'success' })
      setTimeout(() => wx.switchTab({ url: '/pages/checkin/index' }), 1200)
    } catch (e) {
      wx.hideLoading()
      if (this.data.reservationId) {
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
