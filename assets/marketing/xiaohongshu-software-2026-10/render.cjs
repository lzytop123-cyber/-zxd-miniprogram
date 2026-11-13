const path = require('path')
const { chromium } = require('C:/Users/Administrator/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright')
require('./floor-plan-art.cjs')

async function main() {
  const browser = await chromium.launch({ headless: true })
  const page = await browser.newPage({ viewport: { width: 1298, height: 1716 }, deviceScaleFactor: 1 })
  await page.goto('file:///' + path.join(__dirname, 'posters.html').replace(/\\/g, '/'))
  await page.evaluate(() => document.fonts.ready)
  // The refreshed homepage cover is exported by render-home.cjs.
  for (let i = 2; i <= 5; i++) {
    const file = path.join(__dirname, `${String(i).padStart(2, '0')}-${['cover','booking','seat-map','checkin','admin'][i - 1]}-1242x1660.png`)
    await page.locator(`#p${i}`).screenshot({ path: file })
    console.log(file)
  }
  await browser.close()
}
main().catch(err => { console.error(err); process.exit(1) })
