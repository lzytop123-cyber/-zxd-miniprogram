const { request } = require('../../utils/request')
const auth = require('../../utils/auth')

let plugin = null

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

const OPEN_EARLY_MS = 15 * 60000

function parseTime(iso) {
  return new Date(String(iso).replace(' ', 'T'))
}

function computeCanOpen(startTime, endTime, now = new Date()) {
  const start = parseTime(startTime)
  const end = parseTime(endTime)
  return now >= new Date(start.getTime() - OPEN_EARLY_MS) && now <= end
}

Page({
  data: {
    reservation: null,
    endDisplay: '',
    statusLabel: '',
    statusHint: '',
    countdown: '',
    canOpen: false,
    lockData: '',
    lockName: '',
    gatewayUnlock: false,
    pluginReady: false,
    pluginHint: '',
    runtimeAppId: '',
    opening: false,
  },

  onShow() {
    const pluginState = detectPlugin()
    const runtimeAppId = getRuntimeAppId()
    this.setData({ ...pluginState, runtimeAppId })
    this.loadActive()
  },

  loadActive() {
    request({ url: '/reservation/active' })
      .then((reservation) => {
        if (!reservation) {
          this._expiredReloadFor = null
          this.setData({ reservation: null, canOpen: false })
          return
        }
        const canOpen = computeCanOpen(reservation.start_time, reservation.end_time)
        this.setData({
          reservation,
          endDisplay: formatDate(reservation.end_time),
          statusLabel: reservation.status_label || '',
          statusHint: reservation.status_hint || '',
          canOpen,
        })
        this.loadBleKey(canOpen ? reservation.id : null)
        this.startCountdown(reservation)
      })
      .catch(() => {
        this.setData({ reservation: null, canOpen: false })
      })
  },

  loadBleKey(reservationId) {
    if (!reservationId) {
      this.setData({ lockData: '', gatewayUnlock: false })
      return
    }
    request({ url: `/ble/key/${reservationId}` })
      .then((res) => {
        wx.setStorageSync(`ble_key_${reservationId}`, res.lockData)
        this.setData({
          lockData: res.lockData,
          lockName: res.lockName || '门店大门',
          gatewayUnlock: !!res.gatewayUnlock,
        })
      })
      .catch(() => {
        this.setData({ lockData: '', gatewayUnlock: false })
      })
  },

  startCountdown(reservation) {
    const tick = () => {
      const now = new Date()
      const end = parseTime(reservation.end_time)
      const diff = end - now
      const canOpen = computeCanOpen(reservation.start_time, reservation.end_time, now)
      if (diff <= 0) {
        this.setData({ countdown: '已结束', canOpen: false })
        if (this._expiredReloadFor !== reservation.id) {
          this._expiredReloadFor = reservation.id
          this.loadActive()
        }
        return
      }
      const h = Math.floor(diff / 3600000)
      const m = Math.floor((diff % 3600000) / 60000)
      const s = Math.floor((diff % 60000) / 1000)
      this.setData({
        countdown: `剩余 ${h}时${m}分${s}秒`,
        canOpen,
      })
    }
    tick()
    if (this._timer) clearInterval(this._timer)
    this._timer = setInterval(tick, 1000)
  },

  onUnload() {
    if (this._timer) clearInterval(this._timer)
  },

  afterOpenSuccess(reservation) {
    wx.hideLoading()
    wx.showToast({ title: '门已开启', icon: 'success' })
    wx.vibrateShort()
    request({
      url: `/ble/checkin/${reservation.id}`,
      method: 'POST',
      data: { reservation_id: reservation.id, result: 'success' },
    }).finally(() => this.loadActive())
    this.setData({ opening: false })
  },

  afterOpenFail(reservation, errorMsg, errorCode) {
    wx.hideLoading()
    wx.showToast({ title: errorMsg || '开门失败', icon: 'none' })
    request({
      url: `/ble/checkin/${reservation.id}`,
      method: 'POST',
      data: {
        reservation_id: reservation.id,
        result: 'fail',
        error_code: errorCode ? String(errorCode) : '',
        error_msg: errorMsg || '',
      },
    })
    this.setData({ opening: false })
  },

  async openDoorBle() {
    if (!this.data.canOpen || this.data.opening) return
    if (!this.data.pluginReady) {
      const appId = this.data.runtimeAppId || getRuntimeAppId()
      const hint = this.data.pluginHint || '通通锁插件未加载'
      wx.showModal({
        title: '蓝牙开门不可用',
        content: `${hint}。请确认已在 wx4d3a834429fc6538 后台添加插件并重新上传体验版；当前运行 AppID：${appId || '未知'}。可先使用「远程开门」。`,
        showCancel: false,
      })
      return
    }
    const { reservation } = this.data
    if (!reservation) return

    try {
      await wx.openBluetoothAdapter()
    } catch (e) {
      wx.showModal({
        title: '请开启蓝牙',
        content: '蓝牙开门需要开启手机蓝牙，或在通通锁 APP 中确认已打开远程开锁后使用「远程开门」。',
      })
      return
    }

    this.setData({ opening: true })
    wx.showLoading({ title: '蓝牙连接中...' })
    const lockData = wx.getStorageSync(`ble_key_${reservation.id}`) || this.data.lockData

    if (!plugin || typeof plugin.controlLock !== 'function') {
      wx.hideLoading()
      wx.showModal({
        title: '蓝牙开门不可用',
        content: '通通锁插件未正确加载，请重新上传体验版，或使用「远程开门」。',
        showCancel: false,
      })
      this.setData({ opening: false })
      return
    }

    if (!lockData) {
      wx.hideLoading()
      wx.showToast({ title: '钥匙未生成，请稍后重试', icon: 'none' })
      this.setData({ opening: false })
      return
    }

    const openAction = plugin.CONTROL_ACTION_OPEN || 3
    try {
      const result = await plugin.controlLock({
        controlAction: openAction,
        lockData,
      })
      if (result && result.errorCode === 0) {
        this.afterOpenSuccess(reservation)
      } else {
        const msg = (result && result.errorMsg) || '蓝牙开门失败，可试远程开门'
        this.afterOpenFail(reservation, msg, result && result.errorCode)
      }
    } catch (err) {
      wx.hideLoading()
      this.afterOpenFail(
        reservation,
        err?.errorMsg || err?.message || '蓝牙插件调用失败',
        err?.errorCode || ''
      )
    }
  },

  openDoorRemote() {
    if (!this.data.canOpen || this.data.opening) return
    const { reservation } = this.data
    if (!reservation) return

    this.setData({ opening: true })
    wx.showLoading({ title: '远程开门中...' })
    request({ url: `/ble/unlock/${reservation.id}`, method: 'POST' })
      .then(() => this.afterOpenSuccess(reservation))
      .catch((err) => {
        const msg = err.detail || err.message || '远程开门失败'
        this.afterOpenFail(reservation, msg, '')
      })
  },

  checkout() {
    const { reservation } = this.data
    wx.showModal({
      title: '提前离座',
      content: '确定要提前结束本次学习吗？',
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
    if (!auth.isLoggedIn()) {
      auth.goLogin('')
      return
    }
    wx.switchTab({ url: '/pages/home/index' })
  },
})
