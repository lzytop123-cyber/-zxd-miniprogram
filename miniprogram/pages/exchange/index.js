const { request } = require('../../utils/request')

Page({
  data: {
    platform: 'meituan',
    platformLabel: '美团',
    code: '',
    storeId: null,
    loading: false,
    scanning: false,
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

  _applyScanResult(res) {
    const { fillCodeFromScanResult } = require('../../utils/voucherScan')
    const parsed = fillCodeFromScanResult(res)
    if (!parsed.ok) {
      wx.showToast({ title: parsed.message, icon: 'none', duration: 2500 })
      return false
    }
    this.setData({ code: parsed.code })
    wx.showToast({ title: '券码已填入', icon: 'success' })
    return true
  },

  async onScanTap() {
    if (this.data.loading || this.data.scanning) return
    this.setData({ scanning: true })
    let loadingShown = false
    try {
      const { pickAndScanVoucher } = require('../../utils/voucherScan')
      const res = await pickAndScanVoucher({
        onAlbumStart: () => {
          loadingShown = true
          wx.showLoading({ title: '识别券码…', mask: true })
        },
      })
      this._applyScanResult(res)
    } catch (e) {
      const msg = e.errMsg || e.message || ''
      if (msg.includes('cancel') || msg.includes('fail cancel')) return
      if (msg.includes('未识别') || msg.includes('条形码')) {
        wx.showModal({
          title: '识别失败',
          content: msg.includes('条形码')
            ? msg
            : '相册图片未识别到二维码。若券上是条形码，请选择「相机扫码」。',
          showCancel: false,
        })
        return
      }
      wx.showToast({ title: '扫码失败', icon: 'none' })
    } finally {
      if (loadingShown) wx.hideLoading()
      this.setData({ scanning: false })
    }
  },

  async onAlbumScanTap() {
    if (this.data.loading || this.data.scanning) return
    this.setData({ scanning: true })
    wx.showLoading({ title: '识别券码…', mask: true })
    try {
      const { pickFromAlbumAndDecode } = require('../../utils/voucherScan')
      const res = await pickFromAlbumAndDecode()
      this._applyScanResult(res)
    } catch (e) {
      const msg = e.errMsg || e.message || ''
      if (msg.includes('cancel') || msg.includes('fail cancel')) return
      if (msg.includes('未识别') || msg.includes('条形码')) {
        wx.showModal({
          title: '识别失败',
          content: msg,
          showCancel: false,
        })
        return
      }
      wx.showToast({ title: '识别失败', icon: 'none' })
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
      wx.showToast({ title: '请输入有效券码', icon: 'none' })
      return
    }
    const { platform, storeId } = this.data
    this.setData({ loading: true, code })
    wx.showLoading({ title: '连接核销中…', mask: true })
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
        success: () => wx.switchTab({ url: '/pages/packages/index' }),
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
