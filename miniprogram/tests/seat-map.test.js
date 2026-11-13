const { describe, it } = require('node:test')
const assert = require('node:assert/strict')
const { readFileSync } = require('node:fs')
const { runInNewContext } = require('node:vm')
const { buildImageMarkers, seatDisplayImage } = require('../utils/seat-map-image')

it('fits a tall image and its marker layer inside the visible map area', () => {
  let component
  const source = readFileSync(require.resolve('../components/floor-plan-map/index'), 'utf8')
  runInNewContext(source, {
    Component: (definition) => { component = definition },
    require: () => ({}),
  })
  const area = { width: 360, height: 280 }
  const context = {
    data: { mode: 'image', aspectRatio: 1 },
    createSelectorQuery: () => ({
      select: () => ({
        boundingClientRect: (callback) => ({ exec: () => callback(area) }),
      }),
    }),
    setData(update) { Object.assign(this.data, update) },
  }
  component.methods.fitImageFloor.call(context)
  assert.equal(context.data.floorStyle, 'width:280px;height:280px;left:40px;top:0px;')

  context.data.drawnFloor = true
  area.width = 400
  component.methods.fitImageFloor.call(context)
  assert.equal(context.data.floorStyle, 'width:400px;height:280px;left:0px;top:0px;')

  context.data.drawnFloor = false
  area.width = 360
  context.data.aspectRatio = 2
  component.methods.fitImageFloor.call(context)
  assert.equal(context.data.floorStyle, 'width:360px;height:180px;left:0px;top:50px;')
})

describe('seat-map-image', () => {
  it('builds markers from published map + availability', () => {
    const mapMarkers = [
      { seat_id: 10, seat_code: 'A1', x_pct: 12.5, y_pct: 33, orient: 'up', zone_name: 'A区', has_curtain: 1 },
      { seat_id: 11, seat_code: 'A2', x_pct: 40, y_pct: 50, orient: 'down', zone_name: 'A区' },
    ]
    const seats = [
      { id: 10, seat_code: 'A1', status: 'available' },
      { id: 11, seat_code: 'A2', status: 'occupied' },
    ]
    const markers = buildImageMarkers(mapMarkers, seats)
    assert.equal(markers.length, 2)
    assert.equal(markers[0].left, 12.5)
    assert.equal(markers[0].top, 33)
    assert.equal(markers[0].status, 'available')
    assert.equal(markers[1].status, 'occupied')
    assert.equal(markers[0].map_label, 'A1')
    assert.equal(markers[0].has_curtain, 1)
  })

  it('marks missing availability as empty and does not invent legacy slots', () => {
    const markers = buildImageMarkers(
      [{ seat_id: 99, seat_code: 'X1', x_pct: 1, y_pct: 2, orient: 'up' }],
      [],
    )
    assert.equal(markers.length, 1)
    assert.equal(markers[0].status, 'empty')
    assert.equal(markers[0].id, 99)
  })

  it('seatDisplayImage reads zone from markers', () => {
    const display = seatDisplayImage(
      { id: 1, seat_code: 'B2', map_label: 'B2' },
      [{ seat_id: 1, zone_name: '沉浸区' }],
    )
    assert.equal(display.mapLabel, 'B2')
    assert.equal(display.zoneName, '沉浸区')
  })
})
