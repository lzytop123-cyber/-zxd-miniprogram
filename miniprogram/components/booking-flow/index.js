const CACHE_VERSION = 'v2'

const STEPS = [
  { n: 1, title: '选择门店', desc: '切换至千峰南路店 / 长风街店', cat: 'base' },
  { n: 2, title: '选择套餐', desc: '时长卡 · 次卡 · 夜读', cat: 'base' },
  { n: 3, title: '在线选座', desc: '标准区 · 沉浸区 · 快捷座', cat: 'seat' },
  { n: 4, title: '确认支付', desc: '微信支付一键完成', cat: 'pay' },
  { n: 5, title: '到店开门', desc: '支付/到点/开门自动入座', cat: 'entry' },
  { n: 6, title: '开始自习', desc: '计时管理，到点续费或离场', cat: 'base' },
]

const THEMES = {
  base: { bg: '#E8F5E9', border: '#52B788', badge: '#2D6A4F' },
  seat: { bg: '#E0F2F1', border: '#40916C', badge: '#2e7d5f' },
  pay: { bg: '#FFF8E6', border: '#C9A227', badge: '#8A6D3B' },
  entry: { bg: '#D8F3DC', border: '#1B4332', badge: '#1B4332' },
}

const LEGEND = [
  { label: '选座', color: '#40916C' },
  { label: '支付', color: '#C9A227' },
  { label: '入场', color: '#1B4332' },
]

function rpx(v, windowWidth) {
  return (windowWidth / 750) * v
}

function roundRect(ctx, x, y, w, h, radius) {
  const r = Math.min(radius, w / 2, h / 2)
  ctx.beginPath()
  ctx.moveTo(x + r, y)
  ctx.arcTo(x + w, y, x + w, y + h, r)
  ctx.arcTo(x + w, y + h, x, y + h, r)
  ctx.arcTo(x, y + h, x, y, r)
  ctx.arcTo(x, y, x + w, y, r)
  ctx.closePath()
}

function drawArrow(ctx, cx, y, size, color) {
  ctx.strokeStyle = color
  ctx.fillStyle = color
  ctx.lineWidth = 2
  ctx.beginPath()
  ctx.moveTo(cx, y)
  ctx.lineTo(cx, y + size * 0.55)
  ctx.stroke()
  ctx.beginPath()
  ctx.moveTo(cx, y + size * 0.55)
  ctx.lineTo(cx - size * 0.22, y + size * 0.32)
  ctx.lineTo(cx + size * 0.22, y + size * 0.32)
  ctx.closePath()
  ctx.fill()
}

function drawHorizontalArrow(ctx, x, cy, size, color) {
  ctx.strokeStyle = color
  ctx.fillStyle = color
  ctx.lineWidth = 2
  ctx.beginPath()
  ctx.moveTo(x - size * 0.55, cy)
  ctx.lineTo(x + size * 0.55, cy)
  ctx.stroke()
  ctx.beginPath()
  ctx.moveTo(x + size * 0.55, cy)
  ctx.lineTo(x + size * 0.32, cy - size * 0.22)
  ctx.lineTo(x + size * 0.32, cy + size * 0.22)
  ctx.closePath()
  ctx.fill()
}

function wrapText(ctx, text, x, y, maxWidth, fontSize, maxLines) {
  const chars = text.split('')
  let line = ''
  let lineY = y
  let lines = 0
  for (let i = 0; i < chars.length; i += 1) {
    const test = line + chars[i]
    if (ctx.measureText(test).width > maxWidth && line) {
      ctx.fillText(line, x, lineY)
      lines += 1
      if (lines >= maxLines) return
      line = chars[i]
      lineY += fontSize * 1.35
    } else {
      line = test
    }
  }
  if (line && lines < maxLines) ctx.fillText(line, x, lineY)
}

