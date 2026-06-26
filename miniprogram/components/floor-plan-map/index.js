const { buildSeatMarkers } = require('../../utils/seat-layout')

Component({
  properties: {
    seats: { type: Array, value: [] },
    selectedId: { type: Number, value: null },
  },
  data: {
    markers: [],
  },
  observers: {
    seats(seats) {
      this.setData({ markers: buildSeatMarkers(seats) })
    },
  },
  methods: {
    onTap(e) {
      const { id, code, status } = e.currentTarget.dataset
      if (!id || status === 'empty') return
      this.triggerEvent('select', { id, code, status })
    },
  },
})
