<template>
  <el-card>
    <template #header>
      <div class="header-row">
        <span>期限卡</span>
        <div class="right">
          <el-input-number v-model="userId" :min="1" placeholder="用户ID" controls-position="right" style="width:120px" />
          <el-select v-model="status" clearable placeholder="状态" style="width:100px; margin-left:8px">
            <el-option label="有效" :value="1" />
            <el-option label="失效" :value="0" />
          </el-select>
          <el-button type="primary" style="margin-left:8px" @click="search">查询</el-button>
        </div>
      </div>
    </template>

    <el-table :data="list" v-loading="loading" stripe>
      <el-table-column prop="id" label="ID" width="60" />
      <el-table-column label="用户" width="120">
        <template #default="{ row }">
          <div>{{ row.user_nickname || '-' }}</div>
          <div class="sub">ID {{ row.user_id }}</div>
        </template>
      </el-table-column>
      <el-table-column prop="card_name" label="卡名称" min-width="140" />
      <el-table-column label="类型" width="100">
        <template #default="{ row }">{{ cardTypeLabel(row.card_type) }}</template>
      </el-table-column>
      <el-table-column label="余量" width="120">
        <template #default="{ row }">
          <span v-if="row.remaining_hours != null">{{ row.remaining_hours }}小时</span>
          <span v-else-if="row.remaining_sessions != null">{{ row.remaining_sessions }}次</span>
          <span v-else>-</span>
        </template>
      </el-table-column>
      <el-table-column label="有效期" width="200">
        <template #default="{ row }">
          {{ row.start_date || '-' }} ~ {{ row.end_date || '-' }}
        </template>
      </el-table-column>
      <el-table-column label="来源" width="90">
        <template #default="{ row }">{{ sourceLabel(row.source) }}</template>
      </el-table-column>
      <el-table-column prop="status" label="状态" width="80">
        <template #default="{ row }">
          <el-tag :type="row.status === 1 ? 'success' : 'info'" size="small">
            {{ row.status === 1 ? '有效' : '失效' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="created_at" label="发放时间" width="170" />
    </el-table>

    <div class="pager">
      <el-pagination v-model:current-page="page" :total="total" layout="total, prev, pager, next" @current-change="load" />
    </div>
  </el-card>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import http from '../api/http'

const list = ref<any[]>([])
const loading = ref(false)
const page = ref(1)
const total = ref(0)
const userId = ref<number | null>(null)
const status = ref<number | null>(null)

const cardTypeMap: Record<string, string> = {
  hourly: '小时卡',
  daily: '天卡',
  weekly: '周卡',
  monthly: '月卡',
  quarterly: '季卡',
  session: '次卡',
  night_monthly: '夜读月卡',
  custom: '自定义',
}

const sourceMap: Record<string, string> = {
  purchase: '在线购买',
  meituan: '美团兑换',
  douyin: '抖音兑换',
  admin: '后台发放',
  gift: '赠送',
}

function cardTypeLabel(v: string) {
  return cardTypeMap[v] || v
}

function sourceLabel(v: string) {
  return sourceMap[v] || v
}

async function load() {
  loading.value = true
  try {
    const params: Record<string, unknown> = { page: page.value, page_size: 20 }
    if (userId.value) params.user_id = userId.value
    if (status.value !== null && status.value !== undefined) params.status = status.value
    const res = await http.get('/admin/period-cards', { params })
    list.value = res.data.items
    total.value = res.data.total
  } finally {
    loading.value = false
  }
}

function search() {
  page.value = 1
  load()
}

onMounted(load)
</script>

<style scoped>
.header-row { display: flex; justify-content: space-between; align-items: center; }
.right { display: flex; align-items: center; }
.sub { font-size: 12px; color: #999; }
.pager { margin-top: 16px; display: flex; justify-content: flex-end; }
</style>
