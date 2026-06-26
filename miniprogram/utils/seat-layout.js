/** 选座布局 — 知行岛平面图（1–27 号，按建筑平面图分区） */

const MAP_WIDTH = 1024
const MAP_HEIGHT = 990
const PLAN_SEAT_COUNT = 27

const CODE_TO_SLOT = {
  A01: 3, A02: 4, A03: 5, A04: 6, A05: 7, A06: 8, A07: 9, A08: 10,
  B01: 14, B02: 15, B03: 16, B04: 17, B05: 18, B06: 19, B07: 20, B08: 21,
  C01: 1, C02: 2, C03: 11, C04: 12, C05: 13, C06: 25, C07: 26, C08: 27,
}

/**
 * 第二张建筑平面图
 * - 左上沉浸：左墙 21–24，右墙 19–20
 * - 中上沉浸：左墙 16–18，右墙 14–15
 * - 左下沉浸：左墙 25–27，右侧休息区（虚线）
 * - 标准区：内列上 9–11、下 12–13，靠右列 8–3，入口旁 1–2
 */
const ZONE_LAYOUT = {
  immLeft: [[21, 22, 23, 24], [19, 20]],
  immMid: [[16, 17, 18], [14, 15]],
  immLow: [25, 26, 27],
  standardUpper: [9, 10, 11],
  standardLower: [12, 13],
  standardRight: [8, 7, 6, 5, 4, 3],
  standardEntry: [1, 2],
}

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

function resolveSlot(slot, bySlot) {
  return bySlot[slot] || placeholderSeat(slot)
}

function pickColumns(columns, bySlot) {
  return columns.map((col) => col.map((slot) => resolveSlot(slot, bySlot)))
}

function pickList(slots, bySlot) {
  return slots.map((slot) => resolveSlot(slot, bySlot))
}

function groupSeatsForZones(seats) {
  const bySlot = {}
  ;(seats || []).forEach((s) => {
    const item = enrichSeat(s)
    if (item.map_slot) bySlot[item.map_slot] = item
  })

  return {
    immLeft: pickColumns(ZONE_LAYOUT.immLeft, bySlot),
    immMid: pickColumns(ZONE_LAYOUT.immMid, bySlot),
    immLow: pickList(ZONE_LAYOUT.immLow, bySlot),
    standardUpper: pickList(ZONE_LAYOUT.standardUpper, bySlot),
    standardLower: pickList(ZONE_LAYOUT.standardLower, bySlot),
    standardRight: pickList(ZONE_LAYOUT.standardRight, bySlot),
    standardEntry: pickList(ZONE_LAYOUT.standardEntry, bySlot),
  }
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
    groupSeatsForZones,
    zoneNameBySlot,
  }
}

module.exports = {
  getLayout,
  groupSeatsForZones,
  zoneNameBySlot,
  MAP_WIDTH,
  MAP_HEIGHT,
  PLAN_SEAT_COUNT,
}
