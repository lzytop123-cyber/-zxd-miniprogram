function hourlyAllowsPartialUse(card) {
  if (card.total_hours != null) return Number(card.total_hours) >= 50
  if (Number(card.remaining_hours) >= 50) return true
  const name = card.card_name || ''
  return name.includes('50') && name.includes('小时')
}

function hourlyRuleText(card) {
  if (hourlyAllowsPartialUse(card)) {
    return '按小时扣减，可多次预约直至小时用完'
  }
  return '须一次性预约用完剩余时长，核销后失效'
}

function hourlyDetailLines(card) {
  if (hourlyAllowsPartialUse(card)) {
    return [
      '按小时扣减，预约时自动抵扣',
      '可在有效期内多次使用直至小时用完',
    ]
  }
  return [
    '须一次性预约用完剩余全部时长',
    '核销后该卡失效，不可分次使用',
  ]
}

function dailyPassDays(card) {
  if (card.daily_pass_days != null) return Number(card.daily_pass_days)
  if (!card.start_date || !card.end_date) return 1
  const s = new Date(`${card.start_date}T00:00:00`)
  const e = new Date(`${card.end_date}T00:00:00`)
  return Math.floor((e - s) / 86400000) + 1
}

function dailyRuleText(card) {
  const span = dailyPassDays(card)
  if (span > 1) {
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

const OFFICE_NIGHT_USAGE_RULE = '可提前预约固定座位 · 每日可用：工作日 18:00-23:30 · 周末 7:30-23:30（开门时生效）'
const OFFICE_NIGHT_BOOKING_HINT = '选择开始使用日期即可，最长连续 30 天；每日具体时段在到店开门时校验'

function isOfficeNightMonthlyCard(card) {
  if (!card) return false
  if (card.card_type === 'night_monthly') return true
  if (card.usage_rule) return true
  if (card.card_type !== 'monthly') return false
  const name = String(card.card_name || '').replace(/\s/g, '')
  if (name.includes('上班族') || name.includes('晚自习') || name.includes('夜读')) return true
  return !!(card.daily_start)
}

function nightWindowForDate(dateStr) {
  const d = new Date(`${dateStr}T12:00:00`)
  const day = d.getDay()
  const isWeekend = day === 0 || day === 6
  return isWeekend
    ? { start: '07:30', end: '23:30', label: '周末' }
    : { start: '18:00', end: '23:30', label: '工作日' }
}

function compareClock(a, b) {
  const [ah, am] = String(a || '00:00').split(':').map(Number)
  const [bh, bm] = String(b || '00:00').split(':').map(Number)
  return ah * 60 + am - (bh * 60 + bm)
}

function clampNightClock(clock, min, max) {
  if (compareClock(clock, min) < 0) return min
  if (compareClock(clock, max) > 0) return max
  return clock
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
  daily: '全天不限时，用一次即核销',
  weekly: '7天内完成一次预约即核销',
  monthly: '开卡后30天内可预约一次，使用后即失效',
  quarterly: '90天内完成一次预约即核销',
  session: '按自然日扣次，连选N天扣N次',
  hourly: '须一次性预约用完剩余时长',
  night_monthly: '30天内固定座位，完成一次预约即核销',
}

const CARD_DETAIL_LINES = {
  daily: [
    '兑换或购买后即时开卡',
    '全天不限时，完成一次预约即核销',
    '需在有效期内使用',
  ],
  weekly: [
    '兑换即开卡，连续7个自然日有效',
    '7天内完成一次预约即核销',
    '不可暂停',
  ],
  monthly: [
    '兑换即开卡，连续30个自然日有效',
    '30天内可预约一次，使用后即失效',
    '不可暂停',
  ],
  quarterly: [
    '兑换即开卡，连续90个自然日有效',
    '90天内完成一次预约即核销',
    '不可暂停',
  ],
  session: [
    '按自然日扣次，连选N天扣N次',
    '可在有效期内多次预约直至次数用完',
  ],
  hourly: [
    '按小时扣减，预约时自动抵扣',
    '可在有效期内多次使用直至小时用完',
  ],
  night_monthly: [
    OFFICE_NIGHT_USAGE_RULE,
    '选座时请选择「夜读」套餐，默认预约30天',
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
  weekly: { tag: '7天内有效', rule: '7天内完成一次预约即核销' },
  monthly: { tag: '30天内有效', rule: '开卡后30天内可预约一次' },
  quarterly: { tag: '90天内有效', rule: '90天内完成一次预约即核销' },
  session: { tag: '按次扣减', rule: '连选N天扣N次' },
  night_monthly: { tag: '30天夜读', rule: OFFICE_NIGHT_USAGE_RULE },
}

function formatValidity(card) {
  if (card.card_type === 'monthly' && card.start_date && card.end_date) {
    return `${card.start_date} 至 ${card.end_date} · 不可暂停`
  }
  if (card.start_date && card.end_date && ['weekly', 'quarterly', 'night_monthly'].includes(card.card_type)) {
    return `兑换即开卡 · ${card.start_date} 至 ${card.end_date}`
  }
  if (card.end_date) return `有效期至 ${card.end_date}`
  return ''
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

function formatCard(card) {
  const ruleText = card.card_type === 'hourly'
    ? hourlyRuleText(card)
    : (card.card_type === 'daily' ? dailyRuleText(card) : (RULE_LINES[card.card_type] || ''))
  const span = card.card_type === 'daily' ? dailyPassDays(card) : 0
  return {
    ...card,
    typeLabel: span > 1 ? `${span}天卡` : (TYPE_LABELS[card.card_type] || '期限卡'),
    validityText: formatValidity(card),
    remainText: formatRemain(card),
    ruleText,
    hourlyMultiUse: card.card_type === 'hourly' ? hourlyAllowsPartialUse(card) : false,
  }
}

function buildCardDetail(card) {
  const lines = card.card_type === 'hourly'
    ? [...hourlyDetailLines(card)]
    : (card.card_type === 'daily' ? [...dailyDetailLines(card)] : [...(CARD_DETAIL_LINES[card.card_type] || [])])
  if (card.validityText) lines.unshift(card.validityText)
  if (card.remainText) lines.unshift(card.remainText)
  if (card.daily_start) lines.push(`可用时段：${card.daily_start} 起`)
  if (isOfficeNightMonthlyCard(card)) lines.push(OFFICE_NIGHT_USAGE_RULE)
  return {
    mode: 'owned',
    title: card.card_name || card.typeLabel,
    subtitle: card.typeLabel,
    lines,
  }
}

function enrichPackage(item) {
  const hint = PKG_HINTS[item.bill_type] || {}
  const validDays = item.valid_days
  const sessionCount = item.session_count
  let tag = hint.tag

  if (item.bill_type === 'session') {
    const count = sessionCount || 10
    tag = `含 ${count} 次`
  } else if (validDays && item.bill_type === 'daily' && validDays > 1) {
    tag = `${validDays}天内有效`
  } else if (validDays && ['weekly', 'monthly', 'quarterly'].includes(item.bill_type)) {
    tag = `${validDays}天内有效`
  } else if (validDays && item.bill_type === 'night_monthly') {
    tag = `${validDays}天有效`
  }

  const priceText = Number(item.price).toFixed(item.price % 1 === 0 ? 0 : 2)
  const ruleText = item.remark || hint.rule || '购买后发放至「我的期限卡」'

  return {
    ...item,
    tagText: tag || '',
    ruleText,
    priceText,
  }
}

function buildPackageDetail(pkg) {
  const lines = []
  if (pkg.tagText) lines.push(pkg.tagText)
  if (pkg.valid_days && pkg.bill_type !== 'session') {
    lines.push(`有效天数：${pkg.valid_days} 天`)
  }
  if (pkg.remark) lines.push(pkg.remark)
  lines.push(...(CARD_DETAIL_LINES[pkg.bill_type] || []))
  lines.push('购买后发放至「我的期限卡」，预约时选择期限卡支付')

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
  isCardUsable,
  isOfficeNightMonthlyCard,
  nightWindowForDate,
  normalizeNightBookingTimes,
  validateNightBookingTimes,
  hourlyAllowsPartialUse,
  dailyPassDays,
  enrichPackage,
  filterPackages,
  buildCardDetail,
  buildPackageDetail,
}
