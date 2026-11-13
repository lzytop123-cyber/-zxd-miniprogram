function pickExchangeStore(stores, preferredId) {
  const list = Array.isArray(stores) ? stores : []
  if (!list.length) {
    return { storeId: null, storeName: '', storeIndex: 0 }
  }
  const preferred = preferredId != null && preferredId !== '' ? Number(preferredId) : null
  let index = 0
  if (preferred != null && Number.isFinite(preferred)) {
    const found = list.findIndex((s) => Number(s.id) === preferred)
    if (found >= 0) index = found
  }
  const store = list[index]
  return {
    storeId: store.id,
    storeName: store.name || '',
    storeIndex: index,
  }
}

function buildExchangeUrl({ platform, storeId } = {}) {
  const parts = []
  if (platform) parts.push(`platform=${encodeURIComponent(platform)}`)
  if (storeId != null && storeId !== '') parts.push(`storeId=${encodeURIComponent(storeId)}`)
  const qs = parts.length ? `?${parts.join('&')}` : ''
  return `/pages/exchange/index${qs}`
}

module.exports = {
  pickExchangeStore,
  buildExchangeUrl,
}
