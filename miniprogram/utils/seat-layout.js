/**
 * 知行岛座位平面图 — 座位中心坐标来自原图 floor-plan-default.png（1024×990）
 * 通过连通域检测逐个量出每个编号框的几何中心，误差 ≤2px
 * left/top 为相对整张平面图的百分比，叠加层 1:1 铺满原图即可精确对齐
 */

const MAP_WIDTH = 1024
const MAP_HEIGHT = 990
const PLAN_SEAT_COUNT = 27

const CODE_TO_SLOT = {
  A01: 3, A02: 4, A03: 5, A04: 6, A05: 7, A06: 8, A07: 9, A08: 10,
  B01: 14, B02: 15, B03: 16, B04: 17, B05: 18, B06: 19, B07: 20, B08: 21,
  C01: 1, C02: 2, C03: 11, C04: 12, C05: 13, C06: 25, C07: 26, C08: 27,
}

/** 像素 → 整张平面图百分比 */
function pct(x, y) {
  return {
    left: +((x / MAP_WIDTH) * 100).toFixed(3),
    top: +((y / MAP_HEIGHT) * 100).toFixed(3),
  }
}

/**
 * 原图座位编号框中心像素（1024×990 整图）
 */
const MAIN_POS = {
  /* 左上沉浸区：左墙 21→24，靠中墙 20/19 */
  21: pct(149, 296),
  22: pct(149, 358),
  23: pct(149, 416),
  24: pct(149, 475),
  20: pct(319, 295),
  19: pct(319, 357),

  /* 中上沉浸区：左墙 16/17/18，靠右 15/14 */
  16: pct(395, 294),
  17: pct(395, 355),
  18: pct(395, 413),
  15: pct(567, 293),
  14: pct(567, 355),

  /* 左下沉浸区：27→25 */
  27: pct(148, 569),
  26: pct(148, 631),
  25: pct(148, 689),

  /* 标准区：内列 9-11 / 12-13，右墙 8→3，入口 1-2 */
  9: pct(644, 290),
  10: pct(644, 352),
  11: pct(644, 410),
  12: pct(639, 595),
  13: pct(639, 656),
  8: pct(866, 292),
  7: pct(866, 353),
  6: pct(866, 411),
  5: pct(867, 471),
  4: pct(867, 533),
  3: pct(867, 591),
  1: pct(801, 735),
  2: pct(863, 735),
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
