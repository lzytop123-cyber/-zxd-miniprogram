function hourlyAllowsMultiUse(card) {
  if (!card || card.card_type !== 'hourly') return false
  if (card.total_hours != null) return Number(card.total_hours) >= 50
  if (Number(card.remaining_hours) >= 50) return true
  const name = card.card_name || ''
  return name.includes('50') && name.includes('小时')
}

/** @deprecated 使用 hourlyAllowsMultiUse */
function hourlyAllowsPartialUse(card) {
  return hourlyAllowsMultiUse(card)
}

function hourlyRuleText(card) {
  if (hourlyAllowsMultiUse(card)) {
    return '按实际时长扣减，可多次预约'
  }
  const h = card.remaining_hours != null ? card.remaining_hours : ''
  return `可约 ≤${h} 小时，一次性核销`
}

function hourlyDetailLines(card) {
  if (hourlyAllowsMultiUse(card)) {
    return [
      '按实际预约时长扣减',
      '有效期内可多次使用',
    ]
  }
  return [
    '可少于卡面时长（如 4h 卡约 3h）',
    '完成预约后一次性核销',
  ]
}

function dailyPassDays(card) {
  if (card.daily_pass_days != null) return Number(card.daily_pass_days)
  if (card.total_sessions != null && Number(card.total_sessions) > 1) {
    return Number(card.total_sessions)
  }
  if (!card.start_date || !card.end_date) return 1
  const span = Math.floor(
    (new Date(`${card.end_date}T00:00:00`) - new Date(`${card.start_date}T00:00:00`)) / 86400000
  ) + 1
  if (span <= 7) return span
  return 1
}

function dailyRuleText(card) {
  const span = dailyPassDays(card)
  if (span > 1 && card.start_date && card.end_date) {
    const window = Math.floor(
      (new Date(`${card.end_date}T00:00:00`) - new Date(`${card.start_date}T00:00:00`)) / 86400000
    ) + 1
    if (window > 7) {
      return `${window} 天内须预约连续 ${span} 天`
    }
    return `连续 ${span} 天不限时，须一次约满 ${card.start_date} 至 ${card.end_date}`
  }
  return RULE_LINES.daily
}

function dailyDetailLines(card) {
  const span = dailyPassDays(card)
  if (span > 1) {
    return [
      '兑换即开卡，连续自然日有效',
      `须一次预约连续 ${span} 天（不可拆分）`,
      '完成预约后该卡核销',
    ]
  }
  return CARD_DETAIL_LINES.daily
}

const TYPE_LABELS = {
  daily: '天卡',
  weekly: '周卡',
  monthly: '月卡',
  quarterly: '季卡',
  session: '次卡',
  hourly: '小时卡',
  night_monthly: '夜读月卡',
}

const {
  OFFICE_NIGHT_USAGE_RULE,
  OFFICE_NIGHT_BOOKING_HINT,
  nightWindowForDate,
  compareClock,
  clampClock: clampNightClock,
} = require('./storeHours')

function isOfficeNightMonthlyCard(card) {
  if (!card) return false
  if (card.card_type === 'night_monthly') return true
  if (card.usage_rule) return true
  if (card.card_type !== 'monthly') return false
  const name = String(card.card_name || '').replace(/\s/g, '')
  if (name.includes('上班族') || name.includes('晚自习') || name.includes('夜读')) return true
  return !!(card.daily_start)
}

function normalizeNightBookingTimes(dateStr, startClock, endClock) {
  const win = nightWindowForDate(dateStr)
  let start = clampNightClock(startClock, win.start, win.end)
  let end = clampNightClock(endClock, win.start, win.end)
  if (compareClock(end, start) <= 0) {
    end = win.end
    if (compareClock(end, start) <= 0) start = win.start
  }
  return {
    startClock: start,
    endClock: end,
    nightHint: `${win.label}可选 ${win.start}-${win.end}`,
  }
}