function drawStepCard(ctx, x, y, w, h, step, px) {
  const theme = THEMES[step.cat] || THEMES.base
  const radius = rpx(20, px.windowWidth)

  roundRect(ctx, x, y, w, h, radius)
  ctx.fillStyle = theme.bg
  ctx.fill()
  ctx.strokeStyle = theme.border
  ctx.lineWidth = 2
  ctx.stroke()

  const badgeR = rpx(26, px.windowWidth)
  const badgeCx = x + rpx(52, px.windowWidth)
  const badgeCy = y + h / 2
  ctx.beginPath()
  ctx.arc(badgeCx, badgeCy, badgeR, 0, Math.PI * 2)
  ctx.fillStyle = theme.badge
  ctx.fill()

  ctx.fillStyle = '#FFFFFF'
  ctx.font = `bold ${rpx(26, px.windowWidth)}px sans-serif`
  ctx.textAlign = 'center'
  ctx.textBaseline = 'middle'
  ctx.fillText(String(step.n), badgeCx, badgeCy + 1)

  const textX = x + rpx(96, px.windowWidth)
  const titleY = y + h * 0.38
  ctx.fillStyle = '#1C2B20'
  ctx.font = `bold ${rpx(28, px.windowWidth)}px sans-serif`
  ctx.textAlign = 'left'
  ctx.textBaseline = 'middle'
  ctx.fillText(step.title, textX, titleY)

  ctx.fillStyle = '#5A6B62'
  const fontSize = rpx(22, px.windowWidth)
  ctx.font = `${fontSize}px sans-serif`
  const maxW = w - rpx(110, px.windowWidth)
  wrapText(ctx, step.desc, textX, y + h * 0.62, maxW, fontSize, 2)
}

function drawHeroStepCard(ctx, x, y, w, h, step, px) {
  const theme = THEMES[step.cat] || THEMES.base
  const radius = rpx(14, px.windowWidth)

  roundRect(ctx, x, y, w, h, radius)
  ctx.fillStyle = 'rgba(255,255,255,0.93)'
  ctx.fill()
  ctx.strokeStyle = 'rgba(255,255,255,0.4)'
  ctx.lineWidth = 1
  ctx.stroke()

  const badgeR = rpx(18, px.windowWidth)
  const badgeCx = x + rpx(32, px.windowWidth)
  const badgeCy = y + h / 2
  ctx.beginPath()
  ctx.arc(badgeCx, badgeCy, badgeR, 0, Math.PI * 2)
  ctx.fillStyle = theme.badge
  ctx.fill()

  ctx.fillStyle = '#FFFFFF'
  ctx.font = `bold ${rpx(20, px.windowWidth)}px sans-serif`
  ctx.textAlign = 'center'
  ctx.textBaseline = 'middle'
  ctx.fillText(String(step.n), badgeCx, badgeCy + 1)

  ctx.fillStyle = '#1C2B20'
  ctx.font = `bold ${rpx(24, px.windowWidth)}px sans-serif`
  ctx.textAlign = 'left'
  ctx.textBaseline = 'middle'
  ctx.fillText(step.title, x + rpx(58, px.windowWidth), badgeCy)
}

function paintHeroBackground(ctx, width, height, windowWidth) {
  const bgGrad = ctx.createLinearGradient(0, 0, width * 0.7, height)
  bgGrad.addColorStop(0, '#2D6A4F')
  bgGrad.addColorStop(0.48, '#40916C')
  bgGrad.addColorStop(1, '#52B788')
  ctx.fillStyle = bgGrad
  ctx.fillRect(0, 0, width, height)

  ctx.fillStyle = 'rgba(255,255,255,0.07)'
  const step = rpx(36, windowWidth)
  for (let gx = step; gx < width; gx += step) {
    for (let gy = step; gy < height; gy += step) {
      ctx.beginPath()
      ctx.arc(gx, gy, 1.2, 0, Math.PI * 2)
      ctx.fill()
    }
  }
}

function measurePageLayout(windowWidth, canvasWidth) {
  const w = canvasWidth || windowWidth - rpx(48, windowWidth)
  const padX = rpx(32, windowWidth)
  const padY = rpx(28, windowWidth)
  const titleH = rpx(56, windowWidth)
  const titleGap = rpx(20, windowWidth)
  const cardW = w - padX * 2
  const cardH = rpx(136, windowWidth)
  const arrowH = rpx(40, windowWidth)
  const legendGap = rpx(28, windowWidth)
  const legendH = rpx(56, windowWidth)
  const contentH =
    padY +
    titleH +
    titleGap +
    STEPS.length * cardH +
    (STEPS.length - 1) * arrowH +
    legendGap +
    legendH +
    padY
  return { padX, padY, titleH, titleGap, cardW, cardH, arrowH, legendGap, legendH, contentH, canvasW: w }
}

function measureHeroLayout(windowWidth, heroHeightRpx) {
  const w = windowWidth
  const h = rpx(heroHeightRpx, windowWidth)
  return { canvasW: w, contentH: h }
}

