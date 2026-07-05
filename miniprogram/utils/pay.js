const { isDevEnv } = require('../config')

function isMockPrepay(wechatPay) {
  return wechatPay && String(wechatPay.package || '').includes('mock_prepay')
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

/**
 * 微信支付客户端成功后，等待服务端确认 pay_status=1。
 * mock 预支付走 mock-pay，已在 completeWechatPay 内完成。
 */
async function ensureReservationPaid(reservationId, wechatPay) {
  const { request } = require('./request')

  if (isMockPrepay(wechatPay)) {
    const row = await request({
      url: `/reservation/${reservationId}`,
      silent: true,
      force: true,
    })
    if (!row || row.pay_status !== 1) {
      throw new Error('支付未完成，请稍后在「我的订单」查看')
    }
    return row
  }

  const attempts = 24
  for (let i = 0; i < attempts; i += 1) {
    try {
      return await request({
        url: `/reservation/${reservationId}/confirm-pay`,
        method: 'POST',
        silent: true,
      })
    } catch (e) {
      if (i === attempts - 1) {
        throw new Error('支付确认中，请稍后在「我的订单」查看或下拉刷新')
      }
      await sleep(500)
    }
  }
  throw new Error('支付确认超时')
}

/**
 * 完成微信支付；mock 预支付仅在 develop 环境可用。
 */
function completeWechatPay(wechatPay, mockRequest) {
  if (!wechatPay) return Promise.resolve()

  if (isMockPrepay(wechatPay)) {
    if (!isDevEnv()) {
      return Promise.reject(new Error('支付服务未配置，请联系店长'))
    }
    if (typeof mockRequest === 'function') {
      return mockRequest()
    }
    return Promise.resolve()
  }

  return new Promise((resolve, reject) => {
    wx.requestPayment({
      timeStamp: wechatPay.timeStamp,
      nonceStr: wechatPay.nonceStr,
      package: wechatPay.package,
      signType: wechatPay.signType || 'RSA',
      paySign: wechatPay.paySign,
      success: resolve,
      fail: (err) => reject(new Error(err.errMsg || '支付取消')),
    })
  })
}

module.exports = { isMockPrepay, completeWechatPay, ensureReservationPaid }
