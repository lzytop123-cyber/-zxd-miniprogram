const { request } = require('../../utils/request')
const routes = require('../../utils/routes')

Page({
  data: {
    platform: 'meituan',
    platformLabel: '??',
    code: '',
    storeId: null,
    loading: false,
    scanning: false,
  },

  onLoad(options) {
    const platform = options.platform || 'meituan'
    this.setData({
      platform,
      platformLabel: platform === 'douyin' ? '??' : '??',
      storeId: options.storeId || null,
    })
    wx.setNavigationBarTitle({ title: `${platform === 'douyin' ? '??' : '??'}??` })
  },

  onInput(e) {
    this.setData({ code: e.detail.value.trim() })
  },

  _applyScanResult(res) {
    const { fillCodeFromScanResult } = require('./utils/voucherScan')
    const parsed = fillCodeFromScanResult(res)
    if (!parsed.ok) {
      wx.showToast({ title: parsed.message, icon: 'none', duration: 2500 })
      return false
    }
    this.setData({ code: parsed.code })
    wx.showToast({ title: '?????', icon: 'success' })
    return true
  },

  async onScanTap() {
    if (this.data.loading || this.data.scanning) return
    this.setData({ scanning: true })
    let loadingShown = false
    try {
      const { pickAndScanVoucher } = require('./utils/voucherScan')
      const res = await pickAndScanVoucher({
        onAlbumStart: () => {
          loadingShown = true
          wx.showLoading({ title: '?????', mask: true })
        },
      })
      this._applyScanResult(res)
    } catch (e) {
      const msg = e.errMsg || e.message || ''
      if (msg.includes('cancel') || msg.includes('fail cancel')) return
      if (msg.includes('???') || msg.includes('???')) {
        wx.showModal({
          title: '????',
          content: msg.includes('???')
            ? msg
            : '??????????????????????????????',
          showCancel: false,
        })
        return
      }
      wx.showToast({ title: '????', icon: 'none' })
    } finally {
      if (loadingShown) wx.hideLoading()
      this.setData({ scanning: false })
    }
  },

  async onAlbumScanTap() {
    if (this.data.loading || this.data.scanning) return
    this.setData({ scanning: true })
    wx.showLoading({ title: '?????', mask: true })
    try {
      const { pickFromAlbumAndDecode } = require('./utils/voucherScan')
      const res = await pickFromAlbumAndDecode()
      this._applyScanResult(res)
    } catch (e) {
      const msg = e.errMsg || e.message || ''
      if (msg.includes('cancel') || msg.includes('fail cancel')) return
      if (msg.includes('???') || msg.includes('???')) {
        wx.showModal({
          title: '????',
          content: msg,
          showCancel: false,
        })
        return
      }
      wx.showToast({ title: '????', icon: 'none' })
    } finally {
      wx.hideLoading()
      this.setData({ scanning: false })
    }
  },

  onSubmitTap() {
    this.submit()
  },

  async submit(forcedCode) {
    const code = typeof forcedCode === 'string' ? forcedCode.trim() : (this.data.code || '').trim()
    if (!code || code.length < 6) {
      wx.showToast({ title: '???????', icon: 'none' })
      return
    }
    const { platform, storeId } = this.data
    this.setData({ loading: true, code })
    wx.showLoading({ title: '??????', mask: true })
    try {
      const path = platform === 'douyin' ? '/exchange/douyin' : '/exchange/meituan'
      let reqUrl = `${path}/${encodeURIComponent(code)}`
      if (storeId) reqUrl += `?store_id=${Number(storeId)}`
      const result = await request({ url: reqUrl, method: 'POST', silent: true })
      wx.hideLoading()
      wx.showModal({
        title: '????',
        content: `????${result.card_name || '???'}`,
        showCancel: false,
        success: () => wx.switchTab({ url: '/pages/packages/index' }),
      })
    } catch (e) {
      wx.hideLoading()
      const msg = e.detail || e.message || '????'
      if (msg.includes('???') || msg.includes('dealId=')) {
        wx.showModal({
          title: '?????',
          content: `${msg}\n\n??????????????????????`,
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
    wx.navigateTo({ url: routes.exchangeRecords })
  },
})
