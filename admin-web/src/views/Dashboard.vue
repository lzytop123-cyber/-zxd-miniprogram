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

    <el-card>
      <template #header>近7日营收</template>
      <el-table :data="revenue" stripe size="small">
        <el-table-column prop="date" label="日期" />
        <el-table-column prop="revenue" label="营收(元)" />
        <el-table-column prop="orders" label="订单数" />
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import http from '../api/http'

const cards = ref<any[]>([])
const revenue = ref<any[]>([])

onMounted(async () => {
  const res = await http.get('/admin/stats')
  const d = res.data
  cards.value = [
    { label: '今日营收', value: `¥${d.today_revenue}` },
    { label: '本月营收', value: `¥${d.month_revenue}` },
    { label: '入住率', value: `${d.occupancy_rate}%` },
    { label: '今日新增用户', value: d.new_users_today },
  ]
  const rev = await http.get('/admin/stats/revenue', { params: { days: 7 } })
  revenue.value = rev.data
})
</script>

<style scoped>
.stat-label { color: #888; font-size: 14px; }
.stat-value { font-size: 22px; font-weight: bold; margin-top: 8px; color: #1a1a1a; }
</style>
