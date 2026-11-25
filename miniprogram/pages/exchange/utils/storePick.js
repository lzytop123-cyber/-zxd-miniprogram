function pickExchangeStore(stores, preferredId) {
  const list = Array.isArray(stores) ? stores : []
  if (!list.length) {
    return { storeId: null, storeName: '', storeIndex: 0, storePicked: false }
  }
  const preferred = preferredId != null && preferredId !== '' ? Number(preferredId) : null
  if (preferred == null || !Number.isFinite(preferred)) {
    // 多门店时不默认选中，避免误核销到千峰等第一家店
    return { storeId: null, storeName: '', storeIndex: 0, storePicked: false }
  }
  const found = list.findIndex((s) => Number(s.id) === preferred)
  if (found < 0) {
    return { storeId: null, storeName: '', storeIndex: 0, storePicked: false }
  }
  const store = list[found]
  return {
    storeId: store.id,
    storeName: store.name || '',
    storeIndex: found,
    storePicked: true,
  }
}

const { buildExchangeUrl } = require('../../../utils/routes')

module.exports = {
  pickExchangeStore,
  buildExchangeUrl,
}
