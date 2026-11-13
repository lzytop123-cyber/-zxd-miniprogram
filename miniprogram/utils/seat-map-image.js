/**
 * 图片座位图：用服务端标记 + 空位状态拼成 floor-plan-map 可用的 markers。
 */

function buildImageMarkers(mapMarkers, seats) {
  const byId = {}
  ;(seats || []).forEach((s) => {
    if (s && s.id != null) byId[Number(s.id)] = s
  })

  return (mapMarkers || []).map((m) => {
    const seatId = Number(m.seat_id)
    const seat = byId[seatId] || {}
    const code = m.seat_code || seat.seat_code || String(seatId)
    return {
      id: seatId,
      seat_code: code,
      map_label: code,
      map_slot: seatId,
      left: Number(m.x_pct),
      top: Number(m.y_pct),
      orient: m.orient || 'up',
      status: seat.status || 'empty',
      zone_name: m.zone_name || seat.zone_name || '',
      has_outlet: seat.has_outlet,
      has_curtain: m.has_curtain ?? seat.has_curtain,
    }
  })
}

function seatDisplayImage(seat, markers) {
  if (!seat) return { mapLabel: '', zoneName: '', seatCode: '' }
  const id = Number(seat.id)
  const marker = (markers || []).find((m) => Number(m.seat_id || m.id) === id)
  return {
    mapLabel: seat.map_label || seat.seat_code || '',
    zoneName: (marker && marker.zone_name) || seat.zone_name || '',
    seatCode: seat.seat_code || '',
  }
}

module.exports = {
  buildImageMarkers,
  seatDisplayImage,
}
