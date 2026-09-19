<template>
  <div class="landing" @pointermove="onMove">
    <div class="aurora" aria-hidden="true">
      <span class="blob b1"></span>
      <span class="blob b2"></span>
      <span class="blob b3"></span>
    </div>
    <div class="grid-bg" aria-hidden="true"></div>
    <div class="spotlight" aria-hidden="true"></div>

    <!-- 顶部导航 -->
    <nav class="nav">
      <div class="nav-brand">
        <div class="brand-mark">知</div>
        <div>
          <b>知行岛</b>
          <span>自习室智能管理平台</span>
        </div>
      </div>
      <div class="nav-links">
        <a href="#features">产品能力</a>
        <a href="#pitch">为什么选我们</a>
        <a href="#pricing">套餐价格</a>
        <a href="#contact">联系我们</a>
        <el-button type="primary" @click="goLogin">进入后台</el-button>
      </div>
    </nav>

    <!-- Hero -->
    <section class="hero">
      <div class="hero-left">
        <span class="hero-badge"><i class="live-dot"></i>已服务多家自习室，稳定运行</span>
        <h1>
          让一家自习室<br />
          <span class="accent">自己会打理</span>
        </h1>
        <p class="hero-sub">
          座位排位、门锁、团购对账、会员卡、AI 学习助手<br />
          一套后台把琐事全收了，老板娘从财务里解放出来。
        </p>
        <div class="hero-cta">
          <el-button type="primary" size="large" @click="goLogin"><span>免费试用 7 天</span><el-icon><ArrowRight /></el-icon></el-button>
          <el-button size="large" @click="scrollTo('#contact')">加微信咨询</el-button>
        </div>
        <div class="hero-stats">
          <div><b>4</b><span>渠道自动对账</span></div>
          <div class="sep"></div>
          <div><b>≤ 5min</b><span>月度对账时间</span></div>
          <div class="sep"></div>
          <div><b>0</b><span>门店多少家均免费</span></div>
        </div>
      </div>

      <!-- 右侧：产品截图 mock -->
      <div class="hero-right">
        <div class="browser">
          <div class="bar">
            <span class="dot r"></span><span class="dot y"></span><span class="dot g"></span>
            <div class="url">islandspace.top / dashboard</div>
          </div>
          <div class="mock">
            <div class="mock-side">
              <div class="mock-logo"></div>
              <div v-for="i in 8" :key="i" class="mock-nav-item" :class="{ active: i === 1 }"></div>
            </div>
            <div class="mock-main">
              <div class="mock-kpi">
                <div v-for="i in 3" :key="i" class="mock-kpi-card">
                  <div class="mock-line s"></div>
                  <div class="mock-line l"></div>
                </div>
              </div>
              <div class="mock-chart">
                <svg viewBox="0 0 300 100" preserveAspectRatio="none">
                  <defs>
                    <linearGradient id="mock-area" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stop-color="#FFD000" stop-opacity="0.5" />
                      <stop offset="100%" stop-color="#FFD000" stop-opacity="0" />
                    </linearGradient>
                  </defs>
                  <path d="M0,70 Q40,50 70,55 T140,40 T210,50 T300,20 L300,100 L0,100 Z" fill="url(#mock-area)" />
                  <path d="M0,70 Q40,50 70,55 T140,40 T210,50 T300,20" fill="none" stroke="#FFD000" stroke-width="2.5" />
                </svg>
              </div>
              <div class="mock-todos">
                <div v-for="i in 4" :key="i" class="mock-todo" :class="{ warn: i === 3 }"></div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- 能力 -->
    <section id="features" class="section">
      <div class="section-head">
        <span class="section-tag">产品能力</span>
        <h2>6 大模块，覆盖自习室 90% 日常</h2>
        <p>从学员进店到财务对账，每一步都不用你亲自跑腿。</p>
      </div>
      <div class="features">
        <article v-for="f in features" :key="f.title" class="feat">
          <div class="feat-icon"><el-icon><component :is="f.icon" /></el-icon></div>
          <h3>{{ f.title }}</h3>
          <p>{{ f.desc }}</p>
        </article>
      </div>
    </section>

    <!-- 为什么选我们 -->
    <section id="pitch" class="section pitch">
      <div class="section-head">
        <span class="section-tag">为什么选我们</span>
        <h2>不是"通用后台改包"，是自习室主自己写的</h2>
      </div>
      <div class="pitch-grid">
        <div v-for="p in pitches" :key="p.title" class="pitch-card">
          <div class="pitch-num">{{ p.num }}</div>
          <h3>{{ p.title }}</h3>
          <p>{{ p.desc }}</p>
        </div>
      </div>
    </section>

    <!-- 价格 -->
    <section id="pricing" class="section">
      <div class="section-head">
        <span class="section-tag">套餐</span>
        <h2>先免费用，觉得好再付</h2>
      </div>
      <div class="pricing">
        <div class="price-card">
          <div class="price-name">试用版</div>
          <div class="price-amt"><b>¥0</b><span>/ 7 天</span></div>
          <ul>
            <li>1 家门店</li><li>核心 6 大模块</li><li>不限座位数</li><li>基础技术支持</li>
          </ul>
          <el-button @click="goLogin">立即试用</el-button>
        </div>
        <div class="price-card featured">
          <div class="price-tag">推荐</div>
          <div class="price-name">经营版</div>
          <div class="price-amt"><b>¥199</b><span>/ 月 · 单店</span></div>
          <ul>
            <li>全部模块（含 AI 学习助手）</li><li>四渠道自动对账</li><li>蓝牙锁远程管理</li><li>专属微信答疑群</li>
          </ul>
          <el-button type="primary" @click="scrollTo('#contact')">加微信开通</el-button>
        </div>
        <div class="price-card">
          <div class="price-name">连锁版</div>
          <div class="price-amt"><b>议价</b><span>3 家以上门店</span></div>
          <ul>
            <li>多店数据看板</li><li>分店权限隔离</li><li>定制导出报表</li><li>驻场部署可选</li>
          </ul>
          <el-button @click="scrollTo('#contact')">联系咨询</el-button>
        </div>
      </div>
    </section>

    <!-- 联系 -->
    <section id="contact" class="section contact">
      <div class="contact-inner">
        <div>
          <span class="section-tag">开始使用</span>
          <h2>加微信，30 秒开通你的自习室后台</h2>
          <p>回复"自习室系统"，我把试用链接和 5 分钟上手指南发给你。</p>
        </div>
        <div class="qr-block">
          <div class="qr-wrap">
            <div class="qr-placeholder">
              <span>微信二维码</span>
              <i>（部署后替换为真实二维码图片）</i>
            </div>
          </div>
          <p><b>微信</b> zhixingdao_admin</p>
        </div>
      </div>
    </section>

    <footer class="foot">
      <span>© {{ year }} 知行岛 · 自习室智能管理平台</span>
      <span class="foot-links">
        <a @click="goLogin">进入后台</a> · <a href="#features">产品能力</a> · <a href="#pricing">价格</a>
      </span>
    </footer>
  </div>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router'
