const fs = require('fs')
const path = require('path')
const { chromium } = require('C:/Users/Administrator/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright')

async function main() {
  const outDir = path.join(__dirname, 'video-frames')
  fs.mkdirSync(outDir, { recursive: true })
  const browser = await chromium.launch({ headless: true })
  const page = await browser.newPage({ viewport: { width: 1120, height: 1960 }, deviceScaleFactor: 1 })
  await page.goto('file:///' + path.join(__dirname, 'video-scenes.html').replace(/\\/g, '/'))
  await page.evaluate(async () => {
    await document.fonts.ready
    await Promise.all([...document.images].map(img => img.complete ? Promise.resolve() : new Promise(resolve => { img.onload = resolve; img.onerror = resolve })))
  })
  for (let i = 0; i < 7; i++) {
    const file = path.join(outDir, `scene-${String(i).padStart(2, '0')}.png`)
    await page.locator(`#v${i}`).screenshot({ path: file })
    if (i === 0) fs.copyFileSync(file, path.join(__dirname, 'video-cover-1080x1920.png'))
    console.log(file)
  }
  await browser.close()
}

main().catch(err => { console.error(err); process.exit(1) })