function validateNightBookingTimes(dateStr, startClock, endClock) {
  const win = nightWindowForDate(dateStr)
  if (compareClock(startClock, win.start) < 0) {
    return `${win.label}开始时间不能早于 ${win.start}`
  }
  if (compareClock(startClock, win.end) > 0) {
    return `${win.label}开始时间不能晚于 ${win.end}`
  }
  if (compareClock(endClock, win.start) < 0) {
    return `${win.label}结束时间不能早于 ${win.start}`
  }
  if (compareClock(endClock, win.end) > 0) {
    return `${win.label}结束时间不能晚于 ${win.end}`
  }
  if (compareClock(endClock, startClock) <= 0) {
    return '结束时间须晚于开始时间'
  }
  return ''
}

const RULE_LINES = {
  daily: '效期内预约一次即核销',
  weekly: '效期内须一次预约连续 7 天',
  monthly: '效期内须一次预约连续 30 天',
  quarterly: '效期内预约一次即核销',
  session: '按自然日扣次',
  hourly: '可约不超过卡面时长，一次性核销',
  night_monthly: '效期内须一次预约连续 30 天',
}

const CARD_DETAIL_LINES = {
  daily: [
    '兑换或购买后即时开卡',
    '全天不限时，预约一次即核销',
  ],
  weekly: [
    '兑换即开卡，效期见卡面日期',
    '效期内须一次预约连续 7 天',
  ],
  monthly: [
    '兑换即开卡，效期见卡面日期',
    '效期内须一次预约连续 30 天',
  ],
  quarterly: [
    '连续90个自然日有效',
    '90天内预约一次即核销',
  ],
  session: [
    '按自然日扣次',
    '有效期内可多次预约',
  ],
  hourly: [
    '可少于卡面时长',
    '完成预约后一次性核销',
  ],
  night_monthly: [
    OFFICE_NIGHT_USAGE_RULE,
    '预约时选「夜读」，须一次约满连续 30 天',
  ],
}

const PKG_CATEGORY_TABS = [
  { key: 'all', label: '全部' },
  { key: 'duration', label: '时长卡', types: ['daily', 'weekly', 'monthly', 'quarterly'] },
  { key: 'session', label: '次卡', types: ['session'] },
  { key: 'night', label: '夜读', types: ['night_monthly'] },
]

const PKG_HINTS = {
  daily: { tag: '1天内有效', rule: '全天不限时，用一次即核销' },
  weekly: { tag: '效期见卡面', rule: '效期内须一次预约连续 7 天' },
  monthly: { tag: '效期见卡面', rule: '效期内须一次预约连续 30 天' },
  quarterly: { tag: '90天内有效', rule: '90天内完成一次预约即核销' },
  session: { tag: '按次扣减', rule: '连选N天扣N次' },
  night_monthly: { tag: '30天夜读', rule: '效期内须连续 30 天 · ' + OFFICE_NIGHT_USAGE_RULE },
}

const MONTHLY_CARD_USE_DAYS = 180

function officeNightPassDays(card) {
  if (!isOfficeNightMonthlyCard(card)) return 0
  if (card.total_sessions != null && Number(card.total_sessions) > 1) {
    return Number(card.total_sessions)
  }
  return 30
}

function inferPassDaysFromCardName(name) {
  const text = String(name || '').replace(/\s/g, '').replace(/　/g, '')
  if (/双月|两个月|2个月/.test(text)) return 60
  if (/四个月|4个月/.test(text)) return 120
  if (/三个月|3个月/.test(text)) return 90
  return 0
}

function formatPassDurationLabel(span) {
  const days = Number(span) || 0
  if (days >= 30 && days % 30 === 0) return `连续${days / 30}个月`
  if (days > 0) return `连续${days}天`
  return ''
}

function monthlyPassDays(card) {
  if (!card || card.card_type !== 'monthly') return 0
  if (isOfficeNightMonthlyCard(card)) return 0
  const inferred = inferPassDaysFromCardName(card.card_name)
  if (inferred) return inferred
  if (card.period_pass_days != null && Number(card.period_pass_days) > 0) {
    return Number(card.period_pass_days)
  }
  if (card.total_sessions != null && Number(card.total_sessions) > 1) {
    return Number(card.total_sessions)
  }
  return 30
}

function quarterlyPassDays(card) {
  if (!card || card.card_type !== 'quarterly') return 0
  if (card.period_pass_days != null && Number(card.period_pass_days) > 0) {
    return Number(card.period_pass_days)
  }
  if (card.total_sessions != null && Number(card.total_sessions) > 1) {
    return Number(card.total_sessions)
  }
  return 90
}

