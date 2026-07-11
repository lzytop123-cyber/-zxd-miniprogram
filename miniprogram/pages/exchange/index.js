const { request } = require('../../utils/request')
const routes = require('../../utils/routes')

Page({
  data: {
    platform: 'meituan',
    platformLabel: '美团',
    code: '',
    redeemPayload: '',
    scanReady: false,
    storeId: null,
    loading: false,
    scanning: false,
  },

  onLoad(options) {
    this._applyPlatform(options.platform || 'meituan', options.storeId || null)
  },

  onPlatformTap(e) {
    const platform = e.currentTarget.dataset.platform
    if (!platform || platform === this.data.platform) return
    this._applyPlatform(platform, this.data.storeId)
  },

  _applyPlatform(platform, storeId) {
    const platformLabel = platform === 'douyin' ? '抖音' : '美团'
    this.setData({
      platform,
      platformLabel,
      storeId: storeId || null,
      code: '',
      redeemPayload: '',
      scanReady: false,
    })
    wx.setNavigationBarTitle({ title: `${platformLabel}团购兑换` })
  },

  onInput(e) {
    this.setData({
      code: e.detail.value.trim(),
      redeemPayload: '',
      scanReady: false,
    })
  },

  _applyScanResult(res) {
    const { fillCodeFromScanResult } = require('./utils/voucherScan')
    const parsed = fillCodeFromScanResult(res, { platform: this.data.platform })
    if (!parsed.ok) {
      wx.showToast({ title: parsed.message, icon: 'none', duration: 2500 })
      return false
    }
    if (parsed.isDouyinScan) {
      this.setData({
        redeemPayload: parsed.code,
        code: '已扫码，点击立即兑换',
        scanReady: true,
      })
      wx.showToast({ title: '抖音券已识别', icon: 'success' })
      return true
    }
    this.setData({
      code: parsed.code,
      redeemPayload: '',
      scanReady: false,
    })
    wx.showToast({ title: '券码已填入', icon: 'success' })
    return true
  },

  async onScanTap() {
    if (this.data.loading || this.data.scanning) return
    this.setData({ scanning: true })
    let loadingShown = false
    try {
      const { scanFromCamera } = require('./utils/voucherScan')
      wx.showLoading({ title: '正在扫码…', mask: true })
      loadingShown = true
      const res = await scanFromCamera()
      this._applyScanResult(res)
    } catch (e) {
      const msg = e.errMsg || e.message || ''
      if (msg.includes('cancel') || msg.includes('fail cancel')) return
      wx.showToast({ title: '扫码失败，请对准抖音券二维码', icon: 'none', duration: 2500 })
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

  _resolveSubmitCode(forcedCode) {
    if (typeof forcedCode === 'string' && forcedCode.trim()) return forcedCode.trim()
    if (this.data.redeemPayload) return this.data.redeemPayload.trim()
    const manual = (this.data.code || '').trim()
    if (manual === '已扫码，点击立即兑换') return this.data.redeemPayload.trim()
    return manual
  },

  async submit(forcedCode) {
    const code = this._resolveSubmitCode(forcedCode)
    if (!code || code.length < 6) {
      wx.showToast({
        title: this.data.platform === 'douyin' ? '请先扫码或输入券号' : '请输入有效券码',
        icon: 'none',
      })
      return
    }
    const { platform, storeId } = this.data
    this.setData({ loading: true })
    wx.showLoading({ title: '连接核销中…', mask: true })
    try {
      let result
      if (platform === 'douyin') {
        result = await request({
          url: '/exchange/douyin',
          method: 'POST',
          data: { code, store_id: storeId || undefined },
          silent: true,
        })
      } else {
        let reqUrl = `/exchange/meituan/${encodeURIComponent(code)}`
        if (storeId) reqUrl += `?store_id=${Number(storeId)}`
        result = await request({ url: reqUrl, method: 'POST', silent: true })
      }
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
