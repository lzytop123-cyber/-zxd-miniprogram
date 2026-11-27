const { request, invalidateCache } = require('../../utils/request')
const auth = require('../../utils/auth')
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
    resultTitle: '',
    resultLines: [],
    lastRedeemedBillType: 'hourly',
    showSuccessModal: false,
    errorMsg: '',
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
      resultTitle: '',
      resultLines: [],
      showSuccessModal: false,
      errorMsg: '',
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
    try {
      wx.setStorageSync('lastSelectedStoreId', store.id)
    } catch (_) {}
    this.setData({
      storeId: store.id,
      storeName: store.name,
      storeIndex: idx,
      storePicked: true,
      errorMsg: '',
    })
  },

  onInput(e) {
    this.setData({ code: e.detail.value.trim(), errorMsg: '' })
  },

  clearCode() {
    this.setData({ code: '', errorMsg: '' })
  },

  pasteCode() {
    wx.getClipboardData({
      success: (res) => {
        const text = String((res && res.data) || '').trim()
        if (!text) {
          wx.showToast({ title: '剪贴板为空', icon: 'none' })
          return
        }
        this.setData({ code: text, errorMsg: '' })
      },
      fail: () => {
        wx.showToast({ title: '无法读取剪贴板', icon: 'none' })
      },
    })
  },

  _applyScanResult(res) {
    const { fillCodeFromScanResult } = require('./utils/voucherScan')
    const parsed = fillCodeFromScanResult(res, { platform: this.data.platform })
    if (!parsed.ok) {
      wx.showToast({ title: parsed.message, icon: 'none', duration: 2500 })
      return false
    }
    this.setData({ code: parsed.code, errorMsg: '' })
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
    if (this.data.loading || this._confirming) return
    const inputCode = typeof forcedCode === 'string' ? forcedCode.trim() : (this.data.code || '').trim()
    if (!inputCode || inputCode.length < 6) {
      wx.showToast({ title: '请输入有效券码', icon: 'none' })
      return
    }
    const { platform, platformLabel, storeId, storeName, storePicked } = this.data
    if (!storeId || !storePicked) {
      wx.showToast({ title: '请先选择门店后再兑换', icon: 'none' })
      return
    }
    if (!auth.isLoggedIn()) {
      auth.requireLogin(routes.buildExchangeUrl({ platform, storeId }))
      return
    }
    this._confirming = true
    let confirmed = false
    try {
      confirmed = await new Promise((resolve) => {
        wx.showModal({
          title: '确认核销',
          content: `将核销到「${storeName || '所选门店'}」。\n核销后${platformLabel}券即作废，请确认门店无误。`,
          confirmText: '确认核销',
          confirmColor: '#2D6A4F',
          success: (res) => resolve(!!res.confirm),
          fail: () => resolve(false),
        })
      })
    } finally {
      this._confirming = false
    }
    if (!confirmed) return

    let code = inputCode
    if (platform === 'douyin') {
      const { toDouyinSubmitCode } = require('./utils/voucherScan')
      code = toDouyinSubmitCode(inputCode)
    }
    this.setData({
      loading: true,
      code: inputCode,
      resultTitle: '',
      resultLines: [],
      showSuccessModal: false,
      errorMsg: '',
    })

    try {
      let result
      if (platform === 'douyin') {
        result = await request({
          url: '/exchange/douyin',
          method: 'POST',
          data: { code, store_id: Number(storeId) },
          silent: true,
          timeout: 60000,
        })
      } else {
        const reqUrl = `/exchange/meituan/${encodeURIComponent(code)}?store_id=${Number(storeId)}`
        result = await request({ url: reqUrl, method: 'POST', silent: true, timeout: 60000 })
      }
      const payload = result && typeof result === 'object' ? result : {}
      const lines = [`已核销到「${storeName || '所选门店'}」`, payload.card_name || '期限卡']
      if (payload.validity_range) {
        lines.push(`卡面效期 ${payload.validity_range}`)
      } else if (payload.start_date && payload.end_date) {
        lines.push(`卡面效期 ${payload.start_date} ~ ${payload.end_date}`)
      } else if (payload.end_date) {
        lines.push(`卡面效期至 ${payload.end_date}`)
      }
      if (payload.remaining_hours != null) {
        lines.push(`含 ${payload.remaining_hours} 小时`)
      } else if (payload.remaining_sessions != null) {
        lines.push(`含 ${payload.remaining_sessions} 次`)
      }
      const billType =
        payload.card_type === 'night_monthly'
          ? 'night'
          : payload.card_type || 'hourly'

      invalidateCache('/user/cards')
      invalidateCache('/exchange/records')
      this.setData({
        loading: false,
        code: '',
        resultTitle: '核销成功',
        resultLines: lines,
        lastRedeemedBillType: billType,
        showSuccessModal: true,
        errorMsg: '',
      })
      wx.vibrateShort({ type: 'medium' })
    } catch (e) {
      const rawMsg = e.detail || e.message || '兑换失败，请稍后重试'
      let friendlyMsg = rawMsg
      if (rawMsg.includes('dealId') || rawMsg.includes('未配置')) {
        friendlyMsg = '该团购商品暂未完成门店配置，您的券未被核销，请联系店长处理后再试。'
      } else if (rawMsg.includes('仅适用于') || rawMsg.includes('不适用于当前门店')) {
        friendlyMsg = `${rawMsg}（该券未被核销，请切换上方门店后重试）`
      }
      this.setData({ loading: false, errorMsg: friendlyMsg })
      wx.showToast({ title: friendlyMsg.slice(0, 22), icon: 'none', duration: 2800 })
    } finally {
      if (this.data.loading) this.setData({ loading: false })
    }
  },

  closeSuccessModal() {
    this.setData({ showSuccessModal: false })
  },

  goBookAfterSuccess() {
    const { storeId, lastRedeemedBillType } = this.data
    this.setData({ showSuccessModal: false })
    wx.navigateTo({
      url: `${routes.bookingIndex}?storeId=${storeId}&billType=${lastRedeemedBillType || 'hourly'}`,
      fail: () => wx.navigateTo({ url: routes.profileCards }),
    })
  },

  goMyCards() {
    this.setData({ showSuccessModal: false })
    wx.navigateTo({
      url: routes.profileCards,
      fail: () => wx.switchTab({ url: '/pages/profile/index' }),
    })
  },

  goRecords() {
    wx.navigateTo({ url: routes.exchangeRecords })
  },
})