function periodPassSpan(billType, card) {
  if (card) {
    if (card.period_pass_days != null && Number(card.period_pass_days) > 0) {
      return Number(card.period_pass_days)
    }
    if (billType === 'weekly') return weeklyPassDays(card)
    if (billType === 'monthly') return monthlyPassDays(card)
    if (billType === 'quarterly') return quarterlyPassDays(card)
    if (billType === 'night') return officeNightPassDays(card)
  }
  if (billType === 'weekly') return 7
  if (billType === 'monthly') return 30
  if (billType === 'quarterly') return 90
  return 0
}

function weeklyPassDays(card) {
  if (!card || card.card_type !== 'weekly') return 0
  if (card.total_sessions != null && Number(card.total_sessions) > 1) {
    return Number(card.total_sessions)
  }
  return 7
}

function cardValidUntil(card) {
  return (card && card.end_date) || ''
}

/** 预约开始日须在卡面效期内。 */
function withinCardValidity(card, startIso) {
  if (!card) return false
  const start = startIso.slice(0, 10)
  if (card.start_date && start < card.start_date) return false
  if (card.end_date && start > card.end_date) return false
  return true
}

/** @deprecated 使用 cardValidUntil */
function monthlyCardUseDeadline(card) {
  return cardValidUntil(card)
}

/** @deprecated 使用 withinCardValidity */
function withinMonthlyCardUseWindow(card, startIso) {
  return withinCardValidity(card, startIso)
}

const PERIOD_PASS_TYPES = new Set(['daily', 'weekly', 'monthly', 'quarterly', 'night_monthly'])

/** 卡面效期天数（兑换后），与 pricing valid_days（预约跨度）不同 */
const CARD_FACE_VALIDITY_DAYS = {
  daily: 90,
  weekly: 90,
  monthly: 180,
  quarterly: 180,
  night_monthly: 90,
  session: { 10: 90, 30: 360, _default: 90 },
}

function isPeriodPassCard(card) {
  return PERIOD_PASS_TYPES.has(resolveCardType(card))
}

function todayDateStr() {
  const d = new Date()
  const pad = (n) => (n < 10 ? '0' + n : '' + n)
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}

function validityDaysRemaining(card) {
  if (!card || !card.end_date) return null
  if (card.validity_days_remaining != null) return Number(card.validity_days_remaining)
  const t = new Date(`${todayDateStr()}T00:00:00`)
  const e = new Date(`${card.end_date}T00:00:00`)
  return Math.floor((e - t) / 86400000)
}

function formatValidityRange(card) {
  if (card.validity_range) return card.validity_range
  if (card.start_date && card.end_date) return `${card.start_date} ~ ${card.end_date}`
  if (card.end_date) return `至 ${card.end_date}`
  if (card.start_date) return `${card.start_date} 起`
  return ''
}

function formatValidityRemain(card) {
  const left = validityDaysRemaining(card)
  if (left == null) return { text: '', urgent: false }
  if (left < 0) return { text: '已过期', urgent: true }
  if (left === 0) return { text: '今日到期', urgent: true }
  if (isPeriodPassCard(card)) {
    if (left <= 7) return { text: `${left} 天后到期`, urgent: true }
    return { text: '', urgent: false }
  }
  if (left <= 7) return { text: `剩 ${left} 天`, urgent: true }
  return { text: `剩 ${left} 天`, urgent: false }
}

function resolveCardType(card) {
  if (!card) return ''
  if (isOfficeNightMonthlyCard(card)) return 'night_monthly'
  return card.card_type
}

function cardRuleText(card) {
  const displayType = resolveCardType(card)
  if (displayType === 'hourly') return hourlyRuleText(card)
  if (displayType === 'daily') return dailyRuleText(card)
  if (displayType === 'weekly') {
    const span = weeklyPassDays(card)
    return span ? `效期内须一次预约连续 ${span} 天` : RULE_LINES.weekly
  }
  if (displayType === 'monthly') {
    const span = monthlyPassDays(card)
    return span ? `效期内须一次预约连续 ${span} 天` : RULE_LINES.monthly
  }
  if (displayType === 'quarterly') {
    const span = quarterlyPassDays(card)
    return span > 1 ? `效期内须一次预约连续 ${span} 天` : RULE_LINES.quarterly
  }
  if (displayType === 'night_monthly') {
    const span = officeNightPassDays(card)
    return span ? `效期内须一次预约连续 ${span} 天` : RULE_LINES.night_monthly
  }
  return RULE_LINES[displayType] || ''
}

