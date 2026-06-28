const OPEN_EARLY_MS = 15 * 60000

function parseTime(iso) {
  return new Date(String(iso).replace(' ', 'T'))
}

function computeCanOpen(startTime, endTime, now = new Date()) {
  const start = parseTime(startTime)
  const end = parseTime(endTime)
  return now >= new Date(start.getTime() - OPEN_EARLY_MS) && now <= end
}

function getOpenWindowHint(reservation) {
  if (!reservation) return ''
  const start = parseTime(reservation.start_time)
  const openFrom = new Date(start.getTime() - OPEN_EARLY_MS)
  const pad = (n) => (n < 10 ? `0${n}` : `${n}`)
  return `${pad(openFrom.getHours())}:${pad(openFrom.getMinutes())} 起可开门`
}

function mapBleOpenFailure({ errorCode, errorMsg, canOpen, reservation, mode = 'ble' }) {
  const msg = String(errorMsg || '').toLowerCase()
  const code = Number(errorCode)

  if (!canOpen && reservation) {
    const now = new Date()
    const end = parseTime(reservation.end_time)
    if (now > end) {
      return {
        title: '订单已结束',
        content: '当前订单已过期，无法开门。如需继续学习请重新预约。',
        retryLabel: '',
        showRemote: false,
      }
    }
    return {
      title: '不在开门时段',
      content: `${getOpenWindowHint(reservation)}。请在有效时段内再试。`,
      retryLabel: '',
      showRemote: false,
    }
  }

  if (
    msg.includes('bluetooth')
    || msg.includes('蓝牙')
    || msg.includes('adapter')
    || code === 10001
  ) {
    return {
      title: '请开启蓝牙',
      content: '请在手机设置中打开蓝牙，并靠近门锁后重试。也可尝试远程开门。',
      retryLabel: '重试',
      showRemote: true,
    }
  }

  if (
    msg.includes('timeout')
    || msg.includes('超时')
    || msg.includes('timed out')
    || code === 10012
  ) {
    return {
      title: '连接超时',
      content: '未能在限时内连上门锁。请确认已靠近门锁、蓝牙已开启，然后重试。',
      retryLabel: '重试',
      showRemote: true,
    }
  }

  if (
    msg.includes('permission')
    || msg.includes('authorize')
    || msg.includes('授权')
  ) {
    return {
      title: '需要蓝牙权限',
      content: '请在小程序设置中允许使用蓝牙，然后返回重试。',
      retryLabel: '重试',
      showRemote: mode === 'ble',
    }
  }

  if (msg.includes('key') || msg.includes('钥匙') || msg.includes('lockdata')) {
    return {
      title: '钥匙无效',
      content: '开门钥匙未就绪或已过期，请下拉刷新页面后重试。',
      retryLabel: '刷新重试',
      showRemote: true,
      refresh: true,
    }
  }

  const detail = errorMsg || (mode === 'remote' ? '远程开门失败' : '蓝牙开门失败')
  return {
    title: mode === 'remote' ? '远程开门失败' : '开门失败',
    content: `${detail}。请靠近门锁重试，或联系店长协助。`,
    retryLabel: '重试',
    showRemote: mode === 'ble',
  }
}

function showOpenFailureModal(failure, { onRetry, onRemote, onRefresh } = {}) {
  const buttons = []
  if (failure.showRemote && typeof onRemote === 'function') {
    buttons.push({ text: '远程开门', action: onRemote })
  }
  if (failure.retryLabel) {
    buttons.push({
      text: failure.retryLabel,
      action: failure.refresh ? onRefresh : onRetry,
    })
  }
  buttons.push({ text: '知道了', action: null })

  const itemList = buttons.map((b) => b.text)
  wx.showActionSheet({
    itemList,
    success(res) {
      const picked = buttons[res.tapIndex]
      if (picked && typeof picked.action === 'function') {
        picked.action()
      }
    },
    fail() {
      wx.showModal({
        title: failure.title,
        content: failure.content,
        showCancel: false,
      })
    },
  })
}

module.exports = {
  computeCanOpen,
  getOpenWindowHint,
  mapBleOpenFailure,
  showOpenFailureModal,
}
