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
      wx.vibrateShort({ type: 'light' })
      if (index === this.data.selected) return
      wx.switchTab({ url: path })
      this.setData({ selected: index })
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
