<template>
  <div>
    <el-card style="margin-bottom:16px">
      <template #header>
        <div class="header-row">
          <span>AI 使用统计</span>
          <div class="right">
            <el-date-picker
              v-model="statDate"
              type="date"
              value-format="YYYY-MM-DD"
              placeholder="选择日期"
              style="width:160px"
            />
            <el-input-number
              v-model="userId"
              :min="1"
              controls-position="right"
              placeholder="用户ID"
              style="width:120px; margin-left:8px"
            />
            <el-button type="primary" style="margin-left:8px" @click="search">查询</el-button>
          </div>
        </div>
      </template>

      <el-row :gutter="16" style="margin-bottom:8px">
        <el-col :span="8">
          <div class="stat-label">当日使用人数</div>
          <div class="stat-value">{{ summary.user_count }}</div>
        </el-col>
        <el-col :span="8">
          <div class="stat-label">当日提问次数</div>
          <div class="stat-value">{{ summary.chat_total }}</div>
        </el-col>
        <el-col :span="8">
          <div class="stat-label">统计日期</div>
          <div class="stat-value date">{{ summary.stat_date || '-' }}</div>
        </el-col>
      </el-row>
    </el-card>

    <el-card style="margin-bottom:16px">
      <template #header>当日用户汇总</template>
      <el-table :data="dailyList" v-loading="dailyLoading" stripe>
        <el-table-column label="用户" width="160">
          <template #default="{ row }">
            <div>{{ row.user_nickname || '-' }}</div>
            <div class="sub">ID {{ row.user_id }}</div>
          </template>
        </el-table-column>
        <el-table-column prop="user_phone" label="手机号" width="130">
          <template #default="{ row }">{{ row.user_phone || '-' }}</template>
        </el-table-column>
        <el-table-column prop="chat_count" label="提问次数" width="100" />
        <el-table-column prop="last_used_at" label="最后使用" width="180" />
        <el-table-column label="操作" width="100">
          <template #default="{ row }">
            <el-button link type="primary" @click="filterUser(row.user_id)">看明细</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-card>
      <template #header>问答明细</template>
      <el-table :data="logList" v-loading="logLoading" stripe>
        <el-table-column label="用户" width="140">
          <template #default="{ row }">
            <div>{{ row.user_nickname || '-' }}</div>
            <div class="sub">ID {{ row.user_id }}</div>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="时间" width="170" />
        <el-table-column label="问题" min-width="180">
          <template #default="{ row }">
            <div class="clamp">{{ row.question }}</div>
          </template>
        </el-table-column>
        <el-table-column label="回复" min-width="220">
          <template #default="{ row }">
            <div class="clamp">{{ row.reply }}</div>
          </template>
        </el-table-column>
        <el-table-column label="详情" width="80">
          <template #default="{ row }">
            <el-button link type="primary" @click="showDetail(row)">查看</el-button>
          </template>
        </el-table-column>
      </el-table>
      <div class="pager">
        <el-pagination
          v-model:current-page="logPage"
          :total="logTotal"
          layout="total, prev, pager, next"
          @current-change="loadLogs"
        />
      </div>
    </el-card>

    <el-dialog v-model="detailVisible" title="问答详情" width="640px">
      <div class="detail-block">
        <div class="detail-label">用户</div>
        <div>{{ detail?.user_nickname || '-' }}（ID {{ detail?.user_id }}）</div>
      </div>
      <div class="detail-block">
        <div class="detail-label">时间</div>
        <div>{{ detail?.created_at || '-' }}</div>
      </div>
      <div class="detail-block">
        <div class="detail-label">问题</div>
        <pre class="detail-text">{{ detail?.question }}</pre>
      </div>
      <div class="detail-block">
        <div class="detail-label">回复</div>
        <pre class="detail-text">{{ detail?.reply }}</pre>
      </div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import http from '../api/http'

function todayStr() {
  const d = new Date()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${d.getFullYear()}-${m}-${day}`
}

const statDate = ref(todayStr())
const userId = ref<number | null>(null)

const summary = reactive({
  stat_date: '',
  user_count: 0,
  chat_total: 0,
})
const dailyList = ref<any[]>([])
const dailyLoading = ref(false)

const logList = ref<any[]>([])
const logLoading = ref(false)
const logPage = ref(1)
const logTotal = ref(0)

const detailVisible = ref(false)
const detail = ref<any>(null)

async function loadDaily() {
  dailyLoading.value = true
  try {
    const res = await http.get('/admin/assistant/usage/daily', {
      params: { stat_date: statDate.value, page: 1, page_size: 100 },
    })
    const data = res.data || {}
    summary.stat_date = data.stat_date || statDate.value
    summary.user_count = data.user_count || 0
    summary.chat_total = data.chat_total || 0
    dailyList.value = data.items || []
  } finally {
    dailyLoading.value = false
  }
}

async function loadLogs() {
  logLoading.value = true
  try {
    const params: Record<string, unknown> = {
      page: logPage.value,
      page_size: 20,
      stat_date: statDate.value,
    }
    if (userId.value) params.user_id = userId.value
    const res = await http.get('/admin/assistant/chat-logs', { params })
    logList.value = res.data.items || []
    logTotal.value = res.data.total || 0
  } finally {
    logLoading.value = false
  }
}

function search() {
  logPage.value = 1
  loadDaily()
  loadLogs()
}

function filterUser(id: number) {
  userId.value = id
  search()
}

function showDetail(row: any) {
  detail.value = row
  detailVisible.value = true
}

onMounted(search)
</script>

<style scoped>
.header-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.right {
  display: flex;
  align-items: center;
}
.stat-label {
  color: #888;
  font-size: 13px;
}
.stat-value {
  font-size: 28px;
  font-weight: 700;
  margin-top: 4px;
}
.stat-value.date {
  font-size: 20px;
}
.sub {
  color: #999;
  font-size: 12px;
}
.clamp {
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
  white-space: pre-wrap;
  word-break: break-word;
  line-height: 1.4;
}
.pager {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}
.detail-block {
  margin-bottom: 16px;
}
.detail-label {
  color: #888;
  font-size: 12px;
  margin-bottom: 4px;
}
.detail-text {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
  background: #f6f7f9;
  padding: 12px;
  border-radius: 8px;
  font-family: inherit;
  font-size: 13px;
  line-height: 1.5;
  max-height: 280px;
  overflow: auto;
}
</style>