import {
  ArrowRight, Calendar, DataAnalysis, Lock, Reading, ShoppingBag, Wallet,
} from '@element-plus/icons-vue'

const router = useRouter()
const year = new Date().getFullYear()

const features = [
  { icon: Calendar, title: '座位与预约',   desc: '楼层布局可视化排位、学员端一键选座、时段占用一目了然。' },
  { icon: Lock,     title: '蓝牙 / 远程锁', desc: '预约生效自动放行、低电量告警、异常开门记录全留存。' },
  { icon: Wallet,   title: '四渠道对账',   desc: '美团、抖音、微信支付、微信转账统一到收款台账，退款单独跟踪。' },
  { icon: ShoppingBag, title: '会员卡与积分', desc: '期限卡、次卡、余额、优惠券、邀请闭环，学员端小程序无感衔接。' },
  { icon: DataAnalysis, title: '数据看板',   desc: '每天营收、入座率、待办事项一屏看完，CSV 一键导出。' },
  { icon: Reading,  title: 'AI 学习助手',   desc: '错题本、学习报告、AI 问答，让学员留在你这里而不是隔壁。' },
]

const pitches = [
  { num: '01', title: '我们自己是自习室老板', desc: '每一行代码都为了解决"我今天遇到的问题"，不是猜的。' },
  { num: '02', title: '一次买断，不按门店抽成', desc: '不像有些系统按每笔订单抽 3%——你多做的生意都是自己的。' },
  { num: '03', title: '微信直连，答疑不用等工单', desc: '有 bug、有想法直接群里说，作者当天回复。' },
  { num: '04', title: '数据在你的服务器', desc: '所有数据可以部署在你自己的云上，我们提供部署脚本。' },
]

