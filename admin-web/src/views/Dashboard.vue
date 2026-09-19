<template>
  <div class="dashboard">
    <!-- 顶部问候 + 快捷动作 -->
    <header class="greet">
      <div>
        <h1>{{ greeting }}，{{ adminName }}</h1>
        <p>{{ dateLine }}</p>
      </div>
      <div class="quick">
        <span class="pill"><i class="live-dot"></i>营业中 · {{ store_count }} 家门店</span>
        <el-button :icon="Refresh" @click="refreshAll" :loading="loading">刷新数据</el-button>
      </div>
    </header>

    <!-- 主要指标（3 张大卡） -->
    <section class="kpi-primary">
      <article v-for="k in primary" :key="k.label" class="kpi" :class="k.accent">
        <div class="kpi-head">
          <span class="kpi-label">{{ k.label }}</span>
          <el-icon class="kpi-icon"><component :is="k.icon" /></el-icon>
        </div>
        <div class="kpi-value">{{ k.value }}</div>
        <div v-if="k.progress != null" class="kpi-progress">
          <div class="bar"><i :style="{ width: k.progress + '%' }"></i></div>
          <span class="progress-hint">{{ k.progressHint }}</span>
        </div>
        <div v-else class="kpi-hint">{{ k.hint }}</div>
      </article>
    </section>

    <!-- 次要指标（细长条） -->
    <section class="kpi-strip">
      <div v-for="k in secondary" :key="k.label" class="mini">
        <el-icon class="mini-icon"><component :is="k.icon" /></el-icon>
        <div>
          <div class="mini-label">{{ k.label }}</div>
          <div class="mini-value">{{ k.value }}</div>
        </div>
      </div>
    </section>

    <!-- 运营待办 -->
    <section class="panel">
      <header class="panel-head">
        <h3>运营待办</h3>
        <span class="muted">点击卡片跳到对应模块处理</span>
      </header>
      <div class="todos">
        <router-link v-for="t in todoList" :key="t.label" :to="t.link" class="todo" :class="{ warn: t.count > 0 }">
          <div class="todo-top">
            <el-icon class="todo-icon"><component :is="t.icon" /></el-icon>
            <span>{{ t.label }}</span>
            <el-icon class="chev"><ArrowRight /></el-icon>
          </div>
          <div class="todo-value">{{ t.count }}</div>
          <div class="todo-sub" v-if="t.sub">{{ t.sub }}</div>
        </router-link>
      </div>
    </section>

    <!-- 营收 + 导出 -->
    <div class="two-col">
      <section class="panel">
        <header class="panel-head">
          <h3>近 7 日营收</h3>
          <span class="muted">总计 ¥{{ revenueSum.toLocaleString('zh-CN') }} · {{ revenueOrders }} 单</span>
        </header>
        <div ref="chartEl" class="revenue-chart"></div>
      </section>

      <section class="panel">
        <header class="panel-head">
          <h3>数据导出</h3>
        </header>
        <div class="exports">
          <button v-for="e in exports" :key="e.path" class="export-item" @click="downloadExport(e.path)">
            <span class="export-icon"><el-icon><Download /></el-icon></span>
            <div class="export-text">
              <b>{{ e.label }}</b>
              <i>{{ e.hint }}</i>
            </div>
            <el-icon class="chev"><ArrowRight /></el-icon>
          </button>
        </div>
      </section>
    </div>

    <!-- 小程序 ↔ 后台入口，折叠 -->
    <details class="collapse-panel">
      <summary>
        <div>
          <b>小程序功能 ↔ 后台入口</b>
          <i>共 {{ featureMap.length }} 项 · 学员端到管理端的映射关系</i>
        </div>
        <el-icon class="chev"><ArrowDown /></el-icon>
      </summary>
      <div class="feature-grid">
        <div v-for="f in featureMap" :key="f.mp" class="feature-row">
          <span class="mp">{{ f.mp }}</span>
          <el-icon class="arrow"><ArrowRight /></el-icon>
          <span class="admin">{{ f.admin }}</span>
        </div>
      </div>
    </details>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import {
  Refresh, ArrowRight, ArrowDown, Download,
  Money, TrendCharts, PieChart,
  Ticket, User, Plus, Location, OfficeBuilding,
  CreditCard, Setting, Bell,
} from '@element-plus/icons-vue'
import * as echarts from 'echarts/core'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, MarkLineComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import http from '../api/http'

