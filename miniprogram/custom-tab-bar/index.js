Component({
  data: {
    selected: 0,
    collapsed: false,
    list: [],
  },
  lifetimes: {
    attached() {
      const { buildTabList } = require('../utils/features')
      this.setData({ list: buildTabList() })
    },
  },
  pageLifetimes: {
    show() {
      const { buildTabList } = require('../utils/features')
      this.setData({ list: buildTabList() })
    },
  },
  methods: {
    onTap(e) {
      const { index, path } = e.currentTarget.dataset
      if (!path) return
      wx.vibrateShort({ type: 'light' })

      // 当前选中态可能与真实页面不一致（例如助手已隐藏但仍停在助手页），
      // 不能仅凭 selected===index 就跳过跳转。
      let current = ''
      try {
        const pages = getCurrentPages()
        const cur = pages[pages.length - 1]
        current = cur && cur.route ? `/${cur.route}` : ''
      } catch (err) {
        // ignore
      }
      if (current === path) {
        this.setData({ selected: index, collapsed: false })
        return
      }

      wx.switchTab({
        url: path,
        fail: () => {
          wx.reLaunch({ url: path })
        },
      })
      this.setData({ selected: index, collapsed: false })
    },

    onExpand() {
      wx.vibrateShort({ type: 'light' })
      this.setCollapsed(false)
    },

    setCollapsed(collapsed) {
      if (this.data.collapsed === collapsed) return
      this.setData({ collapsed })
    },
  },
})