function goLogin() { router.push('/login') }
function scrollTo(sel: string) { document.querySelector(sel)?.scrollIntoView({ behavior: 'smooth' }) }
function onMove(e: PointerEvent) {
  const el = e.currentTarget as HTMLElement
  el.style.setProperty('--mx', `${e.clientX}px`)
  el.style.setProperty('--my', `${e.clientY}px`)
}
</script>

<style scoped>
.landing {
  position: relative;
  min-height: 100vh;
  background: #0a0b0d;
  color: #e6e6e8;
  overflow-x: hidden;
  font-family: -apple-system, BlinkMacSystemFont, "PingFang SC", "Microsoft YaHei", "Segoe UI", sans-serif;
}

/* ========== 背景层 ========== */
.aurora { position: fixed; inset: 0; z-index: 0; overflow: hidden; pointer-events: none; }
.blob { position: absolute; border-radius: 50%; filter: blur(100px); animation: drift 24s ease-in-out infinite; }
.b1 { width: 720px; height: 720px; background: radial-gradient(circle, #FFD000, transparent 65%); top: -200px; left: -180px; opacity: 0.5; }
.b2 { width: 620px; height: 620px; background: radial-gradient(circle, #6366f1, transparent 65%); top: 40%; right: -180px; animation-delay: -8s; opacity: 0.45; }
.b3 { width: 520px; height: 520px; background: radial-gradient(circle, #22d3ee, transparent 65%); bottom: -160px; left: 30%; animation-delay: -14s; opacity: 0.28; }
@keyframes drift {
  0%, 100% { transform: translate(0, 0) scale(1); }
  33%      { transform: translate(60px, -40px) scale(1.06); }
  66%      { transform: translate(-40px, 30px) scale(0.94); }
}
.grid-bg {
  position: fixed; inset: 0; z-index: 1; pointer-events: none;
  background-image:
    linear-gradient(rgba(255,255,255,0.045) 1px, transparent 1px),
    linear-gradient(90deg, rgba(255,255,255,0.045) 1px, transparent 1px);
  background-size: 50px 50px;
  mask-image: radial-gradient(ellipse at 50% 30%, black 20%, transparent 65%);
  -webkit-mask-image: radial-gradient(ellipse at 50% 30%, black 20%, transparent 65%);
}
.spotlight {
  position: fixed; inset: 0; z-index: 1; pointer-events: none;
  background: radial-gradient(600px circle at var(--mx, 50%) var(--my, 30%),
    rgba(255, 208, 0, 0.08), transparent 60%);
  transition: background 0.15s ease-out;
}

/* ========== 顶部导航 ========== */
.nav {
  position: sticky; top: 0; z-index: 10;
  display: flex; justify-content: space-between; align-items: center;
  padding: 18px 48px;
  background: rgba(10, 11, 13, 0.75);
  backdrop-filter: blur(20px);
  border-bottom: 1px solid rgba(255,255,255,0.06);
}
.nav-brand { display: flex; align-items: center; gap: 12px; }
.brand-mark {
  width: 38px; height: 38px; border-radius: 10px;
  background: linear-gradient(135deg, #FFD000, #ffb400);
  color: #1a1a1a; font-weight: 700; font-size: 18px;
  display: flex; align-items: center; justify-content: center;
  box-shadow: 0 6px 20px rgba(255, 208, 0, 0.35);
}
.nav-brand b { display: block; font-size: 15px; font-weight: 600; color: #f5f5f7; letter-spacing: 0.5px; }
.nav-brand span { display: block; font-size: 11px; color: #7a7b83; margin-top: 2px; }
.nav-links { display: flex; align-items: center; gap: 8px; }
.nav-links a {
  padding: 8px 14px; font-size: 13.5px; color: #9a9ba3; cursor: pointer;
  border-radius: 8px; transition: color 0.2s, background 0.2s;
}
.nav-links a:hover { color: #f5f5f7; background: rgba(255,255,255,0.04); }

/* ========== Hero ========== */
.hero {
  position: relative; z-index: 2;
  display: grid; grid-template-columns: 1.1fr 1fr; gap: 60px;
  padding: 80px 48px 100px;
  max-width: 1280px; margin: 0 auto;
  align-items: center;
}
.hero-badge {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 6px 12px; border-radius: 999px;
  background: rgba(34, 197, 94, 0.10); border: 1px solid rgba(34, 197, 94, 0.28);
  color: #86efac; font-size: 12px; margin-bottom: 24px;
}
.live-dot {
  width: 6px; height: 6px; border-radius: 50%; background: #22c55e;
  box-shadow: 0 0 8px #22c55e;
  animation: pulse 1.6s ease-in-out infinite;
}
@keyframes pulse { 0%, 100% { opacity: 1; transform: scale(1); } 50% { opacity: 0.4; transform: scale(0.85); } }

.hero h1 {
  font-size: 52px; line-height: 1.15; font-weight: 700;
  letter-spacing: -1px; color: #f5f5f7; margin: 0 0 20px;
}
.accent {
  background: linear-gradient(135deg, #FFD000, #ffb400);
  -webkit-background-clip: text; background-clip: text; color: transparent;
}
.hero-sub { font-size: 15px; line-height: 1.7; color: #a0a1a9; margin: 0 0 32px; }
.hero-cta { display: flex; gap: 12px; margin-bottom: 40px; }
.hero-cta :deep(.el-button) { padding: 12px 22px; height: auto; font-size: 14px; border-radius: 12px; }

.hero-stats { display: flex; align-items: center; gap: 24px; }
.hero-stats > div:not(.sep) { display: flex; flex-direction: column; }
.hero-stats b { font-size: 26px; color: #f5f5f7; font-weight: 700; letter-spacing: -0.3px; }
.hero-stats span { font-size: 12px; color: #7a7b83; margin-top: 4px; }
.sep { width: 1px; height: 40px; background: rgba(255,255,255,0.08); }

/* --- 浏览器窗口 mock --- */
.hero-right { display: flex; justify-content: center; }
.browser {
  width: 100%; max-width: 560px; border-radius: 16px;
  background: #14161a;
  border: 1px solid rgba(255,255,255,0.09);
  box-shadow: 0 40px 100px rgba(0,0,0,0.5), 0 0 0 1px rgba(255, 208, 0, 0.05);
  overflow: hidden;
  transform: perspective(1200px) rotateY(-6deg) rotateX(4deg);
  transition: transform 0.4s ease;
}
.browser:hover { transform: perspective(1200px) rotateY(-3deg) rotateX(2deg); }
.bar {
  display: flex; align-items: center; gap: 8px;
  padding: 10px 14px; background: #1c1e24; border-bottom: 1px solid rgba(255,255,255,0.05);
}
.bar .dot { width: 10px; height: 10px; border-radius: 50%; }
.dot.r { background: #ef4444; } .dot.y { background: #f59e0b; } .dot.g { background: #22c55e; }
.bar .url {
  flex: 1; text-align: center; font-size: 11px; color: #7a7b83;
  padding: 4px 10px; background: rgba(255,255,255,0.03); border-radius: 6px;
  margin: 0 20px;
}
.mock { display: grid; grid-template-columns: 120px 1fr; height: 320px; }
.mock-side { background: #0f1114; padding: 14px 10px; display: flex; flex-direction: column; gap: 8px; }
.mock-logo { width: 26px; height: 26px; border-radius: 6px; background: linear-gradient(135deg, #FFD000, #ffb400); margin-bottom: 10px; }
.mock-nav-item { height: 8px; border-radius: 4px; background: rgba(255,255,255,0.06); }
.mock-nav-item.active { background: rgba(255, 208, 0, 0.3); box-shadow: inset 3px 0 0 #FFD000; }
.mock-main { padding: 16px; display: flex; flex-direction: column; gap: 12px; background: #0a0b0d; }
.mock-kpi { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; }
.mock-kpi-card {
  padding: 10px; border-radius: 8px; background: rgba(255,255,255,0.03);
  border: 1px solid rgba(255,255,255,0.05);
}
.mock-line { height: 4px; border-radius: 2px; background: rgba(255,255,255,0.1); }
.mock-line.s { width: 40%; margin-bottom: 6px; }
.mock-line.l { width: 70%; height: 8px; background: rgba(255,255,255,0.2); }
.mock-chart { flex: 1; background: rgba(255,255,255,0.02); border-radius: 8px; padding: 8px; }
.mock-chart svg { width: 100%; height: 100%; }
.mock-todos { display: grid; grid-template-columns: repeat(4, 1fr); gap: 6px; }
.mock-todo { height: 32px; border-radius: 6px; background: rgba(255,255,255,0.03); }
.mock-todo.warn { background: rgba(255, 208, 0, 0.15); box-shadow: inset 0 0 0 1px rgba(255, 208, 0, 0.3); }

/* ========== 章节通用 ========== */
.section {
  position: relative; z-index: 2;
  max-width: 1120px; margin: 0 auto;
  padding: 80px 48px;
}
.section-head { text-align: center; max-width: 640px; margin: 0 auto 48px; }
.section-tag {
  display: inline-block; padding: 4px 10px; border-radius: 999px;
  background: rgba(255, 208, 0, 0.10); border: 1px solid rgba(255, 208, 0, 0.25);
  color: #FFD000; font-size: 11px; letter-spacing: 1px; text-transform: uppercase;
  margin-bottom: 16px;
}
.section-head h2 { font-size: 32px; color: #f5f5f7; letter-spacing: -0.3px; margin: 0 0 12px; font-weight: 700; }
.section-head p  { font-size: 14px; color: #909096; line-height: 1.6; margin: 0; }

/* ========== 能力卡 ========== */
.features { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; }
.feat {
  padding: 28px 24px; border-radius: 16px;
  background: rgba(18, 20, 26, 0.55);
  border: 1px solid rgba(255,255,255,0.08);
  backdrop-filter: blur(20px);
  transition: transform 0.3s ease, border-color 0.3s ease, box-shadow 0.3s ease;
}
.feat:hover {
  transform: translateY(-4px);
  border-color: rgba(255, 208, 0, 0.3);
  box-shadow: 0 20px 40px rgba(255, 208, 0, 0.06);
}
.feat-icon {
  width: 44px; height: 44px; border-radius: 12px; margin-bottom: 18px;
  background: rgba(255, 208, 0, 0.12); border: 1px solid rgba(255, 208, 0, 0.28);
  color: #FFD000; display: flex; align-items: center; justify-content: center;
  font-size: 20px;
}
.feat h3 { margin: 0 0 8px; font-size: 16px; color: #f5f5f7; font-weight: 600; }
.feat p  { margin: 0; font-size: 13.5px; line-height: 1.7; color: #909096; }

/* ========== 为什么选我们 ========== */
.pitch-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 16px; }
.pitch-card {
  position: relative;
  padding: 32px 28px; border-radius: 16px;
  background: rgba(18, 20, 26, 0.55);
  border: 1px solid rgba(255,255,255,0.08);
  backdrop-filter: blur(20px);
}
.pitch-num {
  position: absolute; top: 24px; right: 28px;
  font-size: 32px; font-weight: 800; color: rgba(255, 208, 0, 0.15);
  letter-spacing: -1px;
}
.pitch-card h3 { margin: 0 0 10px; font-size: 17px; color: #f5f5f7; font-weight: 600; }
.pitch-card p  { margin: 0; font-size: 14px; line-height: 1.7; color: #909096; }

/* ========== 价格 ========== */
.pricing { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; }
.price-card {
  position: relative;
  padding: 32px 28px; border-radius: 16px;
  background: rgba(18, 20, 26, 0.55);
  border: 1px solid rgba(255,255,255,0.08);
  backdrop-filter: blur(20px);
  display: flex; flex-direction: column;
}
.price-card.featured {
  border-color: rgba(255, 208, 0, 0.4);
  box-shadow: 0 20px 60px rgba(255, 208, 0, 0.15);
}
.price-tag {
  position: absolute; top: -10px; left: 28px;
  padding: 4px 10px; border-radius: 999px;
  background: linear-gradient(135deg, #FFD000, #ffb400);
  color: #1a1a1a; font-size: 11px; font-weight: 600; letter-spacing: 0.5px;
}
.price-name { font-size: 14px; color: #909096; margin-bottom: 12px; }
.price-amt { margin-bottom: 24px; }
.price-amt b { font-size: 36px; color: #f5f5f7; font-weight: 700; letter-spacing: -0.5px; }
.price-amt span { font-size: 13px; color: #7a7b83; margin-left: 6px; }
.price-card ul { list-style: none; padding: 0; margin: 0 0 24px; flex: 1; }
.price-card li { padding: 8px 0 8px 22px; font-size: 13.5px; color: #a0a1a9; position: relative; }
.price-card li::before {
  content: '✓'; position: absolute; left: 0; top: 8px;
  color: #FFD000; font-weight: 700;
}

/* ========== 联系 ========== */
.contact { padding-bottom: 100px; }
.contact-inner {
  display: grid; grid-template-columns: 1.2fr 1fr; gap: 60px;
  padding: 48px; border-radius: 20px;
  background: linear-gradient(135deg, rgba(255, 208, 0, 0.08), rgba(99, 102, 241, 0.05));
  border: 1px solid rgba(255, 208, 0, 0.2);
  backdrop-filter: blur(24px);
  align-items: center;
}
.contact h2 { margin: 12px 0; }
.contact p { color: #a0a1a9; font-size: 14px; line-height: 1.7; }
.qr-block { text-align: center; }
.qr-wrap {
  width: 180px; height: 180px; margin: 0 auto 14px;
  padding: 8px; border-radius: 14px; background: #fff;
  box-shadow: 0 12px 40px rgba(255, 208, 0, 0.2);
}
.qr-placeholder {
  width: 100%; height: 100%; border-radius: 8px;
  background: repeating-conic-gradient(#0a0b0d 0% 25%, #fff 0% 50%) 50% / 12px 12px;
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  color: #f5f5f7; text-align: center;
  position: relative;
}
.qr-placeholder span {
  background: rgba(10,11,13,0.85); padding: 4px 10px; border-radius: 6px;
  font-size: 12px; letter-spacing: 0.5px;
}
.qr-placeholder i { display: block; font-style: normal; font-size: 10px; color: #909096; margin-top: 6px; background: rgba(10,11,13,0.7); padding: 2px 8px; border-radius: 4px; }
.qr-block p { color: #909096; font-size: 13px; }
.qr-block b { color: #FFD000; font-family: monospace; letter-spacing: 0.5px; }

/* ========== 底部 ========== */
.foot {
  position: relative; z-index: 2;
  display: flex; justify-content: space-between; align-items: center;
  padding: 24px 48px;
  border-top: 1px solid rgba(255,255,255,0.05);
  font-size: 12px; color: #5c5c66;
}
.foot-links a { color: #7a7b83; cursor: pointer; margin: 0 4px; }
.foot-links a:hover { color: #FFD000; }

/* ========== 响应式 ========== */
@media (max-width: 900px) {
  .nav { padding: 14px 20px; }
  .nav-links a:not(:last-child), .nav-links .el-button:not(:last-child) { display: none; }
  .hero { grid-template-columns: 1fr; padding: 40px 20px 60px; gap: 40px; }
  .hero h1 { font-size: 36px; }
  .section { padding: 60px 20px; }
  .features, .pitch-grid, .pricing { grid-template-columns: 1fr; }
  .contact-inner { grid-template-columns: 1fr; padding: 28px; gap: 32px; text-align: center; }
  .foot { flex-direction: column; gap: 8px; text-align: center; }
}

/* Element Plus button 深色主题内 override */
:deep(.el-button--default) {
  background: rgba(255,255,255,0.06) !important;
  border-color: rgba(255,255,255,0.12) !important;
  color: #e6e6e8 !important;
}
:deep(.el-button--default:hover) {
  background: rgba(255,255,255,0.10) !important;
  border-color: rgba(255,255,255,0.2) !important;
  color: #f5f5f7 !important;
}
</style>
