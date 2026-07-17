const { request } = require('../../utils/request')
const auth = require('../../utils/auth')
const routes = require('../../utils/routes')
const { handleTabScroll } = require('../../utils/tabbar')
const {
  computeCanOpen,
  getOpenWindowHint,
  mapBleOpenFailure,
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

  onShow() {
    if (typeof this.getTabBar === 'function' && this.getTabBar()) {
      this.getTabBar().setData({ selected: 2, collapsed: false })
    }
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
    if (!reservationId) {
      this.setData({ lockData: '' })
      return
    }
    request({ url: `/ble/key/${reservationId}` })
      .then((res) => {
        wx.setStorageSync(`ble_key_${reservationId}`, res.lockData)
        this.setData({
          lockData: res.lockData,
          lockName: res.lockName || '门店大门',
        })
      })
      .catch(() => {
        this.setData({ lockData: '' })
      })
  },

  startCountdown(reservation) {
    const tick = () => {
      const now = new Date()
      const end = parseTime(reservation.end_time)
      const duration = formatReservationDuration(reservation, now)
      const canOpen = computeCanOpen(reservation, now)
      const openWindowHint = getOpenWindowHint(reservation, now)
      if (end <= now) {
        this.setData({
          durationLabel: '剩余时长',
          countdown: '已结束',
          canOpen: false,
          canChangeSeat: false,
          openWindowHint: '订单已结束',
        })
        if (this._expiredReloadFor !== reservation.id) {
          this._expiredReloadFor = reservation.id
          this.loadActive()
        }
        return
      }
      this.setData({
        durationLabel: duration.label,
        countdown: duration.text,
        canOpen,
        canChangeSeat: canChangeSeatFor(reservation, now),
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
    if (failure.refresh) {
      this.loadBleKey(reservation.id)
    }
  },

  async openDoorBle() {
    if (!this.data.canOpen || this.data.opening) return
    if (!this.data.pluginReady) {
      const hint = this.data.pluginHint || '通通锁插件未加载'
      this.setData({ lastOpenError: hint })
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
      this.setData({ opening: false, lastOpenError: failure.content })
      return
    }

    this.setData({ opening: true })
    wx.showLoading({ title: '蓝牙连接中...' })
    const lockData = wx.getStorageSync(`ble_key_${reservation.id}`) || this.data.lockData

    if (!plugin || typeof plugin.controlLock !== 'function') {
      wx.hideLoading()
      this.setData({ opening: false, lastOpenError: '蓝牙插件未加载' })
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
      this.setData({ opening: false, lastOpenError: failure.content })
      this.loadBleKey(reservation.id)
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


  goChangeSeat() {
    const { reservation, canChangeSeat } = this.data
    if (!reservation || !canChangeSeat) return
    wx.navigateTo({ url: `${routes.profileChangeSeat}?id=${reservation.id}` })
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
    if (!auth.isLoggedIn()) {
      auth.goLogin('')
      return
    }
    wx.switchTab({ url: '/pages/home/index' })
  },
})