function paintFlowPage(ctx, width, height, dpr, windowWidth) {
  const px = { windowWidth }
  const layout = measurePageLayout(windowWidth, width)
  ctx.scale(dpr, dpr)

  const bgGrad = ctx.createLinearGradient(0, 0, width, height)
  bgGrad.addColorStop(0, '#F4FAF6')
  bgGrad.addColorStop(1, '#FFFFFF')
  roundRect(ctx, 0, 0, width, height, rpx(24, windowWidth))
  ctx.fillStyle = bgGrad
  ctx.fill()

  let y = layout.padY
  ctx.fillStyle = '#2D6A4F'
  ctx.font = `bold ${rpx(34, windowWidth)}px sans-serif`
  ctx.textAlign = 'left'
  ctx.textBaseline = 'top'
  ctx.fillText('预约流程', layout.padX, y)
  y += layout.titleH + layout.titleGap

  const cardX = layout.padX
  const cardW = layout.cardW
  const cx = width / 2

  STEPS.forEach((step, idx) => {
    drawStepCard(ctx, cardX, y, cardW, layout.cardH, step, px)
    y += layout.cardH
    if (idx < STEPS.length - 1) {
      drawArrow(ctx, cx, y + rpx(4, windowWidth), layout.arrowH - rpx(8, windowWidth), '#52B788')
      y += layout.arrowH
    }
  })

  y += layout.legendGap
  const legendItemW = cardW / LEGEND.length
  LEGEND.forEach((item, i) => {
    const lx = cardX + legendItemW * i + legendItemW * 0.12
    const dotR = rpx(8, windowWidth)
    ctx.beginPath()
    ctx.arc(lx, y + rpx(10, windowWidth), dotR, 0, Math.PI * 2)
    ctx.fillStyle = item.color
    ctx.fill()
    ctx.fillStyle = '#8C9BA5'
    ctx.font = `${rpx(20, windowWidth)}px sans-serif`
    ctx.textAlign = 'left'
    ctx.textBaseline = 'middle'
    ctx.fillText(item.label, lx + rpx(20, windowWidth), y + rpx(10, windowWidth))
  })
}

function paintFlowHero(ctx, width, height, dpr, windowWidth) {
  const px = { windowWidth }
  ctx.scale(dpr, dpr)
  paintHeroBackground(ctx, width, height, windowWidth)

  const pad = rpx(28, windowWidth)
  const headerH = rpx(88, windowWidth)
  const legendH = rpx(44, windowWidth)
  const colGap = rpx(14, windowWidth)
  const rowGap = rpx(18, windowWidth)
  const gridW = width - pad * 2
  const gridTop = headerH + rpx(8, windowWidth)
  const gridH = height - gridTop - legendH - pad * 0.5
  const colW = (gridW - colGap) / 2
  const rowH = (gridH - 2 * rowGap) / 3

  ctx.fillStyle = '#FFFFFF'
  ctx.font = `bold ${rpx(36, windowWidth)}px sans-serif`
  ctx.textAlign = 'left'
  ctx.textBaseline = 'top'
  ctx.fillText('预约流程指引', pad, pad)
  ctx.fillStyle = 'rgba(255,255,255,0.88)'
  ctx.font = `${rpx(22, windowWidth)}px sans-serif`
  ctx.fillText('6 步轻松入座自习', pad, pad + rpx(44, windowWidth))

  STEPS.forEach((step, i) => {
    const col = i % 2
    const row = Math.floor(i / 2)
    const x = pad + col * (colW + colGap)
    const y = gridTop + row * (rowH + rowGap)
    drawHeroStepCard(ctx, x, y, colW, rowH, step, px)
  })

  for (let row = 0; row < 3; row += 1) {
    const yMid = gridTop + row * (rowH + rowGap) + rowH / 2
    const xMid = pad + colW + colGap / 2
    drawHorizontalArrow(ctx, xMid, yMid, rpx(18, windowWidth), 'rgba(255,255,255,0.7)')
  }

  for (let row = 0; row < 2; row += 1) {
    const arrowY = gridTop + (row + 1) * rowH + row * rowGap + rowGap * 0.42
    drawArrow(ctx, width / 2, arrowY, rpx(22, windowWidth), 'rgba(255,255,255,0.65)')
  }

  const legendY = height - pad - legendH * 0.5
  const legendItemW = gridW / LEGEND.length
  LEGEND.forEach((item, i) => {
    const lx = pad + legendItemW * i + legendItemW * 0.15
    const dotR = rpx(7, windowWidth)
    ctx.beginPath()
    ctx.arc(lx, legendY, dotR, 0, Math.PI * 2)
    ctx.fillStyle = item.color
    ctx.fill()
    ctx.fillStyle = 'rgba(255,255,255,0.82)'
    ctx.font = `${rpx(20, windowWidth)}px sans-serif`
    ctx.textAlign = 'left'
    ctx.textBaseline = 'middle'
    ctx.fillText(item.label, lx + rpx(18, windowWidth), legendY)
  })
}