echarts.use([LineChart, GridComponent, TooltipComponent, MarkLineComponent, CanvasRenderer])

const revenue = ref<any[]>([])
const stats = ref<any>({})
const todos = ref<any>({})
const loading = ref(false)
const adminName = ref('管理员')

const dateLine = computed(() => {
  const d = new Date()
  const week = ['周日', '周一', '周二', '周三', '周四', '周五', '周六'][d.getDay()]
  return `${d.getFullYear()} 年 ${d.getMonth() + 1} 月 ${d.getDate()} 日 · ${week}`
})
const greeting = computed(() => {
  const h = new Date().getHours()
  if (h < 6) return '夜深了'
  if (h < 11) return '早上好'
  if (h < 14) return '中午好'
  if (h < 18) return '下午好'
  return '晚上好'
})
const store_count = computed(() => stats.value.store_count ?? 0)

const primary = computed(() => [
  {
    label: '今日营收', value: `¥${fmt(stats.value.today_revenue)}`,
    icon: Money, accent: 'accent-yellow',
    hint: `本月累计 ¥${fmt(stats.value.month_revenue)}`,
    progress: null, progressHint: '',
  },
  {
    label: '本月核销', value: `¥${fmt(stats.value.month_verify_amount)}`,
    icon: TrendCharts, accent: 'accent-indigo',
    hint: `${stats.value.month_verify_count ?? 0} 笔 · 平均 ¥${avg(stats.value.month_verify_amount, stats.value.month_verify_count)}`,
    progress: null, progressHint: '',
  },
  {
    label: '入座率', value: `${stats.value.occupancy_rate ?? 0}%`,
    icon: PieChart, accent: 'accent-cyan',
    progress: Number(stats.value.occupancy_rate ?? 0),
    progressHint: `${stats.value.active_users ?? 0} 在座 / ${stats.value.total_seats ?? 0} 座位`,
    hint: '',
  },
])

const secondary = computed(() => [
  { label: '本月核销笔数', value: stats.value.month_verify_count ?? 0, icon: Ticket },
  { label: '在座人数',     value: stats.value.active_users ?? 0,       icon: User },
  { label: '今日新增用户', value: stats.value.new_users_today ?? 0,    icon: Plus },
  { label: '可用座位',     value: stats.value.total_seats ?? 0,        icon: Location },
  { label: '营业门店',     value: stats.value.store_count ?? 0,        icon: OfficeBuilding },
])

const todoList = computed(() => [
  { label: '待付款订单', count: todos.value.unpaid_orders ?? 0, link: '/reservations', icon: CreditCard, sub: '预约提交但未支付' },
  { label: '待配置团购', count: todos.value.pending_deal_mappings ?? 0, link: '/deal-mappings', icon: Setting, sub: '缺映射的团购券' },
  { label: '座位不完整门店', count: (todos.value.incomplete_seat_stores || []).length, link: '/seats', icon: OfficeBuilding, sub: '楼层/座位待补' },
  { label: '门锁低电量', count: todos.value.unread_battery_alerts ?? 0, link: '/locks', icon: Bell, sub: '需换电池的锁' },
])

const exports = [
  { path: '/admin/export/reservations', label: '预约订单 CSV', hint: '含用户 · 座位 · 金额 · 状态' },
  { path: '/admin/export/wallet-logs',  label: '钱包流水 CSV', hint: '充值 · 消费 · 退款明细' },
  { path: '/admin/export/study-stats',  label: '学习数据 CSV', hint: '打卡 · 时长 · AI 使用' },
]

