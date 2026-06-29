/**
 * 预约页座位布局数据
 * 目标：优先还原参考图的结构比例与空间关系，样式细节后续再继续打磨。
 */

const PLAN_SEAT_COUNT = 27

const CODE_TO_SLOT = {
  A01: 3, A02: 4, A03: 5, A04: 6, A05: 7, A06: 8, A07: 9, A08: 10,
  B01: 14, B02: 15, B03: 16, B04: 17, B05: 18, B06: 19, B07: 20, B08: 21,
  C01: 1, C02: 2, C03: 11, C04: 12, C05: 13, C06: 25, C07: 26, C08: 27,
  A09: 22, B09: 23, C09: 24,
}

function pos(left, top) {
  return {
    left: +left.toFixed(3),
    top: +top.toFixed(3),
  }
}

const MAIN_POS = {
  // 左上沉浸区
  21: pos(6.2, 14.8),
  22: pos(6.2, 24.0),
  23: pos(6.2, 33.2),
  24: pos(6.2, 42.4),
  20: pos(20.6, 14.8),
  19: pos(20.6, 24.0),

  // 中上工位区
  16: pos(35.8, 14.8),
  17: pos(35.8, 24.0),
  18: pos(35.8, 33.2),
  15: pos(50.2, 14.8),
  14: pos(50.2, 24.0),

  // 左下沉浸区
  27: pos(6.2, 57.2),
  26: pos(6.2, 66.5),
  25: pos(6.2, 75.8),

  // 下方功能区
  12: pos(63.4, 63.2),
  13: pos(63.4, 74.4),

  // 右侧标准区
  9: pos(66.2, 14.8),
  10: pos(66.2, 24.0),
  11: pos(66.2, 33.2),
  8: pos(92.0, 14.8),
  7: pos(92.0, 24.0),
  6: pos(92.0, 33.2),
  5: pos(92.0, 43.0),
  4: pos(92.0, 52.8),
  3: pos(92.0, 62.6),

  // 入口右下
  1: pos(84.0, 82.0),
  2: pos(91.8, 82.0),
}

const ALL_SLOTS = Object.keys(MAIN_POS).map(Number)

const SLOT_ZONE = {
  1: '标准区', 2: '标准区', 3: '标准区', 4: '标准区', 5: '标准区',
  6: '标准区', 7: '标准区', 8: '标准区', 9: '标准区', 10: '标准区',
  11: '标准区', 12: '标准区', 13: '标准区',
  14: '工位区', 15: '工位区', 16: '工位区', 17: '工位区', 18: '工位区',
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
  ;(seats || []).forEach((seat) => {
    const item = enrichSeat(seat)
    if (item.map_slot) bySlot[item.map_slot] = item
  })

  return ALL_SLOTS.map((slot) => {
    const seat = bySlot[slot] || placeholderSeat(slot)
    const posItem = MAIN_POS[slot]
    return { ...seat, ...posItem }
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
    planSeatCount: PLAN_SEAT_COUNT,
    applySeats(seats) {
      return (seats || []).map(enrichSeat)
    },
    buildSeatMarkers,
    zoneNameBySlot,
    seatDisplay,
  }
}

export {
  getLayout,
  buildSeatMarkers,
  zoneNameBySlot,
  seatDisplay,
  enrichSeat,
  PLAN_SEAT_COUNT,
}

export default {
  getLayout,
  buildSeatMarkers,
  zoneNameBySlot,
  seatDisplay,
  enrichSeat,
  PLAN_SEAT_COUNT,
}
