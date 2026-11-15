function chooseContactStore(stores, preferredId, located) {
  if (preferredId) return stores.find(s => String(s.id) === String(preferredId)) || null
  if (!located) return null
  return stores.filter(s => s.distance != null && Number.isFinite(Number(s.distance)))
    .sort((a, b) => Number(a.distance) - Number(b.distance))[0] || null
}
module.exports = { chooseContactStore }
