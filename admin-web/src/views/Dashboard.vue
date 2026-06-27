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
import http from '../api/http'

const cards = ref<any[]>([])
const revenue = ref<any[]>([])

const featureMap = [
  { mp: '首页轮播', admin: '首页活动' },
  { mp: '学习订座 / 选座', admin: '价格 · 座位 · 预约订单' },
  { mp: '套餐 Tab / 购卡', admin: '套餐购买 · 价格管理' },
  { mp: '入座 / 开门', admin: '预约订单 · 蓝牙锁' },
  { mp: '团购验券', admin: '团购映射 · 兑换记录' },
  { mp: '我的 · 钱包', admin: '用户管理 · 钱包流水' },
  { mp: '优惠券 / 积分 / 邀请', admin: '优惠券 · 积分 · 邀请' },
  { mp: '学习助手 / 报告', admin: '学习数据 · AI 知识库' },
  { mp: '联系店长（客服）', admin: '微信公众平台客服（非本后台）' },
]

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
})
</script>

<style scoped>
.stat-label { color: #888; font-size: 14px; }
.stat-value { font-size: 22px; font-weight: bold; margin-top: 8px; color: #1a1a1a; }
</style>
