const { request } = require('../../utils/request')
const auth = require('../../utils/auth')
const routes = require('../../utils/routes')
const { handleTabScroll } = require('../../utils/tabbar')
const { syncTabBar } = require('../../utils/features')
const { enableShareMenu, shareAppMessage, shareTimeline } = require('../../utils/share')
const {
  computeCanOpen,
  getOpenWindowHint,
  mapBleOpenFailure,
} = require('../../utils/bleUnlock')

const CHECKIN_SELECT_KEY = 'checkin_selected_id'

// 从通通锁插件成功回包中尽力提取真实电量（字段名随插件版本而异），无有效值返回 null。
// 有真实值时上报服务端记录，避免用模拟递减导致电量告警失真。
function pickBatteryLevel(result) {
  if (!result || typeof result !== 'object') return null
  const candidates = [result.battery, result.electricQuantity, result.power, result.electric]
  for (const v of candidates) {
    if (v === null || v === undefined || v === '') continue
    const n = Number(v)
    if (Number.isFinite(n) && n >= 0 && n <= 100) return Math.round(n)
  }
  return null
}

let plugin = null
let bleOperationPending = false

function detectPlugin() {
  try {
    plugin = requirePlugin('ttlock-plugin')
    const ready = typeof plugin?.controlLock === 'function'
    if (ready) return { pluginReady: true, pluginHint: '' }
    return { pluginReady: false, pluginHint: '插件接口不可用，请检查插件版本' }
  } catch (e) {
    const msg = (e && (e.message || e.errMsg)) || '插件未加载'
    console.warn('[ttlock] requirePlugin failed:', msg)
    return { pluginReady: false, pluginHint: msg }
  }
}

function getRuntimeAppId() {
  try {
    return wx.getAccountInfoSync().miniProgram.appId || ''
  } catch (e) {
    return ''
  }
}

