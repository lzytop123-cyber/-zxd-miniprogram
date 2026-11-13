const path = require('path')
const fs = require('fs')
const { chromium } = require('C:/Users/Administrator/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright')

async function main() {
  const browser = await chromium.launch({ headless: true })
  const page = await browser.newPage({ viewport: { width: 1282, height: 1700 }, deviceScaleFactor: 1 })
  await page.goto('file:///' + path.join(__dirname, 'home-variants.html').replace(/\\/g, '/'))
  await page.evaluate(async () => {
    await document.fonts.ready
    await Promise.all([...document.images].map(img => img.complete ? Promise.resolve() : new Promise(resolve => {img.onload=resolve;img.onerror=resolve})))
  })
  for (let i = 1; i <= 3; i++) {
    const file = path.join(__dirname, `home-${String(i).padStart(2,'0')}-${['overview','structure','entry-points'][i-1]}-1242x1660.png`)
    await page.locator(`#home${i}`).screenshot({ path: file })
    console.log(file)
  }
  await page.evaluate(() => {
    const cover = document.querySelector('#home1')
    cover.querySelector('.smallnum').textContent = '01 / 05'
    cover.querySelector('.eyebrow').textContent = '给自习室老板的经营系统'
    cover.querySelector('.title').innerHTML = '自习室小程序<br><em>预约、选座</em><br>经营一套搞定'
    cover.querySelector('.desc').textContent = '学员自己预约选座，店长在后台管理门店、订单和座位。'
    cover.querySelector('.barrow').innerHTML = '<span>在线预约</span><span>座位平面图</span><span>蓝牙开门</span><span>管理后台</span>'
    cover.querySelector('.callout b').textContent = '学员端 + 店长端，一套系统'
    cover.querySelector('.callout small').textContent = '滑动看实际功能与页面结构'
    cover.querySelector('.footer span:last-child').textContent = '软件功能展示 →'
  })
  const shopCover = path.join(__dirname, 'shop-01-product-cover-1242x1660.png')
  await page.locator('#home1').screenshot({ path: shopCover })
  fs.copyFileSync(shopCover, path.join(__dirname, '01-cover-1242x1660.png'))
  console.log(shopCover)
  await browser.close()
}
main().catch(err => { console.error(err); process.exit(1) })
