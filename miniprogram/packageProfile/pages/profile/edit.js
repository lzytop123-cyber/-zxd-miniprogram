const auth = require('../../../utils/auth')
const { request } = require('../../../utils/request')
const { normalizeUser, pickAvatarDisplay } = require('../../../utils/user')
const routes = require('../../../utils/routes')

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

function maskPhone(phone) {
  const s = String(phone || '').replace(/\D/g, '')
  if (s.length < 7) return ''
  return `${s.slice(0, 3)}****${s.slice(-4)}`
}

Page({
  data: {
    loading: true,
    user: null,
    draftNickname: '',
    draftStudyGoal: '',
    phoneMasked: '',
    avatarDisplay: '',
    avatarUploading: false,
    saving: false,
    goalOptions: GOAL_OPTIONS,
  },

  onLoad() {
    this.loadProfile()
  },

  async loadProfile() {
    if (!auth.isLoggedIn()) {
      auth.goLogin(routes.profileEdit)
      return
    }
    try {
      const user = await request({ url: '/user/profile', silent: true, force: true })
      auth.syncAppUser(user)
      await this.applyUser(user)
    } catch (err) {
      const cached = wx.getStorageSync('userInfo')
      if (cached) {
        await this.applyUser(cached)
        return
      }
      wx.showToast({ title: '加载失败，请重试', icon: 'none' })
    }
  },

  async applyUser(user) {
    const normalized = await normalizeUser(user)
    this.setData({
      loading: false,
      user: normalized,
      draftNickname: user.nickname === auth.DEFAULT_NICKNAME ? '' : (user.nickname || ''),
      draftStudyGoal: user.study_goal || '',
      phoneMasked: maskPhone(user.phone),
      avatarDisplay: pickAvatarDisplay('', normalized),
    })
  },

  async onGetPhoneNumber(e) {
    const detail = e.detail || {}
    const code = detail.code
    if (!code) {
      const msg = String(detail.errMsg || '')
      if (msg.includes('deny') || msg.includes('cancel')) return
      wx.showToast({ title: '未获取到手机号，请重试', icon: 'none' })
      return
    }
    wx.showLoading({ title: '更新手机号...' })
    try {
      const profile = await request({
        url: '/user/bind-phone',
        method: 'POST',
        data: { code },
        force: true,
      })
      auth.syncAppUser(profile)
      const normalized = await normalizeUser(profile)
      wx.hideLoading()
      this.setData({ user: normalized, phoneMasked: maskPhone(profile.phone) })
      wx.showToast({ title: '手机号已更新', icon: 'success' })
    } catch (err) {
      wx.hideLoading()
      wx.showToast({ title: err.detail || err.message || '更新失败', icon: 'none' })
    }
  },

  async onChooseAvatar(e) {
    const avatarUrl = e?.detail?.avatarUrl
    if (!avatarUrl) {
      wx.showToast({ title: '未获取到头像，请重试', icon: 'none' })
      return
    }
    await this._uploadAvatarFile(avatarUrl)
  },

  async _uploadAvatarFile(avatarUrl) {
    if (!avatarUrl || this.data.avatarUploading) return

    this.setData({ avatarDisplay: avatarUrl, avatarUploading: true })
    wx.showLoading({ title: '更新头像...', mask: true })
    try {
      const profile = await auth.uploadAvatar(avatarUrl)
      auth.syncAppUser(profile)
      const normalized = await normalizeUser(profile)
      this.setData({ user: normalized, avatarDisplay: avatarUrl })
      wx.showToast({ title: '头像已更新', icon: 'success' })
    } catch (err) {
      this.setData({ avatarDisplay: avatarUrl })
      wx.showToast({
        title: err.detail || err.message || '头像稍后随资料保存',
        icon: 'none',
      })
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
      wx.hideLoading()
      wx.showToast({ title: '已保存', icon: 'success' })
      setTimeout(() => {
        wx.navigateBack({
          fail: () => wx.switchTab({ url: '/pages/profile/index' }),
        })
      }, 600)
    } catch (err) {
      wx.hideLoading()
      wx.showToast({ title: err.detail || err.message || '保存失败', icon: 'none' })
    } finally {
      this.setData({ saving: false })
    }
  },
})
