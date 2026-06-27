const { resolveStaticUrl } = require('../config')
const { resolveImageForDisplay } = require('./media')

/** 解析用户头像供 <image> 展示（本地 HTTP 会下载到沙箱） */
async function normalizeUser(user) {
  if (!user) return user
  const next = { ...user }
  if (next.avatar_url) {
    try {
      next.avatar_url = await resolveImageForDisplay(next.avatar_url)
    } catch (err) {
      // 模拟器不能直接显示 http:// 图片，下载失败时不回填 HTTP 地址
      next.avatar_url = ''
    }
  }
  return next
}

/** 优先用本地临时路径展示（chooseAvatar 返回的 wxfile://） */
function pickAvatarDisplay(localPath, user) {
  if (localPath) return localPath
  if (user?.avatar_url && !String(user.avatar_url).startsWith('http://')) {
    return user.avatar_url
  }
  return ''
}

module.exports = { normalizeUser, pickAvatarDisplay }
