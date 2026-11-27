const auth = require('../../../utils/auth')
const { request, invalidateCache } = require('../../../utils/request')
const { normalizeUser, pickAvatarDisplay } = require('../../../utils/user')
const { peekPendingInvite, clearPendingInvite } = require('../../../utils/share')

const GOAL_OPTIONS = [
  { value: 'kaoyan', label: '考研' },
  { value: 'kaogong', label: '考公' },
  { value: 'other', label: '其他' },
]

const AGREE_KEY = 'login_agreed_v1'
const LAST_PHONE_KEY = 'login_last_phone_v1'

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

function phoneButtonText(phone) {
  const masked = maskPhone(phone)
  return masked ? `手机号${masked}快速登录` : '手机号快捷登录'
}

Page({
  data: {
    step: 'welcome',
    agreed: false,
    phoneBtnText: '手机号快捷登录',
    loginError: '',
    redirect: '',
    user: null,
    draftNickname: '',
    draftStudyGoal: '',
    avatarDisplay: '',
    avatarUploading: false,
    saving: false,
    phoneLogging: false,
    canUseChooseAvatar: typeof wx.canIUse === 'function' ? wx.canIUse('button.open-type.chooseAvatar') : true,
    goalOptions: GOAL_OPTIONS,
  },

  onLoad(options) {
    let agreed = false
    let lastPhone = ''
    try {
      agreed = !!wx.getStorageSync(AGREE_KEY)
      lastPhone = wx.getStorageSync(LAST_PHONE_KEY) || ''
    } catch (e) {
      // ignore
    }
    this.setData({
      redirect: options.redirect ? decodeURIComponent(options.redirect) : '',
      agreed,
      phoneBtnText: phoneButtonText(lastPhone),
      step: 'welcome',
    })

    if (auth.isLoggedIn()) {
      this.resumeIfLoggedIn()
    }
  },

  _rememberPhone(phone) {
    if (!phone) return
    try {
      wx.setStorageSync(LAST_PHONE_KEY, String(phone))
    } catch (e) {
      // ignore
    }
    this.setData({ phoneBtnText: phoneButtonText(phone) })
  },

  async resumeIfLoggedIn() {
    this.setData({ step: 'loading', loginError: '' })
    try {
      const user = await request({ url: '/user/profile', silent: true, force: true })
      auth.syncAppUser(user)
      await this.applyUser(user)
    } catch (err) {
      this.setData({ step: 'welcome', loginError: '' })
    }
  },

  toggleAgree() {
    const agreed = !this.data.agreed
    this.setData({ agreed })
    try {
      wx.setStorageSync(AGREE_KEY, agreed)
    } catch (e) {
      // ignore
    }
  },

  openAgreement(e) {
    const type = e.currentTarget.dataset.type === 'privacy' ? 'privacy' : 'user'
    wx.navigateTo({
      url: `/packageProfile/pages/profile/agreement?type=${type}`,
    })
  },

  onNeedAgree() {
    wx.showToast({ title: '请先同意用户协议', icon: 'none' })
  },

  onSkipLogin() {
    if (getCurrentPages().length > 1) {
      wx.navigateBack({
        fail: () => wx.switchTab({ url: '/pages/home/index' }),
      })
      return
    }
    wx.switchTab({ url: '/pages/home/index' })
  },

  onCancelLoading() {
    this.setData({ step: 'welcome', phoneLogging: false, loginError: '' })
  },

  async onPhoneLogin(e) {
    if (!this.data.agreed) {
      this.onNeedAgree()
      return
    }
    const detail = e.detail || {}
    const code = detail.code
    if (!code) {
      const msg = String(detail.errMsg || '')
      const denied =
        msg.includes('deny') ||
        msg.includes('cancel') ||
        msg.includes('fail') ||
        detail.errno === 1400001
      if (denied) {
        // 登录规范：取消授权后须可退出，不得反复强制授权
        wx.showModal({
          title: '已取消授权',
          content: '你可以先浏览门店与套餐，需要预约时再回来登录。',
          confirmText: '先逛逛',
          cancelText: '留在此页',
          success: (res) => {
            if (res.confirm) this.onSkipLogin()
          },
        })
        return
      }
      wx.showToast({ title: '未获取到手机号，请重试', icon: 'none' })
      return
    }

    this.setData({ step: 'loading', loginError: '', phoneLogging: true })
    try {
      if (!auth.isLoggedIn()) {
        await auth.login({ silent: false, force: true })
      }
      const user = await request({
        url: '/user/bind-phone',
        method: 'POST',
        data: { code },
        force: true,
      })
      auth.syncAppUser(user)
      this._rememberPhone(user.phone)
      await this.applyUser(user)
    } catch (err) {
      this.setData({
        step: 'error',
        loginError: err.detail || err.message || '登录失败，请重试',
      })
    } finally {
      this.setData({ phoneLogging: false })
    }
  },

  async bootstrap() {
    // 兼容错误页「重试」：回到欢迎页走手机号授权
    this.setData({ step: 'welcome', loginError: '' })
  },

  async _tryApplyPendingInvite(user) {
    const pending = peekPendingInvite()
    if (!pending) return
    if (user && (user.invited_by || user.invite_code === pending)) {
      clearPendingInvite()
      return
    }
    try {
      await request({
        url: '/user/invite/apply',
        method: 'POST',
        data: { invite_code: pending },
        silent: true,
      })
      clearPendingInvite()
      invalidateCache('/user/profile')
    } catch (_) {
      clearPendingInvite()
    }
  },

  async applyUser(user, localAvatar) {
    await this._tryApplyPendingInvite(user)
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
    if (!this.data.agreed) {
      this.setData({ step: 'welcome' })
      return
    }
    this.setData({ step: 'welcome', loginError: '' })
  },

  async onChooseAvatar(e) {
    const avatarUrl = e?.detail?.avatarUrl
    if (!avatarUrl) {
      // 安卓或隐私未就绪时自动回退相册选择，确保点击一定有响应
      this.chooseAvatarFromAlbum()
      return
    }
    await this._uploadAvatarFile(avatarUrl)
  },

  onChooseAvatarError() {
    this.setData({ canUseChooseAvatar: false })
    this.chooseAvatarFromAlbum()
  },

  chooseAvatarFromAlbum() {
    if (this.data.avatarUploading) return
    const pick = typeof wx.chooseMedia === 'function'
      ? () => new Promise((resolve, reject) => {
        wx.chooseMedia({
          count: 1,
          mediaType: ['image'],
          sourceType: ['album', 'camera'],
          sizeType: ['compressed'],
          success: (res) => resolve(res?.tempFiles?.[0]?.tempFilePath || ''),
          fail: reject,
        })
      })
      : () => new Promise((resolve, reject) => {
        wx.chooseImage({
          count: 1,
          sizeType: ['compressed'],
          sourceType: ['album', 'camera'],
          success: (res) => resolve(res?.tempFilePaths?.[0] || ''),
          fail: reject,
        })
      })

    pick()
      .then((filePath) => {
        if (filePath) return this._uploadAvatarFile(filePath)
      })
      .catch((err) => {
        const msg = String((err && err.errMsg) || '')
        if (msg.includes('cancel')) return
        if (msg.includes('privacy') || msg.includes('scope')) {
          wx.showModal({
            title: '提示',
            content: '当前环境暂未开启头像相册权限，可直接点击下方「开始使用」使用默认头像进入。',
            showCancel: false,
            confirmColor: '#2D6A4F',
          })
          return
        }
        wx.showToast({ title: '可直接使用默认头像继续', icon: 'none' })
      })
  },

  async _uploadAvatarFile(avatarUrl) {
    if (!avatarUrl || this.data.avatarUploading) return

    this.setData({ avatarDisplay: avatarUrl, avatarUploading: true })
    wx.showLoading({ title: '同步头像...', mask: true })
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

  skipProfileSetup() {
    auth.finishLoginRedirect(this.data.redirect)
  },

  async saveProfile() {
    const { draftNickname, draftStudyGoal, saving, user, avatarUploading, avatarDisplay } = this.data
    if (saving || avatarUploading) return

    const fallbackName = `知行岛友${user?.id || ''}`.trim()
    const nickname = draftNickname.trim() || (user?.nickname && user.nickname !== auth.DEFAULT_NICKNAME ? user.nickname : fallbackName)
    const avatarTempPath = isLocalAvatarPath(avatarDisplay) ? avatarDisplay : undefined

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
      wx.showToast({ title: '欢迎加入知行岛', icon: 'success' })
      setTimeout(() => auth.finishLoginRedirect(this.data.redirect), 600)
    } catch (err) {
      wx.hideLoading()
      wx.showToast({ title: err.detail || err.message || '保存失败', icon: 'none' })
    } finally {
      this.setData({ saving: false })
    }
  },
})
