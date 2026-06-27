const auth = require('../../utils/auth')
const { request } = require('../../utils/request')
const { normalizeUser, pickAvatarDisplay } = require('../../utils/user')

const GOAL_OPTIONS = [
  { value: 'kaoyan', label: '考研' },
  { value: 'kaogong', label: '考公' },
  { value: 'other', label: '其他' },
]

Page({
  data: {
    step: 'loading',
    loginError: '',
    redirect: '',
    user: null,
    draftNickname: '',
    draftStudyGoal: '',
    avatarDisplay: '',
    avatarUploading: false,
    saving: false,
    goalOptions: GOAL_OPTIONS,
  },

  onLoad(options) {
    this.setData({ redirect: options.redirect ? decodeURIComponent(options.redirect) : '' })
    this.bootstrap()
  },

  async bootstrap() {
    if (!auth.isLoggedIn()) {
      this.setData({ step: 'login', user: null, loginError: '', avatarDisplay: '' })
      return
    }

    this.setData({ step: 'loading', loginError: '' })
    try {
      await auth.waitForLogin()
      const user = await request({ url: '/user/profile', silent: true })
      auth.syncAppUser(user)
      await this.applyUser(user)
    } catch (err) {
      this.setData({
        step: 'login',
        loginError: err.detail || err.message || '登录失败，请重试',
      })
    }
  },

  async applyUser(user, localAvatar) {
    const normalized = await normalizeUser(user)
    const avatarDisplay = pickAvatarDisplay(localAvatar, normalized)
    if (user.needs_profile_setup) {
      this.setData({
        step: 'setup',
        user: normalized,
        draftNickname: user.nickname === auth.DEFAULT_NICKNAME ? '' : (user.nickname || ''),
        draftStudyGoal: user.study_goal || '',
        avatarDisplay,
        loginError: '',
      })
      return
    }
    auth.finishLoginRedirect(this.data.redirect)
  },

  doLogin() {
    wx.showLoading({ title: '登录中...' })
    auth
      .login({ silent: false, force: true })
      .then(() => this.bootstrap())
      .catch((err) => {
        this.setData({
          step: 'login',
          loginError: err.detail || err.message || '登录失败',
        })
      })
      .finally(() => wx.hideLoading())
  },

  async onChooseAvatar(e) {
    const { avatarUrl } = e.detail
    if (!avatarUrl || this.data.avatarUploading) return

    // 先立刻更新界面（微信临时路径可直接显示）
    this.setData({ avatarDisplay: avatarUrl, avatarUploading: true })
    wx.showLoading({ title: '同步头像...' })
    try {
      const profile = await auth.uploadAvatar(avatarUrl)
      auth.syncAppUser(profile)
      const normalized = await normalizeUser(profile)
      this.setData({
        user: normalized,
        avatarDisplay: avatarUrl,
      })
      wx.showToast({ title: '头像已同步', icon: 'success' })
    } catch (err) {
      // 上传失败也保留本地预览
      wx.showToast({ title: err.detail || err.message || '头像同步失败', icon: 'none' })
    } finally {
      wx.hideLoading()
      this.setData({ avatarUploading: false })
    }
  },

  onNicknameInput(e) {
    this.setData({ draftNickname: e.detail.value })
  },

  onGoalSelect(e) {
    const value = e.currentTarget.dataset.value
    const next = this.data.draftStudyGoal === value ? '' : value
    this.setData({ draftStudyGoal: next })
  },

  async saveProfile() {
    const { draftNickname, draftStudyGoal, saving, user, avatarUploading, avatarDisplay } = this.data
    if (saving || avatarUploading) return

    const nickname = draftNickname.trim()
    const hasAvatar = !!(avatarDisplay || user?.avatar_url)
    if (!hasAvatar) {
      wx.showToast({ title: '请点击头像使用微信头像', icon: 'none' })
      return
    }
    if (!nickname) {
      wx.showToast({ title: '请填写昵称', icon: 'none' })
      return
    }

    this.setData({ saving: true })
    wx.showLoading({ title: '保存中...' })
    try {
      const profile = await auth.saveProfile({
        nickname,
        studyGoal: draftStudyGoal,
      })
      wx.hideLoading()
      wx.showToast({ title: '登录成功', icon: 'success' })
      auth.syncAppUser(profile)
      auth.finishLoginRedirect(this.data.redirect)
    } catch (err) {
      wx.hideLoading()
      wx.showToast({ title: err.detail || err.message || '保存失败', icon: 'none' })
    } finally {
      this.setData({ saving: false })
    }
  },
})
