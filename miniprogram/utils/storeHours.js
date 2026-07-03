/** 门店营业时间与夜读月卡时段（与后端 store_hours.py 一致） */

const STORE_OPEN = { start: '07:30', end: '23:30', label: '营业' }
const STORE_HOURS_LABEL = '7:30-23:30'

const OFFICE_NIGHT_USAGE_RULE =
  '工作日 18:00-23:30，周末 7:30-23:30'
const OFFICE_NIGHT_BOOKING_HINT =
  '选开始日期，最长30天；入座时段以开门时为准'

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
    ? { start: '07:30', end: '23:30', label: '周六日' }
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

/** 日期型预约（天/周/月/季/次卡）：首日 7:30、末日 23:30 */
function storeRangeDateTimes(startDate, endDate) {
  return {
    start: new Date(`${startDate}T${STORE_OPEN.start}:00`),
    end: new Date(`${endDate}T${STORE_OPEN.end}:00`),
  }
}

/** 夜读月卡：按自然日，每日时段开门时校验 */
function nightRangeDateTimes(startDate, endDate) {
  return {
    start: new Date(`${startDate}T00:00:00`),
    end: new Date(`${endDate}T23:59:59`),
  }
}

/** 指定日期 + 时刻 */
function clockRangeDateTimes(startDate, startClock, endDate, endClock) {
  return {
    start: new Date(`${startDate}T${startClock}:00`),
    end: new Date(`${endDate}T${endClock}:00`),
  }
}

function defaultDailyClocks(startDate, todayStr, nowClock) {
  return {
    startClock: defaultHourlyStartClock(startDate, todayStr, nowClock),
    endClock: STORE_OPEN.end,
  }
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
  defaultDailyClocks,
  validateStoreTimeRange,
  clampHourlyClocks,
  storeRangeDateTimes,
  nightRangeDateTimes,
  clockRangeDateTimes,
}
