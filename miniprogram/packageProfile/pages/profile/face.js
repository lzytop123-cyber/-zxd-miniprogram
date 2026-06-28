const { request } = require('../../../utils/request')

Page({
  data: { registered: false },

  onShow() {
    request({ url: '/user/profile' }).then((user) => {
      this.setData({ registered: user.face_registered })
    })
  },

  chooseFace() {
    wx.chooseMedia({
      count: 1,
      mediaType: ['image'],
      sourceType: ['camera', 'album'],
      success: (res) => {
        const path = res.tempFiles[0].tempFilePath
        wx.getFileSystemManager().readFile({
          filePath: path,
          encoding: 'base64',
          success: (file) => {
            wx.showLoading({ title: '上传中' })
            request({
              url: '/user/face',
              method: 'POST',
              data: { face_image: `data:image/jpeg;base64,${file.data}` },
            })
              .then(() => {
                wx.hideLoading()
                wx.showToast({ title: '录入成功' })
                this.setData({ registered: true })
              })
              .catch(() => wx.hideLoading())
          },
        })
      },
    })
  },
})
