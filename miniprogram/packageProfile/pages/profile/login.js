const auth = require('../../../utils/auth')
const { request } = require('../../../utils/request')
const { normalizeUser, pickAvatarDisplay } = require('../../../utils/user')

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
    const type = e.currentTarget.dataset.type
    const title = type === 'privacy' ? '隐私协议' : '用户协议'
    const content =
      type === 'privacy'
        ? '我们将依法保护你的个人信息，仅用于账号登录、预约自习、开门与客服沟通等必要场景。未经同意不会向无关第三方出售你的个人信息。'
        : '欢迎使用知行岛自习室小程序。注册/登录即表示你同意遵守门店秩序，合理使用座位与期限卡权益，不得转让账号从事违法违规活动。'
    wx.showModal({
      title,
      content,
      showCancel: false,
      confirmText: '知道了',
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

  onSkipSetup() {
    // 资料可稍后完善，不得卡住审核员/用户
    auth.finishLoginRedirect(this.data.redirect)
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
    if (!this.data.agreed) {
      this.setData({ step: 'welcome' })
      return
    }
    this.setData({ step: 'welcome', loginError: '' })
  },

  async onChooseAvatar(e) {
    const avatarUrl = e?.detail?.avatarUrl
    if (!avatarUrl) {
      wx.showToast({ title: '未获取到头像，请用相册上传', icon: 'none' })
      return
    }
    await this._uploadAvatarFile(avatarUrl)
  },

  pickAvatarFromAlbum() {
    if (this.data.avatarUploading) return
    wx.chooseMedia({
      count: 1,
      mediaType: ['image'],
      sourceType: ['album', 'camera'],
      success: (res) => {
        const path = res.tempFiles && res.tempFiles[0] && res.tempFiles[0].tempFilePath
        if (!path) {
          wx.showToast({ title: '未选择图片', icon: 'none' })
          return
        }
        this._uploadAvatarFile(path)
      },
      fail: (err) => {
        const msg = String(err?.errMsg || '')
        if (msg.includes('cancel') || msg.includes('deny')) return
        wx.showToast({ title: '选择图片失败', icon: 'none' })
      },
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
      // 上传失败仍保留本地预览，保存资料时会再传
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
