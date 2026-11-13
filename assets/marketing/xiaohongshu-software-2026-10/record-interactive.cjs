const fs = require('fs')
const path = require('path')
const { spawnSync } = require('child_process')
const { chromium } = require('C:/Users/Administrator/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright')

const ffmpeg = 'F:\\ana\\envs\\xiaozhi-esp32-server\\Library\\bin\\ffmpeg.exe'
const ffprobe = 'F:\\ana\\envs\\xiaozhi-esp32-server\\Library\\bin\\ffprobe.exe'
const html = 'file:///' + path.join(__dirname, 'interactive-demo.html').replace(/\\/g, '/')
const raw = path.join(__dirname, 'interactive-demo-raw.webm')
const output = path.join(__dirname, 'zhixingdao-xiaohongshu-animated-demo-1080x1920.mp4')

async function main() {
  const browser = await chromium.launch({ headless: true })

  const preview = await browser.newPage({ viewport: { width: 1080, height: 1920 }, deviceScaleFactor: 1 })
  await preview.goto(html)
  await preview.evaluate(async () => {
    await document.fonts.ready
    await Promise.all([...document.images].map(img => img.complete ? Promise.resolve() : new Promise(resolve => { img.onload = resolve; img.onerror = resolve })))
  })
  for (const phase of ['intro', 'home', 'booking', 'seat', 'checkin', 'admin', 'outro']) {
    await preview.evaluate(name => setPhase(name), phase)
    await preview.waitForTimeout(900)
    const previewFile = path.join(__dirname, 'video-frames', `interactive-${phase}.png`)
    await preview.screenshot({ path: previewFile })
    if (phase === 'intro') fs.copyFileSync(previewFile, path.join(__dirname, 'animated-demo-cover-1080x1920.png'))
  }
  await preview.close()

  const context = await browser.newContext({ viewport: { width: 1080, height: 1920 }, deviceScaleFactor: 1, recordVideo: { dir: path.join(__dirname, 'video-frames'), size: { width: 1080, height: 1920 } } })
  const page = await context.newPage()
  await page.goto(html)
  await page.evaluate(async () => {
    await document.fonts.ready
    await Promise.all([...document.images].map(img => img.complete ? Promise.resolve() : new Promise(resolve => { img.onload = resolve; img.onerror = resolve })))
  })
  await page.evaluate(() => window.startDemo())
  await page.waitForTimeout(20400)
  const recordedPath = await page.video().path()
  await context.close()
  await browser.close()
  fs.copyFileSync(recordedPath, raw)

  const probe = spawnSync(ffprobe, ['-v', 'error', '-show_entries', 'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', raw], { encoding: 'utf8' })
  const recordedSeconds = Number(probe.stdout.trim())
  if (!Number.isFinite(recordedSeconds) || recordedSeconds < 20) throw new Error('Unexpected recording duration: ' + probe.stdout)
  const offset = Math.max(0, recordedSeconds - 20.4)
  const encode = spawnSync(ffmpeg, [
    '-y', '-hide_banner', '-loglevel', 'warning', '-ss', offset.toFixed(3), '-i', raw,
    '-i', path.join(__dirname, 'video-music-original.wav'), '-t', '20.3',
    '-map', '0:v', '-map', '1:a', '-c:v', 'libopenh264', '-b:v', '5500k', '-maxrate', '6500k', '-bufsize', '11000k',
    '-pix_fmt', 'yuv420p', '-r', '24', '-af', 'volume=8dB', '-c:a', 'aac', '-b:a', '160k', '-ar', '44100',
    '-movflags', '+faststart', output,
  ], { stdio: 'inherit' })
  if (encode.status !== 0) process.exit(encode.status || 1)
  console.log(output)
}

main().catch(error => { console.error(error); process.exit(1) })
