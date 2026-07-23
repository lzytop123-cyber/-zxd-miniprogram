const { getAgreement } = require('../../../utils/agreements')

Page({
  data: {
    title: '',
    updatedAt: '',
    sections: [],
  },

  onLoad(options) {
    const type = options.type === 'privacy' ? 'privacy' : 'user'
    const doc = getAgreement(type)
    this.setData({
      title: doc.title,
      updatedAt: doc.updatedAt,
      sections: doc.sections,
    })
    wx.setNavigationBarTitle({ title: doc.title })
  },
})
