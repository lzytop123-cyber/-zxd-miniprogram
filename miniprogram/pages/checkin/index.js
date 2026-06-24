const { request } = require('../../utils/request')

let plugin = null
try {
  plugin = requirePlugin('ttlock-plugin')
} catch (e) {
  console.log('通通锁插件未加载（测试号可忽略）')
}

function formatDate(iso) {
  const d = new Date(iso)
  const pad = (n) => (n < 10 ? '0' + n : '' + n)
  return `${pad(d.getMonth()+1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

Page({
  data: {
    reservation: null,
    endDisplay: '',
    countdown: '',
    canOpen: false,
    lockData: '',
  },

  onShow() {
    this.loadActive()
  },

  loadActive() {
    request({ url: '/reservation/active' })
      .then((reservation) => {
        if (!reservation) {
          this.setData({ reservation: null })
          return
        }
        const start = new Date(reservation.start_time.replace(' ', 'T'))
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
      .catch((err) => {
        console.error('loadActive failed', err)
        this.setData({ reservation: null })
      })
  },

  loadBleKey(reservationId) {
    request({ url: `/ble/key/${reservationId}` }).then((res) => {
      wx.setStorageSync(`ble_key_${reservationId}`, res.lockData)
      this.setData({ lockData: res.lockData })
    }).catch(() => {})
  },

  startCountdown(endTime) {
    const tick = () => {
      const diff = new Date(endTime) - new Date()
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

  async openDoor() {
    if (!this.data.canOpen) return
    const { reservation } = this.data
    if (!reservation) return

    try {
      await wx.openBluetoothAdapter()
    } catch (e) {
      wx.showModal({ title: '请开启蓝牙', content: '开门需要蓝牙权限，请在手机设置中开启' })
      return
    }

    wx.showLoading({ title: '正在连接门锁...' })
    const lockData = wx.getStorageSync(`ble_key_${reservation.id}`) || this.data.lockData

    const onSuccess = () => {
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
        this.loadActive()
      }
    }

    if (!plugin) {
      setTimeout(onSuccess, 800)
      return
    }

    plugin.startBleToLock(
      lockData,
      1,
      onSuccess,
      (errorCode, errorMsg) => {
        wx.hideLoading()
        wx.showToast({ title: '开门失败，请靠近门锁重试', icon: 'none' })
        request({
          url: `/ble/checkin/${reservation.id}`,
          method: 'POST',
          data: { reservation_id: reservation.id, result: 'fail', error_code: String(errorCode), error_msg: errorMsg },
        })
      }
    )
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
