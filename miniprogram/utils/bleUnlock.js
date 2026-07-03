const { nightWindowForDate } = require('./cardDisplay')

const OPEN_EARLY_MS = 15 * 60000
const STORE_OPEN = { start: '07:30', end: '23:30', label: '营业' }

function parseTime(iso) {
  return new Date(String(iso).replace(' ', 'T'))
}

function formatDateOnly(d) {
  const pad = (n) => (n < 10 ? `0${n}` : `${n}`)
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}

function combineDateTime(dateStr, clock) {
  return new Date(`${dateStr}T${clock}:00`)
}

function reservationOpenWindow(reservation, now = new Date()) {
  if (!reservation || !reservation.start_time || !reservation.end_time) return null

  const resStart = parseTime(reservation.start_time)
  const resEnd = parseTime(reservation.end_time)
  const todayStr = formatDateOnly(now)
  const resStartDate = formatDateOnly(resStart)
  const resEndDate = formatDateOnly(resEnd)

  if (todayStr < resStartDate || todayStr > resEndDate) return null

  const billType = reservation.bill_type || 'hourly'
  const daily = billType === 'night' ? nightWindowForDate(todayStr) : STORE_OPEN

  let dayOpen = combineDateTime(todayStr, daily.start)
  dayOpen = new Date(dayOpen.getTime() - OPEN_EARLY_MS)
  const dayClose = combineDateTime(todayStr, daily.end)

  let openFrom
  let openUntil
  if (resStartDate === resEndDate && resStartDate === todayStr) {
    openFrom = new Date(Math.max(dayOpen.getTime(), resStart.getTime() - OPEN_EARLY_MS))
    openUntil = new Date(Math.min(dayClose.getTime(), resEnd.getTime()))
  } else if (resStartDate === todayStr) {
    openFrom = new Date(Math.max(dayOpen.getTime(), resStart.getTime() - OPEN_EARLY_MS))
    openUntil = dayClose
  } else if (resEndDate === todayStr) {
    openFrom = dayOpen
    openUntil = new Date(Math.min(dayClose.getTime(), resEnd.getTime()))
  } else {
    openFrom = dayOpen
    openUntil = dayClose
  }

  if (openUntil <= openFrom) return null
  return { openFrom, openUntil }
}

function computeCanOpen(reservation, now = new Date()) {
  if (!reservation) return false
  const window = reservationOpenWindow(reservation, now)
  if (!window) return false
  return now >= window.openFrom && now <= window.openUntil
}

function getOpenWindowHint(reservation, now = new Date()) {
  if (!reservation) return ''

  const resStart = parseTime(reservation.start_time)
  const resEnd = parseTime(reservation.end_time)
  const todayStr = formatDateOnly(now)
  const resStartDate = formatDateOnly(resStart)
  const resEndDate = formatDateOnly(resEnd)

  if (todayStr < resStartDate) {
    const pad = (n) => (n < 10 ? `0${n}` : `${n}`)
    return `${pad(resStart.getMonth() + 1)}月${pad(resStart.getDate())}日 起可开门`
  }
  if (todayStr > resEndDate) return '订单已结束，无法开门'

  const window = reservationOpenWindow(reservation, now)
  if (window && now >= window.openFrom && now <= window.openUntil) {
    return '已可开门，请站在门口操作'
  }

  const billType = reservation.bill_type || 'hourly'
  if (billType === 'night') {
    const win = nightWindowForDate(todayStr)
    return `${win.label}夜读时段 ${win.start}-${win.end} 可开门（可提前 15 分钟）`
  }
  return `营业时间 ${STORE_OPEN.start}-${STORE_OPEN.end} 可开门（可提前 15 分钟）`
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
      content: `${getOpenWindowHint(reservation, now)}。请在有效时段内再试。`,
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
  reservationOpenWindow,
  showOpenFailureModal,
}
