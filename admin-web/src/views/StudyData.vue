<template>
  <div>
    <el-row :gutter="16" style="margin-bottom:16px">
      <el-col :span="6" v-for="item in goalBreakdown" :key="item.key">
        <el-card shadow="hover">
          <div class="stat-label">{{ item.label }}</div>
          <div class="stat-value">{{ item.count }} 人</div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="16" style="margin-bottom:16px">
      <el-col :span="6" v-for="item in cards" :key="item.label">
        <el-card shadow="hover">
          <div class="stat-label">{{ item.label }}</div>
          <div class="stat-value">{{ item.value }}</div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="16">
      <el-col :span="12">
        <el-card>
          <template #header>近 7 日学习时长</template>
          <el-table :data="daily" stripe size="small">
            <el-table-column prop="date" label="日期" />
            <el-table-column prop="minutes" label="分钟" />
            <el-table-column prop="sessions" label="次数" />
          </el-table>
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card>
          <template #header>
            <div class="header-row">
              <span>学习排行榜</span>
              <el-select v-model="days" style="width:110px" @change="loadBoard">
                <el-option label="近7日" :value="7" />
                <el-option label="近30日" :value="30" />
                <el-option label="近90日" :value="90" />
              </el-select>
            </div>
          </template>
          <el-table :data="leaderboard" stripe size="small" max-height="360">
            <el-table-column prop="rank" label="#" width="50" />
            <el-table-column prop="nickname" label="昵称" />
            <el-table-column label="备考" width="70">
              <template #default="{ row }">{{ row.study_goal_label || '—' }}</template>
            </el-table-column>
            <el-table-column prop="title" label="称号" width="70" />
            <el-table-column prop="total_minutes" label="分钟" width="80" />
            <el-table-column prop="session_count" label="次数" width="70" />
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
const goalBreakdown = ref<any[]>([])
const daily = ref<any[]>([])
const leaderboard = ref<any[]>([])
const days = ref(30)

async function loadOverview() {
  const res = await http.get('/admin/study/overview')
  const d = res.data
  cards.value = [
    { label: '累计学习', value: `${d.total_hours} 小时` },
    { label: '学习人次', value: d.total_sessions },
    { label: '学习用户', value: d.learner_count },
    { label: '今日学习', value: `${d.today_minutes} 分钟` },
    { label: '近7日学习', value: `${Math.floor(d.week_minutes / 60)}h${d.week_minutes % 60}m` },
    { label: '近7日活跃', value: d.week_learners },
  ]
  goalBreakdown.value = d.study_goal_breakdown || []
  daily.value = d.daily || []
}

async function loadBoard() {
  const res = await http.get('/admin/study/leaderboard', { params: { days: days.value, limit: 30 } })
  leaderboard.value = res.data
}

onMounted(async () => {
  await loadOverview()
  await loadBoard()
})
</script>

<style scoped>
.stat-label { color: #888; font-size: 14px; }
.stat-value { font-size: 22px; font-weight: bold; margin-top: 8px; color: #1a1a1a; }
.header-row { display: flex; justify-content: space-between; align-items: center; }
</style>
