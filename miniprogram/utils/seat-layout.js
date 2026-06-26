/**
 * 知行岛座位平面图 — 坐标按原图 1024×990 换算
 * plan-main = 1024×772（主区），底栏 218
 * 所有座位 left/top 为 plan-main 内的百分比
 */

const MAP_WIDTH = 1024
const MAP_HEIGHT = 990
const MAIN_HEIGHT = 772
const PLAN_SEAT_COUNT = 27

const CODE_TO_SLOT = {
  A01: 3, A02: 4, A03: 5, A04: 6, A05: 7, A06: 8, A07: 9, A08: 10,
  B01: 14, B02: 15, B03: 16, B04: 17, B05: 18, B06: 19, B07: 20, B08: 21,
  C01: 1, C02: 2, C03: 11, C04: 12, C05: 13, C06: 25, C07: 26, C08: 27,
}

/** 像素 → plan-main 百分比 */
function pct(x, y) {
  return {
    left: +((x / MAP_WIDTH) * 100).toFixed(2),
    top: +((y / MAIN_HEIGHT) * 100).toFixed(2),
  }
}

/**
 * 原图座位中心像素（1024×772 主区）
 * 左墙自上而下编号，与建筑平面图一致
 */
const MAIN_POS = {
  /* 左上沉浸：左墙 24→21，右墙 19-20 */
  24: pct(35, 58),
  23: pct(35, 168),
  22: pct(35, 278),
  21: pct(35, 388),
  19: pct(318, 128),
  20: pct(318, 308),

  /* 中上沉浸：左墙 18→16，右墙 14-15 */
  18: pct(398, 68),
  17: pct(398, 238),
  16: pct(398, 408),
  14: pct(562, 118),
  15: pct(562, 318),

  /* 左下沉浸：25-27 */
  25: pct(35, 578),
  26: pct(35, 648),
  27: pct(35, 718),

  /* 标准区：内列 9-11 / 12-13，右墙 8→3，入口 1-2 */
  9: pct(682, 58),
  10: pct(682, 133),
  11: pct(682, 208),
  12: pct(682, 368),
  13: pct(682, 443),
  8: pct(962, 48),
  7: pct(962, 118),
  6: pct(962, 188),
  5: pct(962, 258),
  4: pct(962, 328),
  3: pct(962, 398),
  1: pct(652, 688),
  2: pct(742, 688),
}

const ALL_SLOTS = Object.keys(MAIN_POS).map(Number)

function slotFromCode(seatCode) {
  if (!seatCode) return null
  const code = String(seatCode).toUpperCase()
  if (CODE_TO_SLOT[code]) return CODE_TO_SLOT[code]
  const num = parseInt(code.replace(/\D/g, ''), 10)
  return Number.isFinite(num) && num >= 1 && num <= PLAN_SEAT_COUNT ? num : null
}

function displayLabel(seatCode, slot) {
  if (slot != null) return String(slot)
  const m = String(seatCode).match(/(\d+)$/)
  return m ? String(parseInt(m[1], 10)) : seatCode
}

function enrichSeat(seat) {
  const slot = slotFromCode(seat.seat_code)
  return {
    ...seat,
    map_slot: slot,
    map_label: displayLabel(seat.seat_code, slot),
  }
}

function placeholderSeat(slot) {
  return {
    id: null,
    seat_code: null,
    map_slot: slot,
    map_label: String(slot),
    status: 'empty',
  }
}

function buildSeatMarkers(seats) {
  const bySlot = {}
  ;(seats || []).forEach((s) => {
    const item = enrichSeat(s)
    if (item.map_slot) bySlot[item.map_slot] = item
  })

  return ALL_SLOTS.map((slot) => {
    const seat = bySlot[slot] || placeholderSeat(slot)
    const pos = MAIN_POS[slot]
    return { ...seat, ...pos }
  })
}

function zoneNameBySlot(slot) {
  if (!slot) return ''
  if (slot >= 14) return '沉浸区'
  if (slot >= 1 && slot <= 13) return '标准区'
  return ''
}

function getLayout() {
  return {
    mapWidth: MAP_WIDTH,
    mapHeight: MAP_HEIGHT,
    planSeatCount: PLAN_SEAT_COUNT,
    applySeats(seats) {
      return (seats || []).map(enrichSeat)
    },
    buildSeatMarkers,
    zoneNameBySlot,
  }
}

module.exports = {
  getLayout,
  buildSeatMarkers,
  zoneNameBySlot,
  MAP_WIDTH,
  MAP_HEIGHT,
  PLAN_SEAT_COUNT,
}
