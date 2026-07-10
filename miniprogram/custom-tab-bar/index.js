Component({
  data: {
    selected: 0,
    collapsed: false,
    list: [
      { pagePath: '/pages/home/index', text: '首页', icon: '/assets/tab-home.png', selectedIcon: '/assets/tab-home-active.png' },
      { pagePath: '/pages/packages/index', text: '套餐', icon: '/assets/tab-packages.png', selectedIcon: '/assets/tab-packages-active.png' },
      { pagePath: '/pages/checkin/index', text: '入座', icon: '/assets/tab-checkin.png', selectedIcon: '/assets/tab-checkin-active.png' },
      { pagePath: '/pages/report/index', text: '学习助手', icon: '/assets/tab-report.png', selectedIcon: '/assets/tab-report-active.png' },
      { pagePath: '/pages/profile/index', text: '我的', icon: '/assets/tab-profile.png', selectedIcon: '/assets/tab-profile-active.png' },
    ],
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
