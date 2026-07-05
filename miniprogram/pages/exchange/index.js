const { request } = require('../../utils/request')
const routes = require('../../utils/routes')

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
    const platformLabel = platform === 'douyin' ? '抖音' : '美团'
    this.setData({
      platform,
      platformLabel,
      storeId: options.storeId || null,
    })
    wx.setNavigationBarTitle({ title: `${platformLabel}团购兑换` })
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
    wx.showToast({ title: '券码已填入', icon: 'success' })
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
            : '未识别到有效券码，请重试或使用相机扫码',
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
      const { pickFromAlbumAndDecode } = require('./utils/voucherScan')
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
      wx.showToast({ title: '扫码失败', icon: 'none' })
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
      const lines = [result.card_name || '期限卡']
      if (result.validity_range) {
        lines.push(`卡面效期 ${result.validity_range}`)
      } else if (result.start_date && result.end_date) {
        lines.push(`卡面效期 ${result.start_date} ~ ${result.end_date}`)
      } else if (result.end_date) {
        lines.push(`卡面效期至 ${result.end_date}`)
      }
      if (result.remaining_hours != null) {
        lines.push(`含 ${result.remaining_hours} 小时`)
      } else if (result.remaining_sessions != null) {
        lines.push(`含 ${result.remaining_sessions} 次`)
      }
      wx.showModal({
        title: '兑换成功',
        content: lines.join('\n'),
        showCancel: false,
        success: () => {
          const { invalidateCache } = require('../../utils/request')
          invalidateCache('/user/cards')
          wx.switchTab({ url: '/pages/packages/index' })
        },
      })
    } catch (e) {
      wx.hideLoading()
      const msg = e.detail || e.message || '兑换失败'
      if (msg.includes('dealId') || msg.includes('未配置')) {
        wx.showModal({
          title: '待配置团购',
          content: `${msg}\n\n该券未被核销，请联系店长配置后再试`,
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
