const assert = require('node:assert/strict')
const { chooseContactStore } = require('../utils/contact-store')
const stores = [{ id: 1, distance: 5 }, { id: 2, distance: 1 }]
assert.equal(chooseContactStore(stores, 1, true).id, 1)
assert.equal(chooseContactStore(stores, null, true).id, 2)
assert.equal(chooseContactStore(stores, null, false), null)
assert.equal(chooseContactStore([{ id: 1, distance: null }], null, true), null)
assert.equal(chooseContactStore(stores, 99, true), null)
console.log('Contact selection checks passed')