function formatValidity(card) {
  const range = formatValidityRange(card)
  const { text: remain } = formatValidityRemain(card)
  if (range && remain) return `效期 ${range} · ${remain}`
  if (range) {
    return isPeriodPassCard(card) ? `效期 ${range} · 待预约` : `效期 ${range}`
  }
  return remain
}

/** 紧凑展示：顶部 chip、预约提示 */
function formatValidityShort(card) {
  const range = formatValidityRange(card)
  const { text: remain } = formatValidityRemain(card)
  if (remain) return remain
  if (range) {
    if (isPeriodPassCard(card) && card.end_date) return `效期至 ${card.end_date}`
    return range
  }
  return ''
}

/** 预约页关联卡提示：卡名 + 效期 + 可选后缀 */
function cardValidityHint(card, suffix) {
  if (!card) return suffix || ''
  const c = card.validityRangeText != null ? card : formatCard(card)
  const name = c.card_name ? `「${c.card_name}」` : ''
  const base = c.validityRangeText ? `效期 ${c.validityRangeText}` : (c.validityText || '')
  const parts = [name, base].filter(Boolean)
  if (c.validityRemainUrgent && c.validityRemainText) {
    parts.push(c.validityRemainText)
  }
  if (suffix) parts.push(suffix)
  return parts.join('，')
}

function formatRemain(card) {
  if (card.remaining_sessions != null) return `剩余 ${card.remaining_sessions} 次`
  if (card.remaining_hours != null) return `剩余 ${card.remaining_hours} 小时`
  return ''
}

function isCardUsable(card) {
  if (card.card_type === 'hourly') return Number(card.remaining_hours) > 0
  if (card.card_type === 'session') return Number(card.remaining_sessions) > 0
  return true
}

function cardBillTypeForBooking(card) {
  if (!card) return ''
  if (card.displayType === 'night_monthly' || card.card_type === 'night_monthly') return 'night'
  if (isOfficeNightMonthlyCard(card)) return 'night'
  if (card.card_type === 'hourly') return 'hourly'
  if (card.card_type === 'session') return 'session'
  if (card.card_type === 'daily') return 'daily'
  if (['weekly', 'monthly', 'quarterly'].includes(card.card_type)) return card.card_type
  return card.card_type || ''
}

function formatCardSourcePrefix(card) {
  if (!card || !card.source) return ''
  if (card.source === 'meituan') return '美团'
  if (card.source === 'douyin') return '抖音'
  if (card.source === 'purchase') return ''
  return ''
}

function formatCard(card) {
  const displayType = resolveCardType(card)
  const ruleText = cardRuleText(card)
  const span = displayType === 'daily' ? dailyPassDays(card) : 0
  const validityRangeText = formatValidityRange(card)
  const { text: validityRemainText, urgent: validityRemainUrgent } = formatValidityRemain(card)
  const validityText = formatValidity(card)
  const validityShort = formatValidityShort(card)
  const remainText = formatRemain(card)
  const sourcePrefix = formatCardSourcePrefix(card)
  let chipMeta = (displayType === 'hourly' || displayType === 'session')
    ? (remainText || validityShort || ruleText)
    : (validityShort || ruleText)
  if (sourcePrefix && chipMeta) chipMeta = `${sourcePrefix} · ${chipMeta}`
  else if (sourcePrefix && !chipMeta) chipMeta = sourcePrefix
  return {
    ...card,
    displayType,
    typeLabel: span > 1 ? `${span}天卡` : (TYPE_LABELS[displayType] || TYPE_LABELS[card.card_type] || '期限卡'),
    validityRangeText,
    validityRemainText,
    validityRemainUrgent,
    validityText,
    validityShort,
    remainText,
    ruleText,
    chipMeta,
    hourlyMultiUse: displayType === 'hourly' ? hourlyAllowsMultiUse(card) : false,
  }
}

