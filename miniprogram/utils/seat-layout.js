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
  21: pos(6.2, 15.2),
  22: pos(6.2, 24.5),
  23: pos(6.2, 33.8),
  24: pos(6.2, 43.1),
  20: pos(19.6, 15.0),
  19: pos(19.6, 24.2),

  16: pos(35.8, 15.0),
  17: pos(35.8, 24.2),
  18: pos(35.8, 33.6),
  15: pos(50.4, 15.0),
  14: pos(50.4, 24.2),

  27: pos(6.2, 57.2),
  26: pos(6.2, 66.6),
  25: pos(6.2, 76.0),

  12: pos(63.3, 63.5),
  13: pos(63.3, 74.6),

  9: pos(66.1, 15.1),
  10: pos(66.1, 24.4),
  11: pos(66.1, 33.7),
  8: pos(92.1, 15.1),
  7: pos(92.1, 24.4),
  6: pos(92.1, 33.7),
  5: pos(92.1, 43.2),
  4: pos(92.1, 52.8),
  3: pos(92.1, 62.4),

  1: pos(84.0, 82.4),
  2: pos(92.0, 82.4),
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
