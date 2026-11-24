const { describe, it } = require('node:test')
const assert = require('node:assert/strict')
const { pickExchangeStore, buildExchangeUrl } = require('../pages/exchange/utils/storePick')

describe('exchange storePick', () => {
  const stores = [
    { id: 1, name: '千峰南路店' },
    { id: 2, name: '理工大店' },
  ]

  it('prefers matching storeId', () => {
    assert.deepEqual(pickExchangeStore(stores, 2), {
      storeId: 2,
      storeName: '理工大店',
      storeIndex: 1,
      storePicked: true,
    })
  })

  it('does not default when preferred missing or unknown', () => {
    assert.deepEqual(pickExchangeStore(stores, null), {
      storeId: null,
      storeName: '',
      storeIndex: 0,
      storePicked: false,
    })
    assert.deepEqual(pickExchangeStore(stores, 99), {
      storeId: null,
      storeName: '',
      storeIndex: 0,
      storePicked: false,
    })
  })

  it('handles empty list', () => {
    assert.deepEqual(pickExchangeStore([], 1), {
      storeId: null,
      storeName: '',
      storeIndex: 0,
      storePicked: false,
    })
  })

  it('builds exchange url with storeId', () => {
    assert.equal(buildExchangeUrl({ storeId: 2 }), '/pages/exchange/index?storeId=2')
    assert.equal(
      buildExchangeUrl({ platform: 'douyin', storeId: 1 }),
      '/pages/exchange/index?platform=douyin&storeId=1'
    )
  })
})