function buildCardDetail(card) {
  const displayType = resolveCardType(card)
  const lines = displayType === 'hourly'
    ? [...hourlyDetailLines(card)]
    : (displayType === 'daily' ? [...dailyDetailLines(card)] : [...(CARD_DETAIL_LINES[displayType] || CARD_DETAIL_LINES[card.card_type] || [])])
  if (card.validityRangeText) {
    lines.unshift(`效期 ${card.validityRangeText}`)
  } else if (card.validityText) {
    lines.unshift(card.validityText)
  }
  if (card.validityRemainText) lines.unshift(card.validityRemainText)
  if (card.remainText) lines.unshift(card.remainText)
  if (card.daily_start) lines.push(`可用时段：${card.daily_start} 起`)
  if (isOfficeNightMonthlyCard(card)) {
    lines.push(OFFICE_NIGHT_USAGE_RULE)
  }
  return {
    mode: 'owned',
    title: card.card_name || card.typeLabel,
    subtitle: card.typeLabel,
    lines,
  }
}

function packageFaceValidityDays(item) {
  const billType = item.bill_type
  if (billType === 'session') {
    const count = item.session_count || item.valid_days || 10
    const map = CARD_FACE_VALIDITY_DAYS.session
    return map[count] || map._default
  }
  return CARD_FACE_VALIDITY_DAYS[billType] || null
}

function enrichPackage(item) {
  const hint = PKG_HINTS[item.bill_type] || {}
  const sessionCount = item.session_count
  let tag = hint.tag

  if (item.bill_type === 'session') {
    const count = sessionCount || item.valid_days || 10
    const faceDays = packageFaceValidityDays(item)
    tag = faceDays ? `${faceDays}天效期 · 含${count}次` : `含 ${count} 次`
  } else {
    const faceDays = packageFaceValidityDays(item)
    if (faceDays) {
      tag = `${faceDays}天效期`
    } else if (item.bill_type === 'daily') {
      tag = hint.tag
    }
  }

  const priceText = Number(item.price).toFixed(item.price % 1 === 0 ? 0 : 2)
  const ruleText = item.remark || hint.rule || '购买后进「我的期限卡」'

  return {
    ...item,
    tagText: tag || '',
    ruleText,
    priceText,
  }
}

function buildPackageDetail(pkg) {
  const lines = []
  const faceDays = packageFaceValidityDays(pkg)
  if (faceDays) {
    lines.push(`兑换后 ${faceDays} 天效期内可预约`)
  } else if (pkg.tagText) {
    lines.push(pkg.tagText)
  }
  if (pkg.remark) lines.push(pkg.remark)
  lines.push(...(CARD_DETAIL_LINES[pkg.bill_type] || []))
  if (!pkg.remark) lines.push('购买后进「我的期限卡」')

  return {
    mode: 'buy',
    title: pkg.label,
    subtitle: `¥${pkg.priceText}`,
    lines,
    bill_type: pkg.bill_type,
    priceText: pkg.priceText,
  }
}

function filterPackages(packages, tabKey) {
  const tab = PKG_CATEGORY_TABS.find((t) => t.key === tabKey) || PKG_CATEGORY_TABS[0]
  if (tab.key === 'all') return packages
  return packages.filter((p) => tab.types.includes(p.bill_type))
}

module.exports = {
  TYPE_LABELS,
  PKG_CATEGORY_TABS,
  OFFICE_NIGHT_USAGE_RULE,
  OFFICE_NIGHT_BOOKING_HINT,
  formatCard,
  formatValidity,
  formatValidityShort,
  cardValidityHint,
  validityDaysRemaining,
  isCardUsable,
  isOfficeNightMonthlyCard,
  cardBillTypeForBooking,
  officeNightPassDays,
  monthlyPassDays,
  weeklyPassDays,
  quarterlyPassDays,
  periodPassSpan,
  formatPassDurationLabel,
  cardValidUntil,
  withinCardValidity,
  monthlyCardUseDeadline,
  withinMonthlyCardUseWindow,
  MONTHLY_CARD_USE_DAYS,
  nightWindowForDate,
  normalizeNightBookingTimes,
  validateNightBookingTimes,
  hourlyAllowsMultiUse,
  hourlyAllowsPartialUse,
  dailyPassDays,
  enrichPackage,
  filterPackages,
  buildCardDetail,
  buildPackageDetail,
}
