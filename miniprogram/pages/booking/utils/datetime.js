/** 格式化为本地时间字符串（不带时区） */
function pad(n) {
  return n < 10 ? '0' + n : '' + n
}

function formatLocalDateTime(d) {
  return (
    `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}` +
    `T${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
  )
}

function todayStr() {
  return formatLocalDateTime(new Date()).slice(0, 10)
}

function addDays(dateStr, days) {
  const d = new Date(`${dateStr}T12:00:00`)
  d.setDate(d.getDate() + days)
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}

function combineDateTime(dateStr, timeStr) {
  const t = timeStr.length === 5 ? `${timeStr}:00` : timeStr
  return `${dateStr}T${t}`
}

function roundUp15min(d) {
  const r = new Date(d)
  r.setMinutes(Math.ceil(r.getMinutes() / 15) * 15, 0, 0)
  return r
}

function nowTimeStr() {
  const d = roundUp15min(new Date())
  return `${pad(d.getHours())}:${pad(d.getMinutes())}`
}

module.exports = {
  formatLocalDateTime,
  todayStr,
  addDays,
  combineDateTime,
  roundUp15min,
  nowTimeStr,
  pad,
}
