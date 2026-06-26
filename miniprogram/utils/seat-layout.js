/** 选座布局 — 按知行岛平面图 1–27 号分区排列 */

const MAP_WIDTH = 1024
const MAP_HEIGHT = 990

const CODE_TO_SLOT = {
  A01: 3, A02: 4, A03: 5, A04: 6, A05: 7, A06: 8, A07: 9, A08: 10,
  B01: 14, B02: 15, B03: 16, B04: 17, B05: 18, B06: 19, B07: 20, B08: 21,
  C01: 1, C02: 2, C03: 11, C04: 12, C05: 13, C06: 25, C07: 26, C08: 27,
}

/**
 * 平面图分区（与原图一致）
 * - 左上沉浸：左墙 21–24，右墙 19–20
 * - 中上沉浸：左墙 16–18，右墙 14–15
 * - 左下沉浸：左墙 25–27 竖排，右侧休息区
 * - 标准区：内列 9–13，靠右列 8–3，入口旁 1–2
 */
const ZONE_LAYOUT = {
  immLeft: [[21, 22, 23, 24], [19, 20]],
  immMid: [[16, 17, 18], [14, 15]],
  immLow: [25, 26, 27],
  standard: [[9, 10, 11, 12, 13], [8, 7, 6, 5, 4, 3], [1, 2]],
}

function slotFromCode(seatCode) {
  if (!seatCode) return null
  const code = String(seatCode).toUpperCase()
  if (CODE_TO_SLOT[code]) return CODE_TO_SLOT[code]
  const num = parseInt(code.replace(/\D/g, ''), 10)
  return Number.isFinite(num) && num >= 1 && num <= 27 ? num : null
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

function pickColumns(columns, bySlot) {
  return columns.map((col) =>
    col.map((slot) => bySlot[slot]).filter(Boolean)
  )
}

function pickList(slots, bySlot) {
  return slots.map((slot) => bySlot[slot]).filter(Boolean)
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
    standard: pickColumns(ZONE_LAYOUT.standard, bySlot),
  }
}

function getLayout() {
  return {
    mapWidth: MAP_WIDTH,
    mapHeight: MAP_HEIGHT,
    applySeats(seats) {
      return (seats || []).map(enrichSeat)
    },
    groupSeatsForZones,
  }
}

module.exports = { getLayout, groupSeatsForZones, MAP_WIDTH, MAP_HEIGHT }
