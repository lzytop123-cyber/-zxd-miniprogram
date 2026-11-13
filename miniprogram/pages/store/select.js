const { request } = require('../../utils/request')
const auth = require('../../utils/auth')
const routes = require('../../utils/routes')
const { getUserLocation, isLocationDenied, openLocationSettings, formatDistance } = require('../../utils/location')
const { resolveStoreList } = require('../../utils/media')

Page({
  data: {
    stores: [],
    loading: true,
    loadError: '',
    locationHint: '',
  },

  onLoad() {
    this.loadStores({ force: true })
  },

  onShow() {
    if (this._shownOnce) this.loadStores({ force: true })
    this._shownOnce = true
  },

  onPullDownRefresh() {
    this.loadStores({ force: true }).finally(() => wx.stopPullDownRefresh())
  },

  async loadStores({ force = false } = {}) {
    this.setData({ loading: true, loadError: '' })
    let locationHint = ''

    try {
      let list
      const denied = await isLocationDenied()
      if (denied) {
        locationHint = '开启定位可查看距离'
      } else {
        try {
          const { latitude, longitude } = await getUserLocation()
          list = await request({
            url: `/store/list?latitude=${latitude}&longitude=${longitude}`,
            silent: true,
            force,
          })
        } catch (error) {
          locationHint = '定位暂不可用，可按地址选择门店'
        }
      }

      if (!list) {
        list = await request({ url: '/store/list', silent: true, force })
      }

      const resolved = await resolveStoreList(list || [])
      const stores = resolved.map((store) => ({
        ...store,
        distanceLabel: formatDistance(store.distance),
      }))
      this.setData({ stores, locationHint, loading: false })
    } catch (error) {
      this.setData({
        stores: [],
        locationHint,
        loading: false,
        loadError: '门店加载失败，请检查网络后重试',
      })
    }
  },

  async openLocationSetting() {
    const denied = await isLocationDenied()
    if (denied) {
      const enabled = await openLocationSettings()
      if (!enabled) return
    }
    this.loadStores({ force: true })
  },

  selectStore(event) {
    const id = event.detail?.id ?? event.currentTarget?.dataset?.id
    const store = this.data.stores.find((item) => String(item.id) === String(id))
    if (!store) return

    const bookingUrl = `${routes.bookingIndex}?storeId=${store.id}`
    if (!auth.requireLogin(bookingUrl)) return
    wx.navigateTo({ url: bookingUrl })
  },
})
