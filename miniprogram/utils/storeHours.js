/** 门店营业时间与夜读月卡时段（与后端 store_hours.py 一致） */

const STORE_OPEN = { start: '07:30', end: '23:30', label: '营业' }
const STORE_HOURS_LABEL = '7:30-23:30'

const OFFICE_NIGHT_USAGE_RULE =
  '工作日 18:00-23:30 · 周末 7:30-23:30 可入座（晚间固定座位，白天可与他人分时共用）'
const OFFICE_NIGHT_BOOKING_HINT =
  '选择开始使用日期即可，最长连续 30 天；每日具体时段在到店开门时校验'

function compareClock(a, b) {
  const [ah, am] = String(a || '00:00').split(':').map(Number)
  const [bh, bm] = String(b || '00:00').split(':').map(Number)
  return ah * 60 + am - (bh * 60 + bm)
}

function clampClock(clock, min, max) {
  if (compareClock(clock, min) < 0) return min
  if (compareClock(clock, max) > 0) return max
  return clock
}

function nightWindowForDate(dateStr) {
  const d = new Date(`${dateStr}T12:00:00`)
  const day = d.getDay()
  const isWeekend = day === 0 || day === 6
  return isWeekend
    ? { start: '07:30', end: '23:30', label: '周末' }
    : { start: '18:00', end: '23:30', label: '工作日' }
}

function defaultHourlyStartClock(dateStr, todayStr, nowClock) {
  if (dateStr === todayStr) {
    return clampClock(nowClock, STORE_OPEN.start, STORE_OPEN.end)
  }
  return STORE_OPEN.start
}

function validateStoreTimeRange(dateStr, startClock, endClock) {
  if (compareClock(startClock, STORE_OPEN.start) < 0) {
    return `开始时间不能早于营业时间 ${STORE_OPEN.start}`
  }
  if (compareClock(startClock, STORE_OPEN.end) > 0) {
    return `开始时间不能晚于营业时间 ${STORE_OPEN.end}`
  }
  if (compareClock(endClock, STORE_OPEN.start) < 0) {
    return `结束时间不能早于营业时间 ${STORE_OPEN.start}`
  }
  if (compareClock(endClock, STORE_OPEN.end) > 0) {
    return `结束时间不能晚于营业时间 ${STORE_OPEN.end}`
  }
  if (compareClock(endClock, startClock) <= 0) {
    return '结束时间须晚于开始时间'
  }
  return ''
}

function clampHourlyClocks(dateStr, startClock, endClock) {
  let start = clampClock(startClock, STORE_OPEN.start, STORE_OPEN.end)
  let end = clampClock(endClock, STORE_OPEN.start, STORE_OPEN.end)
  if (compareClock(end, start) <= 0) {
    end = STORE_OPEN.end
    if (compareClock(end, start) <= 0) start = STORE_OPEN.start
  }
  return { startClock: start, endClock: end }
}

module.exports = {
  STORE_OPEN,
  STORE_HOURS_LABEL,
  OFFICE_NIGHT_USAGE_RULE,
  OFFICE_NIGHT_BOOKING_HINT,
  compareClock,
  clampClock,
  nightWindowForDate,
  defaultHourlyStartClock,
  validateStoreTimeRange,
  clampHourlyClocks,
}
