const { isDevEnv } = require('../config')

function isMockPrepay(wechatPay) {
  return wechatPay && String(wechatPay.package || '').includes('mock_prepay')
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

module.exports = { isMockPrepay, completeWechatPay }
