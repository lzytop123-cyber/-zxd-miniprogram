Component({
  properties: {
    store: { type: Object, value: {} },
    showLocationHint: { type: Boolean, value: false },
  },
  data: {
    coverFailed: false,
  },
  observers: {
    store() {
      this.setData({ coverFailed: false })
    },
  },
  methods: {
    onTap() {
      this.triggerEvent('select', { id: this.properties.store.id })
    },
    onCoverError() {
      this.setData({ coverFailed: true })
    },
  },
})
