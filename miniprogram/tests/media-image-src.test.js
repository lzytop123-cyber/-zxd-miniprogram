const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const test = require('node:test')
const vm = require('node:vm')

function loadMedia({ isDevtools = true, useProd = false } = {}) {
  const requests = []
  const wx = {
    env: { USER_DATA_PATH: 'C:\\Users\\Administrator\\AppData\\usr' },
    downloadFile() { throw new Error('should not downloadFile') },
    request(opts) {
      requests.push(opts.url)
      throw new Error('should not wx.request')
    },
    getStorageSync: () => ({}),
    setStorageSync() {},
    getFileSystemManager() {
      return {
        accessSync() { throw new Error('no cache') },
        copyFile() {},
        writeFile() {},
      }
    },
  }
  const filename = path.join(__dirname, '../utils/media.js')
  const sandbox = {
    module: { exports: {} },
    exports: {},
    require(id) {
      if (id === '../config') {
        return {
          resolveStaticUrl: (url) => url,
          useProdApi: () => useProd,
          DEV_LAN_HOST: '192.168.0.104',
          DEV_LOCAL_HOST: '127.0.0.1',
          isWechatDevtools: () => isDevtools,
        }
      }
      throw new Error(`unexpected require ${id}`)
    },
    wx,
    Promise,
    console,
    setTimeout,
  }
  sandbox.module.exports = sandbox.exports
  vm.runInNewContext(fs.readFileSync(filename, 'utf8'), sandbox, { filename })
  return { media: sandbox.module.exports, requests }
}

test('devtools uses the remote cover URL instead of a Windows cache path', async () => {
  const { media, requests } = loadMedia({ isDevtools: true, useProd: false })
  const url = 'http://127.0.0.1:8002/static/stores/cover.jpg'
  const src = await media.resolveImageForDisplay(url)
  assert.equal(src, url)
  assert.deepEqual(requests, [])
})
