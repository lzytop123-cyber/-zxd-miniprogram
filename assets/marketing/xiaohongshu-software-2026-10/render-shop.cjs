const path = require('path')
const { chromium } = require('C:/Users/Administrator/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright')

const images = [
  '01-cover-1242x1660.png',
  '02-booking-1242x1660.png',
  '03-seat-map-1242x1660.png',
  '04-checkin-1242x1660.png',
  '05-admin-1242x1660.png',
]

async function main() {
  const browser = await chromium.launch({ headless: true })
  const page = await browser.newPage({ viewport: { width: 750, height: 1000 }, deviceScaleFactor: 1 })
  await page.goto('file:///' + path.join(__dirname, 'posters.html').replace(/\\/g, '/'))
  await page.evaluate(() => {
    document.head.innerHTML = '<style>html,body{margin:0;width:750px;height:1000px;overflow:hidden;background:white}img{display:block;width:750px;height:1000px}</style>'
    document.body.innerHTML = '<img id="export" alt="">'
  })
  for (let i = 0; i < images.length; i++) {
    await page.evaluate(src => new Promise(resolve => {
      const img = document.querySelector('#export')
      img.onload = resolve
      img.onerror = resolve
      img.src = src
    }), images[i])
    const file = path.join(__dirname, `shop-${String(i + 1).padStart(2, '0')}-750x1000.png`)
    await page.screenshot({ path: file })
    console.log(file)
  }
  await browser.close()
}

main().catch(error => { console.error(error); process.exit(1) })
