Component({
  properties: {
    store: { type: Object, value: {} },
    showLocationHint: { type: Boolean, value: false },
  },
  data: {
    coverFailed: false,
    canNavigate: false,
  },
  observers: {
    store(store) {
      const { hasStoreCoords } = require('../../utils/location')
      this.setData({
        coverFailed: false,
        canNavigate: hasStoreCoords(store),
      })
    },
  },
  methods: {
    onTap() {
      this.triggerEvent('select', { id: this.properties.store.id })
    },
    onCoverError() {
      this.setData({ coverFailed: true })
    },
    onNavigate() {
      const { openStoreNavigation } = require('../../utils/location')
      openStoreNavigation(this.properties.store).catch(() => {})
    },
  },
})
