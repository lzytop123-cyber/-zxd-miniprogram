const { request } = require('../../utils/request')
const routes = require('../../utils/routes')
const { pickExchangeStore } = require('./utils/storePick')

Page({
  data: {
    platform: 'meituan',
    platformLabel: '美团',
    code: '',
    stores: [],
    storeId: null,
    storeName: '',
    storeIndex: 0,
    storePicked: false,
    storesLoading: true,
    loading: false,
    scanning: false,
  },

  onLoad(options) {
    const preferredId = options.storeId || options.store_id || null
    this._applyPlatform(options.platform || 'meituan', preferredId)
    this.loadStores(preferredId)
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
      storeId: storeId ? Number(storeId) : this.data.storeId,
      code: '',
    })
    wx.setNavigationBarTitle({ title: `${platformLabel}团购兑换` })
  },

  loadStores(preferredId) {
    this.setData({ storesLoading: true })
    return request({ url: '/store/list', silent: true, force: true })
      .then((list) => {
        const stores = list || []
        const picked = pickExchangeStore(stores, preferredId || this.data.storeId)
        this.setData({
          stores,
          storeId: picked.storeId,
          storeName: picked.storeName,
          storeIndex: picked.storeIndex,
          storePicked: !!picked.storePicked,
          storesLoading: false,
        })
      })
      .catch(() => {
        this.setData({ storesLoading: false })
        wx.showToast({ title: '加载门店失败', icon: 'none' })
      })
  },

  onStoreChange(e) {
    const idx = Number(e.detail.value)
    const store = this.data.stores[idx]
    if (!store) return
    this.setData({
      storeId: store.id,
      storeName: store.name,
      storeIndex: idx,
      storePicked: true,
    })
  },

  onInput(e) {
    this.setData({ code: e.detail.value.trim() })
  },

  _applyScanResult(res) {
    const { fillCodeFromScanResult } = require('./utils/voucherScan')
    const parsed = fillCodeFromScanResult(res, { platform: this.data.platform })
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
    try {
      const { pickAndScanVoucher } = require('./utils/voucherScan')
      const res = await pickAndScanVoucher()
      this._applyScanResult(res)
    } catch (e) {
      const msg = e.errMsg || e.message || ''
      if (msg.includes('cancel') || msg.includes('fail cancel')) return
      wx.showToast({ title: '扫码失败', icon: 'none' })
    } finally {
      this.setData({ scanning: false })
    }
  },

  onSubmitTap() {
    this.submit()
  },

  async submit(forcedCode) {
    const inputCode = typeof forcedCode === 'string' ? forcedCode.trim() : (this.data.code || '').trim()
    if (!inputCode || inputCode.length < 6) {
      wx.showToast({ title: '请输入有效券码', icon: 'none' })
      return
    }
    const { platform, storeId, storeName, storePicked } = this.data
    if (!storeId || !storePicked) {
      wx.showToast({ title: '请先选择门店后再兑换', icon: 'none' })
      return
    }
    const confirmed = await new Promise((resolve) => {
      wx.showModal({
        title: '确认核销',
        content: `将核销到「${storeName || '所选门店'}」。\n核销后美团券即作废，请确认门店无误。`,
        confirmText: '确认核销',
        confirmColor: '#2D6A4F',
        success: (res) => resolve(!!res.confirm),
        fail: () => resolve(false),
      })
    })
    if (!confirmed) return

    let code = inputCode
    if (platform === 'douyin') {
      const { toDouyinSubmitCode } = require('./utils/voucherScan')
      code = toDouyinSubmitCode(inputCode)
    }
    this.setData({ loading: true, code: inputCode })
    wx.showLoading({ title: '连接核销中…', mask: true })
    try {
      let result
      if (platform === 'douyin') {
        result = await request({
          url: '/exchange/douyin',
          method: 'POST',
          data: { code, store_id: Number(storeId) },
          silent: true,
        })
      } else {
        const reqUrl = `/exchange/meituan/${encodeURIComponent(code)}?store_id=${Number(storeId)}`
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
        confirmText: '去选座预约',
        cancelText: '查看卡包',
        showCancel: true,
        confirmColor: '#2D6A4F',
        success: (res) => {
          const { invalidateCache } = require('../../utils/request')
          invalidateCache('/user/cards')
          if (res.confirm) {
            const billType =
              result.card_type === 'night_monthly'
                ? 'night'
                : result.card_type || 'hourly'
            wx.navigateTo({
              url: `${routes.bookingIndex}?storeId=${storeId}&billType=${billType}`,
              fail: () => wx.navigateTo({ url: routes.profileCards }),
            })
          } else {
            wx.navigateTo({
              url: routes.profileCards,
              fail: () => wx.switchTab({ url: '/pages/profile/index' }),
            })
          }
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
