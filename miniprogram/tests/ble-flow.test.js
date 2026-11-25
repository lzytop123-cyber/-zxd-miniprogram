const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const vm = require('node:vm')
function setup({ adapterFailure, result } = {}) {
  let page; let keyResolve; let unlockResolve; let calls=0; let stops=0
  const timers = new Map(); const reports=[]
  const plugin = { controlLock: () => { calls++; return result ? Promise.resolve(result) : new Promise(r=>{unlockResolve=r}) }, stopAllOperations: async()=>{stops++;return {errorCode:0}} }
  vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../pages/checkin/index.js'),'utf8'), {
    require(name) {
      if(name.endsWith('/request')) return {request: opts=>{
        if(opts.url.startsWith('/ble/key/')) return new Promise(r=>{keyResolve=r})
        reports.push(opts);return Promise.resolve()
      }}
      if(name.endsWith('/bleUnlock')) return {computeCanOpen:()=>true,mapBleOpenFailure:()=>({content:'failure'})}
      return {}
    }, Page:p=>{page=p}, requirePlugin:()=>plugin,
    setTimeout:(fn,ms)=>{timers.set(ms,fn);return ms},clearTimeout:ms=>timers.delete(ms),
    wx:{showLoading(){},hideLoading(){},showToast(){},vibrateShort(){},getSystemInfoSync:()=>({system:'test'}),
      openBluetoothAdapter:opts=>adapterFailure?opts.fail({errMsg:'permission denied',errCode:10001}):opts.success({})},console
  })
  page.data={...page.data,reservation:{id:1},canOpen:true}
  page.setData=patch=>Object.assign(page.data,patch)
  page.loadActive=()=>Promise.resolve()
  return {page,timers,reports,key:()=>keyResolve({lockData:'fresh'}),unlock:()=>unlockResolve({errorCode:0}),calls:()=>calls,stops:()=>stops}
}
const flush=async()=>{for(let i=0;i<12;i++)await Promise.resolve()}
async function run(){
  let h=setup();const op=h.page.openDoorBle();assert.equal(h.calls(),0)
  await h.page.openDoorBle();h.key();await flush();assert.equal(h.calls(),1)
  h.timers.get(35000)();assert.equal(h.page.data.opening,false);assert.equal(h.page.data.bleLocked,true)
  await h.page.openDoorBle();assert.equal(h.calls(),1)
  h.unlock();await op;assert.equal(h.page.data.opening,false)
  assert.equal(h.reports.filter(r=>r.data.result==='success').length,1)
  h=setup({adapterFailure:true});const denied=h.page.openDoorBle();h.key();await denied
  assert.equal(h.calls(),0);assert.equal(h.reports[0].data.stage,'adapter')
  assert.equal(h.reports[0].data.error_msg,'permission denied')
  h=setup({result:{errorCode:10012,errorMsg:'timeout'}});const failed=h.page.openDoorBle();h.key();await failed
  assert.equal(h.stops(),1);assert.equal(h.page.data.opening,false)
  console.log('BLE flow: key wait, duplicate taps, timeout guard, late success, adapter errors, cleanup passed')
}
run().catch(e=>{console.error(e);process.exitCode=1})
