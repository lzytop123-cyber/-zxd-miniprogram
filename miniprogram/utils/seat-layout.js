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
  21: pos(10.26, 15.48),
  22: pos(10.26, 23.97),
  23: pos(10.26, 32.46),
  24: pos(10.26, 40.95),
  20: pos(28.68, 15.48),
  19: pos(28.68, 23.97),

  // 中上沉浸区：16-18 竖排，14-15 右侧竖排
  16: pos(37.45, 15.48),
  17: pos(37.45, 23.97),
  18: pos(37.45, 32.46),
  15: pos(55.75, 15.48),
  14: pos(55.75, 23.97),

  // 右侧标准区：9-11 左列，3-8 最右列（下到上 3→8）
  9: pos(64.85, 15.48),
  10: pos(64.85, 23.97),
  11: pos(64.85, 32.46),
  8: pos(90.06, 15.48),
  7: pos(90.06, 23.97),
  6: pos(90.06, 32.46),
  5: pos(90.06, 40.95),
  4: pos(90.06, 49.44),
  3: pos(90.06, 57.93),

  // 中下：12、13 竖排，与 9-11 同列、靠卫生间右侧
  12: pos(64.85, 58.35),
  13: pos(64.85, 66.84),

  // 左下沉浸区：27-25 靠左墙竖排（在房间内垂直均匀展开、上下留白对称）
  27: pos(10.26, 61.5),
  26: pos(10.26, 73.5),
  25: pos(10.26, 85.5),

  // 右下角入口处：1、2 横排
  1: pos(81.51, 77.45, 'h'),
  2: pos(89.73, 77.45, 'h'),
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
