const { request } = require('../../utils/request')
const { getLayout } = require('../../utils/seat-layout')
const { hourlyAllowsPartialUse } = require('../../utils/cardDisplay')

const BILL_LABELS = { hourly: '按小时', daily: '天卡', weekly: '周卡', session: '次卡', monthly: '月卡', quarterly: '季卡', night: '夜读' }

const CARD_BILL_MAP = {
  hourly: ['hourly'],
  daily: ['daily'],
  weekly: ['weekly'],
  session: ['session'],
  monthly: ['monthly'],
  quarterly: ['quarterly'],
  night: ['night', 'night_monthly'],
}

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

function formatDate(iso) {
  const d = new Date(iso)
  const pad = (n) => (n < 10 ? '0' + n : '' + n)
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
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
  },

  onLoad(options) {
    const layout = getLayout()
    const display = layout.seatDisplay({ seat_code: options.seatCode || '' })
    const seatDisplay = display.mapLabel
      ? `${display.mapLabel} 号 · ${display.zoneName}`
      : (options.seatCode || '-')
    this.setData({
      storeId: options.storeId,
      startTime: decodeURIComponent(options.start),
      endTime: decodeURIComponent(options.end),
      seatId: options.seatId,
      seatCode: options.seatCode,
      seatDisplay,
      originalPrice: options.price,
      price: options.price,
      billType: options.billType || 'hourly',
      billTypeLabel: BILL_LABELS[options.billType] || '按小时',
      startDisplay: formatDate(decodeURIComponent(options.start)),
      endDisplay: formatDate(decodeURIComponent(options.end)),
      sessionDays: options.billType === 'session'
        ? countSessionDays(decodeURIComponent(options.start), decodeURIComponent(options.end))
        : 0,
    })
  },

  onShow() {
    this.loadPayOptions()
  },

  async loadPayOptions() {
    try {
      const [cards, coupons] = await Promise.all([
        request({ url: '/user/cards' }),
        request({ url: '/user/coupons' }),
      ])
      const storeId = Number(this.data.storeId)
      const billType = this.data.billType
      const bookingH = billType === 'hourly' ? bookingHours(this.data.startTime, this.data.endTime) : 0
      const allowedTypes = CARD_BILL_MAP[billType] || [billType]
      const usableCards = (cards || []).filter((c) => {
        if (c.store_id && c.store_id !== storeId) return false
        if (c.card_type === 'hourly' && !(c.remaining_hours > 0)) return false
        if (c.card_type === 'session' && !(c.remaining_sessions > 0)) return false
        if (c.card_type === 'hourly') {
          if (billType !== 'hourly') return false
          if (!hourlyAllowsPartialUse(c)) {
            return Math.abs(bookingH - Number(c.remaining_hours)) < 0.05
          }
          return bookingH <= Number(c.remaining_hours)
        }
        if (c.card_type === 'session') return billType === 'session'
        if (c.card_type === 'night_monthly') return billType === 'night'
        if (c.card_type === 'daily') return billType === 'daily'
        if (c.card_type === 'weekly') return billType === 'weekly'
        if (c.card_type === 'monthly') return billType === 'monthly'
        if (c.card_type === 'quarterly') return billType === 'quarterly'
        return allowedTypes.includes(c.card_type)
      })
      const originalPrice = Number(this.data.originalPrice)
      const usableCoupons = (coupons || []).filter(
        (c) => c.status === 0 && originalPrice >= (c.min_amount || 0)
      )
      const patch = { cards, usableCards, coupons, usableCoupons }
      if (
        usableCards.length
        && this.data.payType === 'wechat'
        && !this.data.orderNo
      ) {
        const cur = usableCards[0]
        patch.payType = 'period_card'
        patch.selectedCardId = cur.id
        patch.selectedCardName = cur.card_name || cur.card_type
        patch.price = 0
        patch.discountPrice = 0
      } else if (this.data.payType === 'period_card' && usableCards.length) {
        const cur = usableCards.find((c) => c.id === this.data.selectedCardId) || usableCards[0]
        patch.selectedCardId = cur.id
        patch.selectedCardName = cur.card_name || cur.card_type
        patch.price = 0
        patch.discountPrice = 0
      } else if (!usableCards.length) {
        patch.selectedCardId = null
        patch.selectedCardName = ''
      }
      this.setData(patch)
    } catch (e) {
      // ignore
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
      wx.showToast({ title: e.message || '优惠券不可用', icon: 'none' })
    }
  },

  async submitOrder() {
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
        const wp = payRes.wechat_pay
        if (wp && wp.package && wp.package.includes('mock_prepay')) {
          const mockUrl = `/reservation/${created.id}/mock-pay${this.data.selectedCouponId ? '?coupon_id=' + this.data.selectedCouponId : ''}`
          await request({ url: mockUrl, method: 'POST' })
        } else if (wp) {
          await new Promise((resolve, reject) => {
            wx.requestPayment({
              timeStamp: wp.timeStamp,
              nonceStr: wp.nonceStr,
              package: wp.package,
              signType: wp.signType || 'RSA',
              paySign: wp.paySign,
              success: resolve,
              fail: (err) => reject(new Error(err.errMsg || '支付取消')),
            })
          })
        }
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
      }
      wx.showToast({ title: e.detail || e.message || '下单失败', icon: 'none' })
    }
  },
})
