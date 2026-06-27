/**
 * 知行岛座位平面图 — 座位中心坐标来自原图（1024×990）连通域检测，误差 ≤2px
 * 底图已裁掉标题与四周留白（floor-plan-clean.png），仅保留平面图主体
 * 裁切区域 = 原图 (91,221)–(934,868)，尺寸 843×647
 * MAIN_POS 仍用原图像素坐标，经 pct() 换算到裁切图，叠加层 1:1 铺满即对齐
 */

// 裁切区域（相对原图）
const CROP_LEFT = 91
const CROP_TOP = 221
const MAP_WIDTH = 843
const MAP_HEIGHT = 647
const PLAN_SEAT_COUNT = 27

const CODE_TO_SLOT = {
  A01: 3, A02: 4, A03: 5, A04: 6, A05: 7, A06: 8, A07: 9, A08: 10,
  B01: 14, B02: 15, B03: 16, B04: 17, B05: 18, B06: 19, B07: 20, B08: 21,
  C01: 1, C02: 2, C03: 11, C04: 12, C05: 13, C06: 25, C07: 26, C08: 27,
  D01: 22, D02: 23, D03: 24,
}

/** 原图像素 → 裁切图百分比 */
function pct(x, y) {
  return {
    left: +(((x - CROP_LEFT) / MAP_WIDTH) * 100).toFixed(3),
    top: +(((y - CROP_TOP) / MAP_HEIGHT) * 100).toFixed(3),
  }
}

/**
 * 座位编号框中心像素（原图 1024×990 坐标系）
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

/** 与平面图分区一致：1–13 标准区，14–27 三个沉浸区块均为沉浸区 */
const SLOT_ZONE = {
  1: '标准区', 2: '标准区', 3: '标准区', 4: '标准区', 5: '标准区',
  6: '标准区', 7: '标准区', 8: '标准区', 9: '标准区', 10: '标准区',
  11: '标准区', 12: '标准区', 13: '标准区',
  14: '沉浸区', 15: '沉浸区', 16: '沉浸区', 17: '沉浸区', 18: '沉浸区',
  19: '沉浸区', 20: '沉浸区', 21: '沉浸区', 22: '沉浸区', 23: '沉浸区', 24: '沉浸区',
  25: '沉浸区', 26: '沉浸区', 27: '沉浸区',
}

function slotFromCode(seatCode) {
  if (!seatCode) return null
  const code = String(seatCode).toUpperCase()
  if (Object.prototype.hasOwnProperty.call(CODE_TO_SLOT, code)) {
    return CODE_TO_SLOT[code]
  }
  return null
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
  return SLOT_ZONE[slot] || ''
}

function seatDisplay(seat) {
  if (!seat) return { mapLabel: '', zoneName: '', seatCode: '' }
  const enriched = seat.map_slot != null ? seat : enrichSeat(seat)
  return {
    mapLabel: enriched.map_label || '',
    zoneName: zoneNameBySlot(enriched.map_slot),
    seatCode: enriched.seat_code || '',
  }
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
    seatDisplay,
  }
}

module.exports = {
  getLayout,
  buildSeatMarkers,
  zoneNameBySlot,
  seatDisplay,
  enrichSeat,
  MAP_WIDTH,
  MAP_HEIGHT,
  PLAN_SEAT_COUNT,
}
