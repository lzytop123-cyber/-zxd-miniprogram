const { request } = require('../../utils/request')

let plugin = null
let pluginReady = false
try {
  plugin = requirePlugin('ttlock-plugin')
  pluginReady = true
} catch (e) {
  console.log('通通锁插件未加载，可使用远程开门')
}

function formatDate(iso) {
  const d = new Date(String(iso).replace(' ', 'T'))
  const pad = (n) => (n < 10 ? '0' + n : '' + n)
  return `${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

Page({
  data: {
    reservation: null,
    endDisplay: '',
    countdown: '',
    canOpen: false,
    lockData: '',
    lockName: '',
    gatewayUnlock: false,
    pluginReady: false,
    opening: false,
  },

  onShow() {
    this.setData({ pluginReady })
    this.loadActive()
  },

  loadActive() {
    request({ url: '/reservation/active' })
      .then((reservation) => {
        if (!reservation) {
          this.setData({ reservation: null })
          return
        }
        const start = new Date(String(reservation.start_time).replace(' ', 'T'))
        const now = new Date()
        const canOpen = now >= new Date(start.getTime() - 15 * 60000)
        this.setData({
          reservation,
          endDisplay: formatDate(reservation.end_time),
          canOpen,
        })
        this.loadBleKey(reservation.id)
        this.startCountdown(reservation.end_time)
      })
      .catch(() => {
        this.setData({ reservation: null })
      })
  },

  loadBleKey(reservationId) {
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

  startCountdown(endTime) {
    const tick = () => {
      const diff = new Date(String(endTime).replace(' ', 'T')) - new Date()
      if (diff <= 0) {
        this.setData({ countdown: '已结束' })
        return
      }
      const h = Math.floor(diff / 3600000)
      const m = Math.floor((diff % 3600000) / 60000)
      const s = Math.floor((diff % 60000) / 1000)
      this.setData({ countdown: `剩余 ${h}时${m}分${s}秒` })
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
    })
    if (reservation.status === 0) {
      request({ url: `/reservation/${reservation.id}/checkin`, method: 'POST' })
        .then(() => this.loadActive())
    }
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

    if (!plugin) {
      wx.hideLoading()
      wx.showModal({
        title: '蓝牙插件未启用',
        content: '请在微信后台添加通通锁插件（企业主体），或使用「远程开门」。',
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

    plugin.startBleToLock(
      lockData,
      1,
      () => this.afterOpenSuccess(reservation),
      (errorCode, errorMsg) => {
        this.afterOpenFail(reservation, '蓝牙开门失败，可试远程开门', errorCode)
      }
    )
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
    wx.switchTab({ url: '/pages/home/index' })
  },
})