function formatDate(iso) {
  const d = new Date(String(iso).replace(' ', 'T'))
  const pad = (n) => (n < 10 ? '0' + n : '' + n)
  return `${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

function formatDuration(diffMs) {
  const totalMinutes = Math.max(0, Math.floor(diffMs / 60000))
  const days = Math.floor(totalMinutes / (24 * 60))
  const hours = Math.floor((totalMinutes % (24 * 60)) / 60)
  const minutes = totalMinutes % 60
  const parts = []
  if (days > 0) parts.push(`${days}天`)
  if (days > 0 || hours > 0) parts.push(`${hours}小时`)
  parts.push(`${minutes}分`)
  return parts.join('')
}

/** 未开始：展示预约总时长；已开始：展示距结束剩余。 */
function formatReservationDuration(reservation, now = new Date()) {
  const start = parseTime(reservation.start_time)
  const end = parseTime(reservation.end_time)
  if (end <= now) {
    return { label: '剩余时长', text: '已结束' }
  }
  if (start > now) {
    const spanMs = end - start
    return { label: '预约时长', text: `共 ${formatDuration(spanMs)}` }
  }
  return { label: '剩余时长', text: `剩余 ${formatDuration(end - now)}` }
}

function parseTime(iso) {
  return new Date(String(iso).replace(' ', 'T'))
}

function canChangeSeatFor(reservation, now = new Date()) {
  if (!reservation) return false
  if (reservation.pay_status !== 1) return false
  if (![0, 1].includes(reservation.status)) return false
  return parseTime(reservation.end_time) > now
}

Page({
  data: {
    pageLoading: true,
    loadError: '',
    activeList: [],
    selectedId: null,
    reservation: null,
    endDisplay: '',
    startDisplay: '',
    checkInDisplay: '',
    statusLabel: '',
    statusHint: '',
    durationLabel: '剩余时长',
    countdown: '',
    canOpen: false,
    canChangeSeat: false,
    openWindowHint: '',
    lockData: '',
    lockName: '',
    pluginReady: false,
    pluginHint: '',
    runtimeAppId: '',
    opening: false,
    lastOpenError: '',
  },

  onShareAppMessage() {
    return shareAppMessage({ title: '知行岛自习空间 · 入座开门' })
  },

  onShareTimeline() {
    return shareTimeline({ title: '知行岛自习空间 · 入座开门' })
  },

  onShow() {
    enableShareMenu()
    syncTabBar(this, '/pages/checkin/index')
    this._tabbarLastTop = 0
    const pluginState = detectPlugin()
    const runtimeAppId = getRuntimeAppId()
    const preferred = wx.getStorageSync(CHECKIN_SELECT_KEY)
    if (preferred) {
      wx.removeStorageSync(CHECKIN_SELECT_KEY)
      this._preferredId = Number(preferred)
    }
    this.setData({ ...pluginState, runtimeAppId })
    // 入座页需实时数据，避免缓存空列表导致与订单页不一致
    this.loadActive({ silent: true, force: true })
  },

  onPullDownRefresh() {
    this.loadActive({ force: true }).finally(() => wx.stopPullDownRefresh())
  },

  onPageScroll(e) {
    handleTabScroll(this, e.scrollTop)
  },

  loadActive(options = {}) {
    const { force = false, silent = false } = options
    const requestId = (this._activeRequestId || 0) + 1
    this._activeRequestId = requestId
    const hasList = (this.data.activeList || []).length > 0
    if (!hasList || force) {
      if (!silent || !hasList) {
        this.setData({ pageLoading: !hasList })
      }
    }
    this.setData({ loadError: '' })
    return request({ url: '/reservation/active/list', silent: true, force })
      .then((list) => {
        if (requestId !== this._activeRequestId) return
        const items = list || []
        if (!items.length) {
          this._expiredReloadFor = null
          if (this._timer) clearInterval(this._timer)
          this.setData({
            activeList: [],
            selectedId: null,
            reservation: null,
            canOpen: false,
            pageLoading: false,
            loadError: '',
          })
          return
        }

        let selectedId = this.data.selectedId
        const preferredId = this._preferredId
        if (preferredId && items.some((item) => item.id === preferredId)) {
          selectedId = preferredId
          this._preferredId = null
        } else if (!selectedId || !items.some((item) => item.id === selectedId)) {
          selectedId = items[0].id
        }

        this.setData({ activeList: items, selectedId, pageLoading: false, loadError: '' })
        const reservation = items.find((item) => item.id === selectedId) || items[0]
        this.applyReservation(reservation)
      })
      .catch(() => {
        if (requestId !== this._activeRequestId) return
        const loadError = '订单加载失败，请检查网络后重试'
        if (!hasList) {
          this.setData({
            activeList: [],
            selectedId: null,
            reservation: null,
            canOpen: false,
            pageLoading: false,
            loadError,
          })
        } else {
          this.setData({ pageLoading: false, loadError })
        }
      })
  },

  retryLoadActive() {
    return this.loadActive({ force: true })
  },

  selectReservation(e) {
    if (this._opening) return
    const id = Number(e.currentTarget.dataset.id)
    if (!id || id === this.data.selectedId) return
    const reservation = this.data.activeList.find((item) => item.id === id)
    if (!reservation) return
    this.setData({ selectedId: id })
    this.applyReservation(reservation)
  },

  applyReservation(reservation) {
    if (!reservation) return
    if (this._timer) clearInterval(this._timer)
    this._expiredReloadFor = null
    const canOpen = computeCanOpen(reservation)
    const openWindowHint = getOpenWindowHint(reservation)
    this.setData({
      reservation,
      startDisplay: formatDate(reservation.start_time),
      endDisplay: formatDate(reservation.end_time),
      checkInDisplay: reservation.check_in_time ? formatDate(reservation.check_in_time) : '',
      statusLabel: reservation.status_label || '',
      statusHint: reservation.status_hint || '',
      canOpen,
      canChangeSeat: canChangeSeatFor(reservation),
      openWindowHint,
      lastOpenError: '',
    })
    this.loadBleKey(canOpen ? reservation.id : null)
    this.startCountdown(reservation)
  },

  loadBleKey(reservationId) {
    const requestId = this._keyRequestId = (this._keyRequestId || 0) + 1
    this.setData({ lockData: '', lockName: '' })
    if (!reservationId) {
      this.setData({ lockData: '' })
      return
    }
    return request({ url: `/ble/key/${reservationId}`, force: true, silent: true })
      .then((res) => {
        if (requestId !== this._keyRequestId || this.data.reservation?.id !== reservationId) return null
        this.setData({
          lockData: res.lockData,
          lockName: res.lockName || '门店大门',
        })
        return res.lockData
      })
      .catch(() => {
        if (requestId === this._keyRequestId) this.setData({ lockData: '' })
        return null
      })
  },

  startCountdown(reservation) {
    const tick = () => {
      const now = new Date()
      const end = parseTime(reservation.end_time)
      const ended = end <= now
      const duration = ended
        ? { label: '剩余时长', text: '已结束' }
        : formatReservationDuration(reservation, now)
      const next = {
        durationLabel: duration.label,
        countdown: duration.text,
        canOpen: ended ? false : computeCanOpen(reservation, now),
        canChangeSeat: ended ? false : canChangeSeatFor(reservation, now),
        openWindowHint: ended ? '订单已结束' : getOpenWindowHint(reservation, now),
      }
      const patch = {}
      for (const k in next) {
        if (next[k] !== this.data[k]) patch[k] = next[k]
      }
      if (Object.keys(patch).length) this.setData(patch)
      if (ended && this._expiredReloadFor !== reservation.id) {
        this._expiredReloadFor = reservation.id
        this.loadActive()
      }
    }
    tick()
    if (this._timer) clearInterval(this._timer)
    this._timer = setInterval(tick, 1000)
  },

  onUnload() {
    this._unloaded = true
    this._keyRequestId = (this._keyRequestId || 0) + 1
    if (this._timer) clearInterval(this._timer)
  },

  afterOpenSuccess(reservation, result) {
    wx.hideLoading()
    wx.showToast({ title: '门已开启', icon: 'success' })
    wx.vibrateShort()
    const data = { reservation_id: reservation.id, result: 'success' }
    const battery = pickBatteryLevel(result)
    if (battery !== null) data.battery_level = battery
    request({
      url: `/ble/checkin/${reservation.id}`,
      method: 'POST',
      data,
    }).catch(() => {
      wx.showToast({ title: '门已开，入座记录同步失败，请刷新订单', icon: 'none' })
    }).finally(() => this.loadActive())
    this._opening = false
    this.setData({ opening: false, lastOpenError: '' })
  },

  afterOpenFail(reservation, errorMsg, errorCode, mode = 'ble') {
    wx.hideLoading()
    this._opening = false
    const failure = mapBleOpenFailure({
      errorCode,
      errorMsg,
      canOpen: this.data.canOpen,
      reservation,
      mode,
    })
    this.setData({
      opening: false,
      lastOpenError: failure.content,
    })
    request({
      url: `/ble/checkin/${reservation.id}`,
      method: 'POST',
      data: {
        reservation_id: reservation.id,
        result: 'fail',
        error_code: errorCode ? String(errorCode) : '',
        error_msg: errorMsg || failure.content,
        stage: this._openStage || 'plugin',
        duration_ms: Math.max(0, Date.now() - (this._openStartedAt || Date.now())),
        client_system: this._clientSystem || '',
        plugin_version: '3.1.4',
      },
      silent: true,
    }).catch(() => {})
  },

  async openDoorBle() {
    if (!this.data.canOpen || this._opening || this.data.opening) return
    if (bleOperationPending) {
      this.setData({ lastOpenError: '上一次蓝牙操作尚未结束，请稍候；长时间无响应请联系店长。' })
      return
    }
    const reservation = this.data.reservation
    if (!reservation) return
    this._opening = true
    bleOperationPending = true
    this._openStartedAt = Date.now()
    try { this._clientSystem = wx.getSystemInfoSync().system || '' } catch (_) {}
    this.setData({ opening: true, lastOpenError: '' })
    let watchdog
    let pluginStarted = false
    try {
      this._openStage = 'key'
      wx.showLoading({ title: '准备开门钥匙…' })
      const lockData = await this.loadBleKey(reservation.id)
      if (!lockData) throw new Error('钥匙获取失败，请检查网络后重试')
      if (this._unloaded || this.data.reservation?.id !== reservation.id || !computeCanOpen(reservation)) {
        throw new Error('预约状态已变化，请刷新订单后重试')
      }
      this._openStage = 'adapter'
      await new Promise((resolve, reject) => wx.openBluetoothAdapter({ success: resolve, fail: reject }))
      const state = detectPlugin()
      this.setData(state)
      if (!state.pluginReady) throw new Error(state.pluginHint)
      if (this._unloaded || !computeCanOpen(reservation)) throw new Error('预约状态已变化，请刷新订单后重试')
      this._openStage = 'plugin'
      wx.showLoading({ title: '正在连接门锁…' })
      watchdog = setTimeout(() => {
        wx.hideLoading()
        this.setData({ lastOpenError: '门锁响应超时，开门结果尚未确认。请勿重复操作；可联系店长协助。' })
        // Do not release either guard: stopping the plugin cannot cancel an in-flight connection.
      }, 35000)
      pluginStarted = true
      const result = await plugin.controlLock({ controlAction: plugin.CONTROL_ACTION_OPEN || 3, lockData })
      clearTimeout(watchdog)
      if (result && result.errorCode === 0) {
        this.afterOpenSuccess(reservation, result)
      } else {
        throw result || new Error('蓝牙开门失败')
      }
    } catch (err) {
      clearTimeout(watchdog)
      if (pluginStarted && typeof plugin?.stopAllOperations === 'function') {
        // Only clean up after controlLock has settled, never while it may still unlock.
        try {
          const cleanup = await Promise.race([
            Promise.resolve().then(() => plugin.stopAllOperations()),
            new Promise((_, reject) => { this._cleanupTimer = setTimeout(() => reject(new Error('cleanup timeout')), 5000) }),
          ])
          if (!cleanup || cleanup.errorCode !== 0) throw new Error('cleanup failed')
        } catch (_) {
          this._cleanupFailed = true
        } finally { clearTimeout(this._cleanupTimer) }
      }
      this.afterOpenFail(reservation,
        err?.errorMsg || err?.errMsg || err?.message || '蓝牙开门失败',
        err?.errorCode ?? err?.errCode ?? '', 'ble')
      if (this._cleanupFailed) this.setData({ lastOpenError: '蓝牙状态恢复失败，请退出小程序后重新进入，或联系店长。' })
    } finally {
      clearTimeout(watchdog)
      wx.hideLoading()
      this._opening = false
      // A timed-out cleanup may still be running. Keep the shared guard closed until app restart.
      if (!this._cleanupFailed) bleOperationPending = false
      this.setData({ opening: false })
    }
  },


  goChangeSeat() {
    const { reservation, canChangeSeat } = this.data
    if (!reservation || !canChangeSeat) return
    wx.navigateTo({ url: `${routes.profileChangeSeat}?id=${reservation.id}` })
  },

  goRenew() {
    const { reservation } = this.data
    if (!reservation || !reservation.store_id) return
    const q = [
      `storeId=${reservation.store_id}`,
      `billType=${encodeURIComponent(reservation.bill_type || 'hourly')}`,
      reservation.seat_id ? `seatId=${reservation.seat_id}` : '',
      reservation.seat_code ? `seatCode=${encodeURIComponent(reservation.seat_code)}` : '',
      reservation.end_time ? `startFrom=${encodeURIComponent(reservation.end_time)}` : '',
    ].filter(Boolean).join('&')
    wx.navigateTo({ url: `${routes.bookingIndex}?${q}` })
  },

  showStoreWifi() {
    const storeId = this.data.reservation?.store_id
    if (!storeId) return
    wx.showLoading({ title: '加载中' })
    request({ url: `/store/${storeId}`, silent: true })
      .then((detail) => {
        wx.hideLoading()
        const wifiName = detail && detail.wifi_name
        const wifiPassword = detail && detail.wifi_password
        if (!wifiName) {
          wx.showToast({ title: '该门店暂未配置 WiFi', icon: 'none' })
          return
        }
        const pwd = wifiPassword || '（无密码）'
        wx.showModal({
          title: '门店 WiFi',
          content: `WiFi名称：${wifiName}\n连接密码：${pwd}`,
          confirmText: '复制密码',
          cancelText: '关闭',
          confirmColor: '#2D6A4F',
          success: (res) => {
            if (!res.confirm) return
            wx.setClipboardData({
              data: String(wifiPassword || wifiName),
              success: () => wx.showToast({ title: '已复制', icon: 'success' }),
            })
          },
        })
      })
      .catch(() => {
        wx.hideLoading()
        wx.showToast({ title: '获取 WiFi 信息失败', icon: 'none' })
      })
  },

  goContact() {
    const storeId = this.data.reservation?.store_id
    wx.navigateTo({ url: routes.profileContact + (storeId ? `?storeId=${storeId}` : '') })
  },

  checkout() {
    const { reservation } = this.data
    if (!reservation || reservation.status !== 1) {
      wx.showToast({ title: '请先开门入座', icon: 'none' })
      return
    }
    wx.showModal({
      title: '提前离座',
      content: '确定提前离座？',
      confirmColor: '#2D6A4F',
      success: (res) => {
        if (res.confirm) {
          request({ url: `/reservation/${reservation.id}/checkout`, method: 'POST' }).then(() => {
            wx.showToast({ title: '已离座' })
            this.loadActive()
          })
        }
      },
    })
  },

  goBooking() {
    wx.navigateTo({ url: routes.storeSelect })
  },

  goOrders() {
    if (!auth.requireLogin(routes.profileOrders)) return
    wx.navigateTo({ url: routes.profileOrders })
  },
})
