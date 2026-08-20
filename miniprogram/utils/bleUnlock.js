const { nightWindowForDate, STORE_OPEN } = require('./storeHours')

const NIGHT_BILL_TYPES = new Set(['night', 'night_monthly'])
const OPEN_EARLY_MS = 15 * 60000

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
  const daily = NIGHT_BILL_TYPES.has(billType) ? nightWindowForDate(todayStr) : STORE_OPEN

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
  if (todayStr > resEndDate) return '订单已结束'

  const window = reservationOpenWindow(reservation, now)
  if (window && now >= window.openFrom && now <= window.openUntil) {
    return '可开门'
  }

  const billType = reservation.bill_type || 'hourly'
  if (NIGHT_BILL_TYPES.has(billType)) {
    const win = nightWindowForDate(todayStr)
    return `${win.start}-${win.end} 可开门`
  }
  return `${STORE_OPEN.start}-${STORE_OPEN.end} 可开门`
}

function mapBleOpenFailure({ errorCode, errorMsg, canOpen, reservation }) {
  const raw = String(errorMsg || '')
  const msg = raw.toLowerCase()
  const code = Number(errorCode)

  // 不在可开门时间：优先提示时间窗/过期
  if (!canOpen && reservation) {
    const now = new Date()
    const end = parseTime(reservation.end_time)
    if (now > end) {
      return { content: '订单已过期，请重新预约' }
    }
    return { content: getOpenWindowHint(reservation, now) }
  }

  // 门锁忙：上一次开门操作还没结束
  if (raw.includes('正在操作中') || msg.includes('busy') || msg.includes('operating')) {
    return { content: '门锁正在响应上一次操作，请等约 2 秒后再按一次' }
  }

  // 手机蓝牙未开启 / 适配器不可用
  if (
    msg.includes('bluetooth')
    || raw.includes('蓝牙未开启')
    || raw.includes('蓝牙未打开')
    || msg.includes('adapter')
    || msg.includes('not available')
    || code === 10001
  ) {
    return { content: '手机蓝牙未开启，请下拉控制中心打开蓝牙后重试' }
  }

  // 蓝牙权限未授权
  if (
    msg.includes('permission')
    || msg.includes('authorize')
    || msg.includes('unauthorized')
    || raw.includes('授权')
    || raw.includes('权限')
  ) {
    return { content: '微信没有蓝牙权限，请到「设置 → 微信 → 蓝牙」开启后重试' }
  }

  // 连接超时
  if (
    msg.includes('timeout')
    || msg.includes('timed out')
    || raw.includes('超时')
    || code === 10012
  ) {
    return { content: '连接门锁超时，请把手机靠近门锁（1 米内）再试' }
  }

  // 未连接 / 找不到门锁 / 连接断开
  if (
    msg.includes('connect')
    || msg.includes('disconnect')
    || msg.includes('not found')
    || msg.includes('no device')
    || raw.includes('连接失败')
    || raw.includes('未找到')
    || raw.includes('未连接')
  ) {
    return { content: '没有连接到门锁，请靠近门锁（1 米内）并保持蓝牙开启后重试' }
  }

  // 钥匙 / lockData 失效
  if (msg.includes('key') || raw.includes('钥匙') || msg.includes('lockdata') || raw.includes('未生成')) {
    return { content: '开门钥匙已失效，已为你刷新，请重新点击开门', refresh: true }
  }

  // 门锁电量过低
  if (msg.includes('battery') || raw.includes('电量') || raw.includes('电池')) {
    return { content: '门锁电量过低，暂时无法开门，请联系店长处理' }
  }

  // 兜底：把真实原因和错误码写出来，避免“不知道是什么失败”
  const detail = raw.trim()
  const codePart = Number.isFinite(code) && code !== 0 ? `（代码 ${code}）` : ''
  if (detail) {
    return { content: `开门失败：${detail}${codePart}` }
  }
  return { content: `开门失败${codePart}，请靠近门锁重试；多次失败请联系店长` }
}

module.exports = {
  computeCanOpen,
  getOpenWindowHint,
  mapBleOpenFailure,
  reservationOpenWindow,
}