Component({
  properties: {
    mode: {
      type: String,
      value: 'hero',
    },
    heroHeight: {
      type: Number,
      value: 680,
    },
  },

  data: {
    imagePath: '',
    ready: false,
    canvasHeight: 200,
    placeholderHeight: 200,
  },

  observers: {
    'heroHeight, mode'() {
      if (this._attached) this.initFlow()
    },
  },

  lifetimes: {
    attached() {
      this._attached = true
      this.initFlow()
    },
  },

  methods: {
    cacheKey() {
      const mode = this.properties.mode || 'hero'
      if (mode === 'hero') {
        return `booking_flow_hero_${this.properties.heroHeight}_${CACHE_VERSION}`
      }
      return `booking_flow_page_${CACHE_VERSION}`
    },

    cacheFileName() {
      return `${this.cacheKey()}.png`
    },

    initFlow() {
      const cached = this.loadCache()
      if (cached) {
        this.setData({ imagePath: cached, ready: false })
        return
      }

      const sys = wx.getSystemInfoSync()
      const mode = this.properties.mode || 'hero'
      const layout =
        mode === 'hero'
          ? measureHeroLayout(sys.windowWidth, this.properties.heroHeight)
          : measurePageLayout(sys.windowWidth)

      this.setData({
        imagePath: '',
        ready: true,
        canvasHeight: layout.contentH,
        placeholderHeight: layout.contentH,
      })
      wx.nextTick(() => this.drawAndCache())
    },

    loadCache() {
      try {
        const path = wx.getStorageSync(this.cacheKey())
        if (!path) return ''
        wx.getFileSystemManager().accessSync(path)
        return path
      } catch (e) {
        return ''
      }
    },

    saveCache(tempPath) {
      return new Promise((resolve, reject) => {
        const fs = wx.getFileSystemManager()
        const dest = `${wx.env.USER_DATA_PATH}/${this.cacheFileName()}`
        fs.saveFile({
          tempFilePath: tempPath,
          filePath: dest,
          success: () => {
            wx.setStorageSync(this.cacheKey(), dest)
            resolve(dest)
          },
          fail: reject,
        })
      })
    },

    drawAndCache() {
      const query = this.createSelectorQuery()
      query
        .select('#flowCanvas')
        .fields({ node: true, size: true })
        .exec((res) => {
          const item = res && res[0]
          if (!item || !item.node) return

          const canvas = item.node
          const ctx = canvas.getContext('2d')
          const sys = wx.getSystemInfoSync()
          const dpr = sys.pixelRatio || 2
          const mode = this.properties.mode || 'hero'
          const cssW =
            mode === 'hero'
              ? sys.windowWidth
              : item.width || sys.windowWidth - rpx(48, sys.windowWidth)
          const layout =
            mode === 'hero'
              ? measureHeroLayout(sys.windowWidth, this.properties.heroHeight)
              : measurePageLayout(sys.windowWidth, cssW)
          const cssH = layout.contentH

          canvas.width = cssW * dpr
          canvas.height = cssH * dpr

          this.setData({ canvasHeight: cssH })

          if (mode === 'hero') {
            paintFlowHero(ctx, cssW, cssH, dpr, sys.windowWidth)
          } else {
            paintFlowPage(ctx, cssW, cssH, dpr, sys.windowWidth)
          }

          wx.canvasToTempFilePath({
            canvas,
            success: async (out) => {
              try {
                const saved = await this.saveCache(out.tempFilePath)
                this.setData({ imagePath: saved, ready: false })
              } catch (e) {
                this.setData({ imagePath: out.tempFilePath, ready: false })
              }
            },
            fail: () => {
              this.setData({ ready: true })
            },
          })
        })
    },
  },
})
