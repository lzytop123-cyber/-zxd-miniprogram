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

/**
 * 坐标基于 900 × 700 的逻辑画布，换算为百分比：
 *   left% = x / 900 * 100 ，top% = y / 700 * 100
 * orient: 'v' 竖向座位（桌条在上下），'h' 横向座位（桌条在左右）
 */
function pos(left, top, orient) {
  return {
    left: +left.toFixed(3),
    top: +top.toFixed(3),
    orient: orient || 'v',
  }
}

const MAIN_POS = {
  // 左上沉浸区：21-24 靠左墙竖排，19-20 右侧竖排
  21: pos(11.111, 14.286),
  22: pos(11.111, 23.429),
  23: pos(11.111, 32.571),
  24: pos(11.111, 41.714),
  20: pos(24.667, 14.286),
  19: pos(24.667, 23.429),

  // 中上沉浸区：16-18 竖排，14-15 右侧竖排
  16: pos(38.444, 14.286),
  17: pos(38.444, 23.429),
  18: pos(38.444, 32.571),
  15: pos(52.0, 14.286),
  14: pos(52.0, 23.429),

  // 右侧标准区：9-11 左列，3-8 最右列（下到上 3→8）
  9: pos(66.222, 14.286),
  10: pos(66.222, 23.429),
  11: pos(66.222, 32.571),
  8: pos(89.333, 14.286),
  7: pos(89.333, 23.429),
  6: pos(89.333, 32.571),
  5: pos(89.333, 41.714),
  4: pos(89.333, 50.857),
  3: pos(89.333, 60.0),

  // 中下：12、13 竖排，靠卫生间右侧
  12: pos(68.667, 64.571),
  13: pos(68.667, 73.714),

  // 左下沉浸区：27-25 靠左墙竖排
  27: pos(11.111, 65.0),
  26: pos(11.111, 74.143),
  25: pos(11.111, 83.286),

  // 右下角入口处：1、2 横排
  1: pos(80.222, 86.857, 'h'),
  2: pos(88.0, 86.857, 'h'),
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