const featureMap = [
  { mp: '首页轮播 / 公告', admin: '首页活动 · 消息公告' },
  { mp: '学习订座 / 选座', admin: '价格 · 座位 · 预约订单' },
  { mp: '套餐 Tab / 购卡', admin: '套餐购买 · 价格管理' },
  { mp: '入座 / 开门', admin: '预约订单 · 蓝牙锁' },
  { mp: '团购验券', admin: '团购映射 · 兑换记录' },
  { mp: '我的 · 钱包', admin: '用户管理 · 钱包流水' },
  { mp: '优惠券 / 积分 / 邀请', admin: '优惠券 · 积分 · 邀请' },
  { mp: '学习助手 / 报告', admin: '学习数据 · AI 知识库' },
  { mp: '联系店长（海报二维码）', admin: '首页·运营 → 联系店长' },
]

const revenueSum = computed(() => revenue.value.reduce((s, r) => s + Number(r.revenue || 0), 0))
const revenueOrders = computed(() => revenue.value.reduce((s, r) => s + Number(r.orders || 0), 0))

const chartEl = ref<HTMLElement>()
let chart: echarts.ECharts | null = null
function renderChart() {
  if (!chartEl.value) return
  chart ||= echarts.init(chartEl.value)
  const dates = revenue.value.map(r => shortDate(r.date))
  const values = revenue.value.map(r => Number(r.revenue || 0))
  chart.setOption({
    grid: { top: 20, right: 16, bottom: 26, left: 40 },
    tooltip: {
      trigger: 'axis',
      backgroundColor: '#16171d',
      borderColor: '#16171d',
      textStyle: { color: '#f5f5f7', fontSize: 12 },
      padding: [8, 12],
      formatter: (params: any[]) => {
        const p = params[0]
        const r = revenue.value[p.dataIndex]
        return `<div style="font-weight:600;margin-bottom:4px">${p.axisValue}</div>
                <div>营收 <b style="color:#FFD000">¥${Number(r.revenue).toLocaleString('zh-CN')}</b></div>
                <div style="color:#909096">订单 ${r.orders} 单</div>`
      },
    },
    xAxis: {
      type: 'category', data: dates, boundaryGap: false,
      axisLine: { lineStyle: { color: '#eceef2' } },
      axisLabel: { color: '#8a8b93', fontSize: 11 },
      axisTick: { show: false },
    },
    yAxis: {
      type: 'value',
      splitLine: { lineStyle: { color: '#f2f3f6', type: 'dashed' } },
      axisLabel: { color: '#8a8b93', fontSize: 11, formatter: (v: number) => v >= 1000 ? `${v / 1000}k` : v },
    },
    series: [{
      type: 'line', data: values, smooth: true, symbol: 'circle', symbolSize: 6,
      itemStyle: { color: '#FFD000', borderColor: '#fff', borderWidth: 2 },
      lineStyle: { color: '#FFD000', width: 3, shadowColor: 'rgba(255,208,0,0.4)', shadowBlur: 10, shadowOffsetY: 4 },
      areaStyle: {
        color: {
          type: 'linear', x: 0, y: 0, x2: 0, y2: 1,
          colorStops: [
            { offset: 0, color: 'rgba(255, 208, 0, 0.35)' },
            { offset: 1, color: 'rgba(255, 208, 0, 0.02)' },
          ],
        },
      },
      emphasis: { itemStyle: { borderWidth: 3, shadowBlur: 12, shadowColor: 'rgba(255,208,0,0.6)' } },
    }],
  })
}
watch(revenue, async () => { await nextTick(); renderChart() }, { deep: true })
const onResize = () => chart?.resize()
onMounted(() => window.addEventListener('resize', onResize))
onBeforeUnmount(() => { window.removeEventListener('resize', onResize); chart?.dispose() })

function fmt(v: any) { return Number(v || 0).toLocaleString('zh-CN', { minimumFractionDigits: 0, maximumFractionDigits: 2 }) }
function avg(total: any, count: any) {
  const c = Number(count || 0); if (!c) return '0'
  return (Number(total || 0) / c).toFixed(2)
}
function shortDate(s: string) {
  const [, m, d] = s.split('-'); return `${m}-${d}`
}

