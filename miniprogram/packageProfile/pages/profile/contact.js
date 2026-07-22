const { request } = require('../../../utils/request')
const { resolveStaticUrl } = require('../../../config')

const FALLBACK_POSTER = '/assets/contact-manager.png'

function isRemoteImage(url) {
  const s = String(url || '')
  return /^https?:\/\//i.test(s)
}

Page({
  data: {
    posterUrl: FALLBACK_POSTER,
    isNetworkPoster: false,
    title: '联系店长',
    hint: '长按识别二维码，添加店长微信咨询',
    loading: true,
  },

  onLoad() {
    this.loadContact()
  },

  loadContact() {
    this.setData({ loading: true })
    request({ url: '/home/contact', silent: true, force: true })
      .then((data) => {
        let remote = data?.poster_url ? resolveStaticUrl(data.poster_url) : ''
        // 开发期本地 http 静态资源在真机也不稳定，统一尽量走 https 生产域名
        if (remote && remote.startsWith('http://')) {
          remote = remote.replace(/^http:\/\//i, 'https://')
        }
        const useRemote = isRemoteImage(remote)
        this.setData({
          posterUrl: useRemote ? remote : FALLBACK_POSTER,
          isNetworkPoster: useRemote,
          title: data?.title || '联系店长',
          hint: data?.hint || '长按识别二维码，添加店长微信咨询',
          loading: false,
        })
        if (data?.title) {
          wx.setNavigationBarTitle({ title: data.title })
        }
      })
      .catch(() => {
        this.setData({
          posterUrl: FALLBACK_POSTER,
          isNetworkPoster: false,
          loading: false,
        })
      })
  },

  onPosterError() {
    if (this.data.posterUrl !== FALLBACK_POSTER) {
      this.setData({
        posterUrl: FALLBACK_POSTER,
        isNetworkPoster: false,
      })
    }
  },

  savePoster() {
    const url = this.data.posterUrl
    const saveTemp = (filePath) => {
      wx.saveImageToPhotosAlbum({
        filePath,
        success: () => wx.showToast({ title: '已保存，可打开扫一扫', icon: 'none' }),
        fail: () => {
          wx.showModal({
            title: '需要相册权限',
            content: '请在设置中允许保存到相册后重试',
            confirmText: '去设置',
            success: (res) => {
              if (res.confirm) wx.openSetting({})
            },
          })
        },
      })
    }

    if (!isRemoteImage(url)) {
      // 包内图片可直接保存
      saveTemp(url)
      return
    }

    wx.showLoading({ title: '下载中', mask: true })
    wx.downloadFile({
      url,
      success: (res) => {
        wx.hideLoading()
        if (res.statusCode === 200 && res.tempFilePath) {
          saveTemp(res.tempFilePath)
        } else {
          wx.showToast({ title: '下载失败', icon: 'none' })
        }
      },
      fail: () => {
        wx.hideLoading()
        wx.showToast({ title: '下载失败，请检查域名配置', icon: 'none' })
      },
    })
  },
})
