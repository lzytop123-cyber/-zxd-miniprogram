const { groupSeatsForZones } = require('../../utils/seat-layout')

Component({
  properties: {
    seats: { type: Array, value: [] },
    selectedId: { type: Number, value: null },
  },
  data: {
    zones: {
      immLeft: [[], []],
      immMid: [[], []],
      immLow: [],
      standard: [[], [], []],
    },
  },
  observers: {
    seats(seats) {
      this.setData({ zones: groupSeatsForZones(seats) })
    },
  },
  methods: {
    onTap(e) {
      const { id, code, status } = e.currentTarget.dataset
      this.triggerEvent('select', { id, code, status })
    },
  },
})