async function loadTodos() {
  const res = await http.get('/admin/stats/todos')
  todos.value = res.data
}
async function loadStats() {
  const res = await http.get('/admin/stats')
  stats.value = res.data
}
async function loadRevenue() {
  const res = await http.get('/admin/stats/revenue', { params: { days: 7 } })
  revenue.value = res.data
}
async function refreshAll() {
  loading.value = true
  try { await Promise.all([loadStats(), loadRevenue(), loadTodos()]) }
  finally { loading.value = false }
}

async function downloadExport(path: string) {
  const baseURL = import.meta.env.VITE_API_BASE || '/api'
  const token = localStorage.getItem('admin_token')
  try {
    const res = await fetch(`${baseURL}${path}`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
    if (!res.ok) throw new Error('导出失败')
    const blob = await res.blob()
    const filename = path.split('/').pop() || 'export.csv'
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a'); a.href = url; a.download = filename; a.click()
    URL.revokeObjectURL(url)
    ElMessage.success('导出成功')
  } catch { ElMessage.error('导出失败') }
}

onMounted(refreshAll)
</script>

<style scoped>
.dashboard {
  padding: 4px 8px 24px;
  color: #1f2028;
  font-family: -apple-system, BlinkMacSystemFont, "PingFang SC", "Microsoft YaHei", "Segoe UI", sans-serif;
}
.dashboard > * { animation: rise 0.5s cubic-bezier(0.16, 1, 0.3, 1) both; }
.dashboard > *:nth-child(1) { animation-delay: 0.02s; }
.dashboard > *:nth-child(2) { animation-delay: 0.08s; }
.dashboard > *:nth-child(3) { animation-delay: 0.14s; }
.dashboard > *:nth-child(4) { animation-delay: 0.20s; }
.dashboard > *:nth-child(5) { animation-delay: 0.26s; }
.dashboard > *:nth-child(6) { animation-delay: 0.32s; }
@keyframes rise {
  from { opacity: 0; transform: translateY(10px); }
  to   { opacity: 1; transform: translateY(0); }
}

/* ============ 顶部问候 ============ */
.greet { display: flex; justify-content: space-between; align-items: flex-end; margin-bottom: 24px; gap: 16px; flex-wrap: wrap; }
.greet h1 { margin: 0; font-size: 24px; font-weight: 600; letter-spacing: 0.3px; color: #16171d; }
.greet p  { margin: 6px 0 0; font-size: 13px; color: #8a8b93; letter-spacing: 0.3px; }
.quick { display: flex; align-items: center; gap: 12px; }
.pill {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 6px 12px; border-radius: 999px;
  background: rgba(34, 197, 94, 0.10); border: 1px solid rgba(34, 197, 94, 0.25);
  color: #16a34a; font-size: 12px; letter-spacing: 0.3px; font-weight: 500;
}
.live-dot {
  width: 6px; height: 6px; border-radius: 50%; background: #22c55e;
  box-shadow: 0 0 8px #22c55e;
  animation: pulse 1.6s ease-in-out infinite;
}
@keyframes pulse {
  0%, 100% { opacity: 1; transform: scale(1); }
  50%      { opacity: 0.45; transform: scale(0.85); }
}

/* ============ 主要指标 3 大卡 ============ */
.kpi-primary { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; margin-bottom: 16px; }
.kpi {
  position: relative;
  padding: 22px 24px 20px;
  background: #fff;
  border: 1px solid #eceef2;
  border-radius: 14px;
  box-shadow: 0 1px 2px rgba(20, 22, 30, 0.02);
  transition: transform 0.25s ease, box-shadow 0.25s ease, border-color 0.25s ease;
  overflow: hidden;
}
.kpi:hover { transform: translateY(-2px); box-shadow: 0 12px 32px rgba(20, 22, 30, 0.06); border-color: #dfe2e8; }
.kpi::before {
  content: ''; position: absolute; left: 0; top: 0; width: 3px; height: 100%;
  background: currentColor; opacity: 0.85; border-radius: 3px 0 0 3px;
}
.kpi.accent-yellow { color: #f0a500; }
.kpi.accent-indigo { color: #6366f1; }
.kpi.accent-cyan   { color: #0891b2; }
.kpi-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
.kpi-label { font-size: 13px; color: #6b6c76; font-weight: 500; letter-spacing: 0.3px; }
.kpi-icon {
  width: 34px; height: 34px; border-radius: 10px;
  background: color-mix(in srgb, currentColor 10%, transparent);
  display: flex; align-items: center; justify-content: center;
  font-size: 18px;
}
.kpi-value { font-size: 32px; font-weight: 700; color: #16171d; letter-spacing: -0.5px; line-height: 1.1; font-feature-settings: 'tnum'; }
.kpi-hint { margin-top: 10px; font-size: 12px; color: #8a8b93; letter-spacing: 0.2px; }
.kpi-progress { margin-top: 14px; }
.kpi-progress .bar {
  height: 6px; border-radius: 999px; background: rgba(0,0,0,0.05); overflow: hidden;
}
.kpi-progress .bar i {
  display: block; height: 100%; border-radius: 999px;
  background: currentColor;
  box-shadow: 0 0 12px color-mix(in srgb, currentColor 60%, transparent);
  transition: width 0.6s cubic-bezier(0.16, 1, 0.3, 1);
}
.progress-hint { display: block; margin-top: 6px; font-size: 11.5px; color: #8a8b93; }

/* ============ 次要指标条 ============ */
.kpi-strip {
  display: grid; grid-template-columns: repeat(5, 1fr); gap: 12px; margin-bottom: 16px;
}
.mini {
  display: flex; align-items: center; gap: 12px;
  padding: 14px 16px; background: #fff; border: 1px solid #eceef2; border-radius: 12px;
  transition: border-color 0.2s;
}
.mini:hover { border-color: #dfe2e8; }
.mini-icon {
  width: 36px; height: 36px; border-radius: 10px;
  background: #f5f6f9; color: #6b6c76;
  display: flex; align-items: center; justify-content: center;
  font-size: 16px; flex-shrink: 0;
}
.mini-label { font-size: 12px; color: #8a8b93; letter-spacing: 0.2px; }
.mini-value { font-size: 20px; font-weight: 700; color: #16171d; margin-top: 2px; font-feature-settings: 'tnum'; }

/* ============ 面板通用 ============ */
.panel {
  background: #fff; border: 1px solid #eceef2; border-radius: 14px;
  padding: 20px 24px; margin-bottom: 16px;
}
.panel-head {
  display: flex; justify-content: space-between; align-items: center;
  margin-bottom: 16px;
}
.panel-head h3 { margin: 0; font-size: 15px; font-weight: 600; color: #16171d; letter-spacing: 0.3px; }
.muted { font-size: 12px; color: #8a8b93; }

/* ============ 待办 ============ */
.todos { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; }
.todo {
  display: block; text-decoration: none; color: inherit;
  padding: 16px 18px; border-radius: 12px;
  background: #f9fafb; border: 1px solid transparent;
  transition: all 0.2s ease;
  cursor: pointer;
}
.todo:hover {
  background: #fff; border-color: #dfe2e8;
  transform: translateY(-2px); box-shadow: 0 8px 24px rgba(20, 22, 30, 0.06);
}
.todo.warn {
  background: linear-gradient(135deg, rgba(255, 208, 0, 0.08), rgba(255, 208, 0, 0.02));
  border-color: rgba(240, 165, 0, 0.35);
}
.todo.warn:hover {
  box-shadow: 0 10px 28px rgba(255, 208, 0, 0.18);
  border-color: rgba(240, 165, 0, 0.55);
}
.todo-top { display: flex; align-items: center; gap: 8px; font-size: 13px; color: #6b6c76; }
.todo-top .todo-icon { font-size: 15px; color: #8a8b93; }
.todo.warn .todo-top .todo-icon { color: #f0a500; }
.todo-top .chev { margin-left: auto; font-size: 12px; opacity: 0.4; transition: transform 0.2s, opacity 0.2s; }
.todo:hover .chev { opacity: 1; transform: translateX(3px); }
.todo-value { font-size: 26px; font-weight: 700; color: #16171d; margin-top: 10px; font-feature-settings: 'tnum'; line-height: 1; }
.todo.warn .todo-value { color: #f0a500; }
.todo-sub { margin-top: 6px; font-size: 11.5px; color: #a0a1a9; letter-spacing: 0.2px; }

/* ============ 两栏（营收 + 导出） ============ */
.two-col { display: grid; grid-template-columns: 1.4fr 1fr; gap: 16px; }

/* --- 营收 ECharts --- */
.revenue-chart { width: 100%; height: 260px; }

/* --- 导出 --- */
.exports { display: flex; flex-direction: column; gap: 8px; }
.export-item {
  display: flex; align-items: center; gap: 14px;
  padding: 14px 16px;
  background: #f9fafb; border: 1px solid transparent; border-radius: 12px;
  cursor: pointer; text-align: left; width: 100%;
  transition: all 0.2s ease;
  font-family: inherit;
}
.export-item:hover {
  background: #fff; border-color: #dfe2e8;
  transform: translateX(2px);
  box-shadow: 0 8px 24px rgba(20, 22, 30, 0.06);
}
.export-icon {
  width: 40px; height: 40px; border-radius: 10px;
  background: rgba(255, 208, 0, 0.12);
  color: #f0a500;
  display: flex; align-items: center; justify-content: center;
  font-size: 18px; flex-shrink: 0;
  transition: background 0.2s;
}
.export-item:hover .export-icon { background: rgba(255, 208, 0, 0.22); }
.export-text { flex: 1; min-width: 0; }
.export-text b { display: block; font-size: 14px; color: #16171d; font-weight: 600; margin-bottom: 2px; }
.export-text i { font-style: normal; font-size: 12px; color: #8a8b93; }
.chev { font-size: 12px; color: #b0b1b9; transition: transform 0.2s; }
.export-item:hover .chev { transform: translateX(3px); color: #f0a500; }

/* ============ 折叠面板 ============ */
.collapse-panel {
  background: #fff; border: 1px solid #eceef2; border-radius: 14px;
  padding: 0; margin-top: 16px;
}
.collapse-panel summary {
  display: flex; align-items: center; justify-content: space-between;
  padding: 16px 24px; cursor: pointer; list-style: none;
  transition: background 0.2s;
}
.collapse-panel summary::-webkit-details-marker { display: none; }
.collapse-panel summary:hover { background: #fafbfc; border-radius: 14px; }
.collapse-panel summary b { display: block; font-size: 14px; font-weight: 600; color: #16171d; }
.collapse-panel summary i { display: block; font-style: normal; font-size: 12px; color: #8a8b93; margin-top: 4px; }
.collapse-panel summary .chev { transition: transform 0.25s; font-size: 14px; }
.collapse-panel[open] summary .chev { transform: rotate(180deg); }
.feature-grid {
  padding: 4px 24px 20px;
  display: grid; grid-template-columns: repeat(2, 1fr); gap: 4px 24px;
  border-top: 1px dashed #eceef2;
}
.feature-row {
  display: grid; grid-template-columns: 1fr auto 1fr; gap: 12px; align-items: center;
  padding: 10px 0; font-size: 13px;
  border-bottom: 1px dashed #f0f1f4;
}
.feature-row:last-child, .feature-row:nth-last-child(2) { border-bottom: none; }
.feature-row .mp    { color: #6b6c76; }
.feature-row .admin { color: #16171d; font-weight: 500; }
.feature-row .arrow { font-size: 11px; color: #b0b1b9; }

/* ============ 响应式 ============ */
@media (max-width: 1200px) {
  .kpi-primary { grid-template-columns: 1fr; }
  .kpi-strip { grid-template-columns: repeat(2, 1fr); }
  .todos { grid-template-columns: repeat(2, 1fr); }
  .two-col { grid-template-columns: 1fr; }
  .feature-grid { grid-template-columns: 1fr; }
}
@media (prefers-reduced-motion: reduce) {
  .dashboard > *, .live-dot, .kpi-progress .bar i, .chart-bar { animation: none; transition: none; }
}
</style>
