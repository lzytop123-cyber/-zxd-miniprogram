const assert = require('node:assert/strict')
const fs = require('node:fs')
const vm = require('node:vm')
const { mapBleOpenFailure } = require('../utils/bleUnlock')
async function main() {
  assert.match(mapBleOpenFailure({errorMsg:'bluetooth permission denied', canOpen:true}).content, /权限/)
  assert.match(mapBleOpenFailure({errorMsg:'bluetooth connection timeout', errorCode:10012, canOpen:true}).content, /超时/)
  const pending = []; let page
  vm.runInNewContext(fs.readFileSync('miniprogram/pages/checkin/index.js','utf8'), {
    require: name => name.endsWith('/request') ? {request: () => new Promise(resolve => pending.push(resolve))} : {},
    Page: p => {page=p}, wx: {setStorageSync(){}}, console
  })
  page.data = {reservation:{id:1}, lockData:'old'}
  page.setData = patch => Object.assign(page.data,patch)
  const a = page.loadBleKey(1)
  assert.equal(page.data.lockData,'')
  page.data.reservation={id:2}
  const b = page.loadBleKey(2)
  pending[1]({lockData:'B'}); await b
  pending[0]({lockData:'A'}); await a
  assert.equal(page.data.lockData,'B')
  console.log('BLE permission, timeout and key race regressions passed')
}
main().catch(e=>{console.error(e);process.exitCode=1})
