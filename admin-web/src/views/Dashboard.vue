<template>
  <div>
    <el-row :gutter="16" style="margin-bottom:16px">
      <el-col :span="6" v-for="item in cards" :key="item.label">
        <el-card shadow="hover">
          <div class="stat-label">{{ item.label }}</div>
          <div class="stat-value">{{ item.value }}</div>
        </el-card>
      </el-col>
    </el-row>

    <el-card v-if="todos" style="margin-bottom:16px">
      <template #header>
        <div class="todo-header">
          <span>运营待办</span>
          <el-button link type="primary" @click="loadTodos">刷新</el-button>
        </div>
      </template>
      <el-row :gutter="12">
        <el-col :span="6">
          <div class="todo-item" :class="{ warn: todos.unpaid_orders > 0 }" @click="$router.push('/reservations')">
            <div class="todo-label">待付款订单</div>
            <div class="todo-value">{{ todos.unpaid_orders }}</div>
          </div>
        </el-col>
        <el-col :span="6">
          <div class="todo-item" :class="{ warn: todos.pending_deal_mappings > 0 }" @click="$router.push('/deal-mappings')">
            <div class="todo-label">待配置团购</div>
            <div class="todo-value">{{ todos.pending_deal_mappings }}</div>
          </div>
        </el-col>
        <el-col :span="6">
          <div class="todo-item" :class="{ warn: (todos.incomplete_seat_stores || []).length > 0 }" @click="$router.push('/seats')">
            <div class="todo-label">座位不完整门店</div>
            <div class="todo-value">{{ (todos.incomplete_seat_stores || []).length }}</div>
          </div>
        </el-col>
        <el-col :span="6">
          <div class="todo-item" :class="{ warn: todos.unread_battery_alerts > 0 }" @click="$router.push('/locks')">
            <div class="todo-label">门锁低电量</div>
            <div class="todo-value">{{ todos.unread_battery_alerts }}</div>
          </div>
        </el-col>
      </el-row>
    </el-card>

    <el-row :gutter="16">
      <el-col :span="14">
        <el-card>
          <template #header>近7日营收</template>
          <el-table :data="revenue" stripe size="small">
            <el-table-column prop="date" label="日期" />
            <el-table-column prop="revenue" label="营收(元)" />
            <el-table-column prop="orders" label="订单数" />
          </el-table>
        </el-card>
      </el-col>
      <el-col :span="10">
        <el-card>
          <template #header>数据导出</template>
          <div class="export-list">
            <el-button @click="downloadExport('/admin/export/reservations')">导出预约订单 CSV</el-button>
            <el-button @click="downloadExport('/admin/export/wallet-logs')">导出钱包流水 CSV</el-button>
            <el-button @click="downloadExport('/admin/export/study-stats')">导出学习数据 CSV</el-button>
          </div>
        </el-card>
        <el-card style="margin-top:16px">
          <template #header>小程序功能 ↔ 后台入口</template>
          <el-table :data="featureMap" stripe size="small">
            <el-table-column prop="mp" label="小程序" min-width="100" />
            <el-table-column prop="admin" label="后台管理" min-width="120" />
          </el-table>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import http from '../api/http'

const cards = ref<any[]>([])
const revenue = ref<any[]>([])
const todos = ref<any>(null)

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

async function loadTodos() {
  const res = await http.get('/admin/stats/todos')
  todos.value = res.data
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
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    a.click()
    URL.revokeObjectURL(url)
    ElMessage.success('导出成功')
  } catch {
    ElMessage.error('导出失败')
  }
}

onMounted(async () => {
  const res = await http.get('/admin/stats')
  const d = res.data
  cards.value = [
    { label: '今日营收', value: `¥${d.today_revenue}` },
    { label: '本月营收', value: `¥${d.month_revenue}` },
    { label: '在座人数', value: d.active_users },
    { label: '入座率', value: `${d.occupancy_rate}%` },
    { label: '今日新增用户', value: d.new_users_today },
    { label: '营业门店', value: d.store_count },
    { label: '可用座位', value: d.total_seats },
  ]
  const rev = await http.get('/admin/stats/revenue', { params: { days: 7 } })
  revenue.value = rev.data
  await loadTodos()
})
</script>

<style scoped>
.stat-label { color: #888; font-size: 14px; }
.stat-value { font-size: 22px; font-weight: bold; margin-top: 8px; color: #1a1a1a; }
.todo-header { display: flex; justify-content: space-between; align-items: center; }
.todo-item {
  padding: 12px 16px;
  border-radius: 8px;
  background: #f5f7fa;
  cursor: pointer;
  transition: all 0.15s;
}
.todo-item.warn { background: #fdf6ec; box-shadow: inset 0 0 0 1px #e6a23c; }
.todo-label { font-size: 13px; color: #888; }
.todo-value { font-size: 24px; font-weight: 700; margin-top: 4px; }
.export-list { display: flex; flex-direction: column; gap: 10px; align-items: flex-start; }
</style>
