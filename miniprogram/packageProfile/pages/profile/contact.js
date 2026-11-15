const { request } = require('../../../utils/request')
const { resolveStaticUrl } = require('../../../config')
const { getUserLocation, isLocationDenied, formatDistance } = require('../../../utils/location')
const { chooseContactStore } = require('../../../utils/contact-store')

Page({
  data: { stores: [], selectedStore: null, posterUrl: '', loading: true, locating: false, error: '', locationHint: '可手动选择门店', hint: '' },
  async onLoad(options = {}) {
    this._preferredId = options.storeId || null
    await this.loadStores()
    if (!this._preferredId) this.locate()
  },
  async loadStores() {
    this.setData({ loading: true, error: '' })
    try {
      const stores = await request({ url: '/store/list', silent: true, force: true })
      this.setData({ stores: stores || [], loading: false })
      const selected = chooseContactStore(stores || [], this._preferredId, false)
      if (selected) this.selectStore(selected, '订单所属门店')
    } catch (_) { this.setData({ loading: false, error: '门店加载失败，请重试' }) }
  },
  async locate() {
    if (this.data.locating) return
    const revision = this._selectionRevision || 0
    this.setData({ locating: true, locationHint: '正在查找附近门店…' })
    try {
      if (await isLocationDenied()) throw new Error('denied')
      const { latitude, longitude } = await getUserLocation()
      const stores = await request({ url: `/store/list?latitude=${latitude}&longitude=${longitude}`, silent: true, force: true })
      if (revision !== (this._selectionRevision || 0)) return
      this.setData({ stores: stores || [] })
      const selected = chooseContactStore(stores || [], null, true)
      if (selected) this.selectStore(selected, `距你最近 · ${formatDistance(selected.distance)}`)
      else this.setData({ locationHint: '暂无距离信息，请手动选择门店' })
    } catch (_) {
      if (revision === (this._selectionRevision || 0)) this.setData({ locationHint: '定位不可用，请手动选择门店' })
    } finally { this.setData({ locating: false }) }
  },
  onStoreChange(e) {
    const store = this.data.stores[Number(e.detail.value)]
    if (store) this.selectStore(store, '已选择门店')
  },
  selectStore(store, hint) {
    this._selectionRevision = (this._selectionRevision || 0) + 1
    this.setData({ selectedStore: store, locationHint: hint, posterUrl: '', error: '' })
    this.loadContact()
  },
  async loadContact() {
    if (!this.data.selectedStore) return this.loadStores()
    const id = this._requestId = (this._requestId || 0) + 1
    this.setData({ loading: true, error: '', posterUrl: '' })
    try {
      const data = await request({ url: `/home/contact?store_id=${this.data.selectedStore.id}`, silent: true, force: true })
      if (id !== this._requestId) return
      const posterUrl = data?.poster_url ? resolveStaticUrl(data.poster_url) : ''
      this.setData({ posterUrl, hint: data?.hint || '长按识别二维码，添加店长微信咨询', loading: false })
    } catch (_) {
      if (id === this._requestId) this.setData({ loading: false, error: '二维码加载失败，请重试' })
    }
  },
  onPosterError() { this.setData({ posterUrl: '', error: '二维码图片加载失败，请重试' }) },
  savePoster() {
    const url = this.data.posterUrl
    if (!url || this.data.loading) return
    wx.showLoading({ title: '保存中' })
    wx.downloadFile({ url,
      success: res => {
        wx.hideLoading()
        if (res.statusCode !== 200 || !res.tempFilePath) return wx.showToast({ title: '图片下载失败，请重试', icon: 'none' })
        wx.saveImageToPhotosAlbum({ filePath: res.tempFilePath,
          success: () => wx.showToast({ title: '已保存', icon: 'success' }),
          fail: err => {
            if (/cancel/.test(err.errMsg || '')) return
            if (/auth|deny/.test(err.errMsg || '')) {
              wx.showModal({ title: '需要相册权限', content: '允许保存到相册后可保存二维码', confirmText: '去设置', success: r => { if (r.confirm) wx.openSetting({}) } })
            } else wx.showToast({ title: '保存失败，请重试', icon: 'none' })
          }
        })
      },
      fail: () => { wx.hideLoading(); wx.showToast({ title: '图片下载失败，请重试', icon: 'none' }) }
    })
  }
})
