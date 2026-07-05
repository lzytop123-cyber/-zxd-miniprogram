const auth = require('../../../utils/auth')
const { request } = require('../../../utils/request')
const { normalizeUser, pickAvatarDisplay } = require('../../../utils/user')

const GOAL_OPTIONS = [
  { value: 'kaoyan', label: '考研' },
  { value: 'kaogong', label: '考公' },
  { value: 'other', label: '其他' },
]

function isLocalAvatarPath(path) {
  if (!path) return false
  const s = String(path)
  return s.startsWith('wxfile://') || /^https?:\/\/tmp\//.test(s)
}

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
    this.setData({ step: 'loading', loginError: '' })
    try {
      if (!auth.isLoggedIn()) {
        await auth.login({ silent: false, force: true })
      }
      const user = await request({ url: '/user/profile', silent: true, force: true })
      auth.syncAppUser(user)
      await this.applyUser(user)
    } catch (err) {
      this.setData({
        step: 'error',
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

  retryLogin() {
    this.bootstrap()
  },

  async onChooseAvatar(e) {
    const { avatarUrl } = e.detail
    if (!avatarUrl || this.data.avatarUploading) return

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
      wx.showToast({ title: err.detail || err.message || '头像同步失败', icon: 'none' })
    } finally {
      wx.hideLoading()
      this.setData({ avatarUploading: false })
    }
  },

  onNicknameInput(e) {
    this.setData({ draftNickname: e.detail.value })
  },

  onNicknameBlur(e) {
    const value = String(e.detail.value || '').trim()
    if (value) this.setData({ draftNickname: value })
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
    const avatarTempPath = isLocalAvatarPath(avatarDisplay) ? avatarDisplay : undefined
    const hasAvatar = !!(avatarTempPath || user?.avatar_url)
    if (!hasAvatar) {
      wx.showToast({ title: '请设置头像', icon: 'none' })
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
        avatarTempPath,
      })
      auth.syncAppUser(profile)
      if (profile?.needs_profile_setup) {
        wx.hideLoading()
        wx.showToast({ title: '请设置头像', icon: 'none' })
        return
      }
      wx.hideLoading()
      wx.showToast({ title: '欢迎加入知行岛', icon: 'success' })
      setTimeout(() => auth.finishLoginRedirect(this.data.redirect), 800)
    } catch (err) {
      wx.hideLoading()
      wx.showToast({ title: err.detail || err.message || '保存失败', icon: 'none' })
    } finally {
      this.setData({ saving: false })
    }
  },
})
