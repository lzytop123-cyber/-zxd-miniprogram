const { request } = require('../../utils/request')

Page({
  data: {
    platform: 'meituan',
    platformLabel: '美团',
    code: '',
    storeId: null,
    loading: false,
  },

  onLoad(options) {
    const platform = options.platform || 'meituan'
    this.setData({
      platform,
      platformLabel: platform === 'douyin' ? '抖音' : '美团',
      storeId: options.storeId || null,
    })
    wx.setNavigationBarTitle({ title: `${platform === 'douyin' ? '抖音' : '美团'}兑换` })
  },

  onInput(e) {
    this.setData({ code: e.detail.value.trim() })
  },

  async submit() {
    const { code, platform, storeId } = this.data
    if (!code || code.length < 6) {
      wx.showToast({ title: '请输入有效券码', icon: 'none' })
      return
    }
    this.setData({ loading: true })
    wx.showLoading({ title: '兑换中' })
    try {
      const path = platform === 'douyin' ? '/exchange/douyin' : '/exchange/meituan'
      let reqUrl = `${path}/${encodeURIComponent(code)}`
      if (storeId) reqUrl += `?store_id=${Number(storeId)}`
      const result = await request({ url: reqUrl, method: 'POST', silent: true })
      wx.hideLoading()
      wx.showModal({
        title: '兑换成功',
        content: `已获得：${result.card_name || '期限卡'}`,
        showCancel: false,
        success: () => wx.navigateTo({ url: '/pages/profile/cards' }),
      })
    } catch (e) {
      wx.hideLoading()
      const msg = e.detail || e.message || '兑换失败'
      if (msg.includes('待配置') || msg.includes('dealId=')) {
        wx.showModal({
          title: '暂无法兑换',
          content: `${msg}\n\n您的券未被核销，管理员配置完成后请再试一次。`,
          showCancel: false,
        })
      } else {
        wx.showToast({ title: msg, icon: 'none', duration: 3000 })
      }
    } finally {
      this.setData({ loading: false })
    }
  },

  goRecords() {
    wx.navigateTo({ url: '/pages/exchange/records' })
  },
})
