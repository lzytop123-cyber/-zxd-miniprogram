const { request } = require('../../utils/request')
const auth = require('../../utils/auth')
const {
  computeCanOpen,
  getOpenWindowHint,
  mapBleOpenFailure,
  showOpenFailureModal,
} = require('../../utils/bleUnlock')

const CHECKIN_SELECT_KEY = 'checkin_selected_id'

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

function parseTime(iso) {
  return new Date(String(iso).replace(' ', 'T'))
}

function formatCountdown(diff) {
  const totalMinutes = Math.max(0, Math.floor(diff / 60000))
  const days = Math.floor(totalMinutes / (24 * 60))
  const hours = Math.floor((totalMinutes % (24 * 60)) / 60)
  const minutes = totalMinutes % 60
  const parts = []
  if (days > 0) parts.push(`${days}天`)
  if (days > 0 || hours > 0) parts.push(`${hours}小时`)
  parts.push(`${minutes}分`)
  return `剩余 ${parts.join('')}`
}

Page({
  data: {
    pageLoading: true,
    activeList: [],
    selectedId: null,
    reservation: null,
    endDisplay: '',
    statusLabel: '',
    statusHint: '',
    countdown: '',
    canOpen: false,
    openWindowHint: '',
    lockData: '',
    lockName: '',
    gatewayUnlock: false,
    pluginReady: false,
    pluginHint: '',
    runtimeAppId: '',
    opening: false,
    lastOpenError: '',
  },

  onShow() {
    const pluginState = detectPlugin()
    const runtimeAppId = getRuntimeAppId()
    const preferred = wx.getStorageSync(CHECKIN_SELECT_KEY)
    if (preferred) {
      wx.removeStorageSync(CHECKIN_SELECT_KEY)
      this._preferredId = Number(preferred)
    }
    this.setData({ ...pluginState, runtimeAppId })
    this.loadActive({ silent: true })
  },

  onPullDownRefresh() {
    this.loadActive({ force: true }).finally(() => wx.stopPullDownRefresh())
  },

  loadActive(options = {}) {
    const { force = false, silent = false } = options
    const hasList = (this.data.activeList || []).length > 0
    if (!hasList || force) {
      if (!silent || !hasList) {
        this.setData({ pageLoading: !hasList })
      }
    }
    return request({ url: '/reservation/active/list', silent: true, force })
      .then((list) => {
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

        this.setData({ activeList: items, selectedId, pageLoading: false })
        const reservation = items.find((item) => item.id === selectedId) || items[0]
        this.applyReservation(reservation)
      })
      .catch(() => {
        if (!hasList) {
          this.setData({
            activeList: [],
            selectedId: null,
            reservation: null,
            canOpen: false,
            pageLoading: false,
          })
        } else {
          this.setData({ pageLoading: false })
        }
      })
  },

  selectReservation(e) {
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
      endDisplay: formatDate(reservation.end_time),
      statusLabel: reservation.status_label || '',
      statusHint: reservation.status_hint || '',
      canOpen,
      openWindowHint,
      lastOpenError: '',
    })
    this.loadBleKey(canOpen ? reservation.id : null)
    this.startCountdown(reservation)
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
      const canOpen = computeCanOpen(reservation, now)
      const openWindowHint = getOpenWindowHint(reservation, now)
      if (diff <= 0) {
        this.setData({ countdown: '已结束', canOpen: false, openWindowHint: '订单已结束，无法开门' })
        if (this._expiredReloadFor !== reservation.id) {
          this._expiredReloadFor = reservation.id
          this.loadActive()
        }
        return
      }
      this.setData({
        countdown: formatCountdown(diff),
        canOpen,
        openWindowHint,
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
    this.setData({ opening: false, lastOpenError: '' })
  },

  afterOpenFail(reservation, errorMsg, errorCode, mode = 'ble') {
    wx.hideLoading()
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
      },
    })
    showOpenFailureModal(failure, {
      onRetry: () => this.openDoorBle(),
      onRefresh: () => {
        this.loadBleKey(reservation.id)
        setTimeout(() => this.openDoorBle(), 500)
      },
    })
  },

  async openDoorBle() {
    if (!this.data.canOpen || this.data.opening) return
    if (!this.data.pluginReady) {
      const appId = this.data.runtimeAppId || getRuntimeAppId()
      const hint = this.data.pluginHint || '通通锁插件未加载'
      wx.showModal({
        title: '蓝牙开门不可用',
        content: `${hint}。请确认已在 wx4d3a834429fc6538 后台添加插件并重新上传体验版；当前运行 AppID：${appId || '未知'}。`,
        showCancel: false,
      })
      return
    }
    const { reservation } = this.data
    if (!reservation) return

    try {
      await wx.openBluetoothAdapter()
    } catch (e) {
      const failure = mapBleOpenFailure({
        errorMsg: '蓝牙未开启',
        canOpen: true,
        reservation,
        mode: 'ble',
      })
      showOpenFailureModal(failure, {
        onRetry: () => this.openDoorBle(),
      })
      return
    }

    this.setData({ opening: true })
    wx.showLoading({ title: '蓝牙连接中...' })
    const lockData = wx.getStorageSync(`ble_key_${reservation.id}`) || this.data.lockData

    if (!plugin || typeof plugin.controlLock !== 'function') {
      wx.hideLoading()
      this.setData({ opening: false })
      wx.showModal({
        title: '蓝牙开门不可用',
        content: '通通锁插件未正确加载，请重新上传体验版。',
        showCancel: false,
      })
      return
    }

    if (!lockData) {
      wx.hideLoading()
      const failure = mapBleOpenFailure({
        errorMsg: '钥匙未生成',
        canOpen: true,
        reservation,
        mode: 'ble',
      })
      this.setData({ opening: false })
      showOpenFailureModal(failure, {
        onRefresh: () => {
          this.loadBleKey(reservation.id)
          setTimeout(() => this.openDoorBle(), 500)
        },
      })
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
        this.afterOpenFail(
          reservation,
          (result && result.errorMsg) || '蓝牙开门失败',
          result && result.errorCode,
          'ble'
        )
      }
    } catch (err) {
      this.afterOpenFail(
        reservation,
        err?.errorMsg || err?.message || '蓝牙插件调用失败',
        err?.errorCode || '',
        'ble'
      )
    }
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
