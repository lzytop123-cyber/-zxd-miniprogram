<template>
  <el-card>
    <template #header>
      <div class="header-row">
        <span>开门记录</span>
        <el-button @click="load">刷新</el-button>
      </div>
    </template>

    <el-form inline class="filters" @submit.prevent>
      <el-form-item label="门锁">
        <el-select v-model="filters.lock_id" clearable placeholder="全部" style="width:140px">
          <el-option v-for="l in locks" :key="l.id" :label="l.lock_name || `锁#${l.id}`" :value="l.id" />
        </el-select>
      </el-form-item>
      <el-form-item label="结果">
        <el-select v-model="filters.result" clearable placeholder="全部" style="width:110px">
          <el-option label="成功" :value="1" />
          <el-option label="失败" :value="0" />
        </el-select>
      </el-form-item>
      <el-form-item label="日期">
        <el-date-picker
          v-model="dateRange"
          type="daterange"
          value-format="YYYY-MM-DD"
          start-placeholder="开始"
          end-placeholder="结束"
          style="width:240px"
        />
      </el-form-item>
      <el-form-item>
        <el-button type="primary" @click="search">查询</el-button>
        <el-button @click="reset">重置</el-button>
      </el-form-item>
    </el-form>

    <el-table :data="list" v-loading="loading" stripe>
      <el-table-column prop="opened_at" label="时间" width="170" />
      <el-table-column label="门锁" width="100">
        <template #default="{ row }">{{ row.lock_name || '-' }}</template>
      </el-table-column>
      <el-table-column label="用户" width="130">
        <template #default="{ row }">
          <div>{{ row.user_nickname || '-' }}</div>
          <div class="sub">{{ row.user_phone || (row.user_id ? `ID ${row.user_id}` : '-') }}</div>
        </template>
      </el-table-column>
      <el-table-column label="订单号" min-width="160" show-overflow-tooltip>
        <template #default="{ row }">{{ row.order_no || '-' }}</template>
      </el-table-column>
      <el-table-column label="方式" width="90">
        <template #default="{ row }">{{ row.open_type_label || row.open_type || '-' }}</template>
      </el-table-column>
      <el-table-column label="结果" width="90">
        <template #default="{ row }">
          <el-tag :type="row.result === 1 ? 'success' : 'danger'" size="small">
            {{ row.result === 1 ? '成功' : '失败' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="fail_reason" label="失败原因" min-width="160" show-overflow-tooltip />
    </el-table>

    <div class="pager">
      <el-pagination
        v-model:current-page="page"
        :page-size="pageSize"
        :total="total"
        layout="total, prev, pager, next"
        @current-change="load"
      />
    </div>
  </el-card>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import http from '../api/http'

const list = ref<any[]>([])
const locks = ref<any[]>([])
const loading = ref(false)
const page = ref(1)
const pageSize = 20
const total = ref(0)
const dateRange = ref<[string, string] | null>(null)

const filters = reactive<{
  lock_id: number | null
  result: number | null
}>({
  lock_id: null,
  result: null,
})

async function loadLocks() {
  const res = await http.get('/admin/locks')
  locks.value = res.data || []
}

async function load() {
  loading.value = true
  try {
    const params: Record<string, unknown> = { page: page.value, page_size: pageSize }
    if (filters.lock_id != null) params.lock_id = filters.lock_id
    if (filters.result != null) params.result = filters.result
    if (dateRange.value?.[0]) params.date_from = dateRange.value[0]
    if (dateRange.value?.[1]) params.date_to = dateRange.value[1]
    const res = await http.get('/admin/door-logs', { params })
    list.value = res.data.items || []
    total.value = res.data.total || 0
  } finally {
    loading.value = false
  }
}

function search() {
  page.value = 1
  load()
}

function reset() {
  filters.lock_id = null
  filters.result = null
  dateRange.value = null
  page.value = 1
  load()
}

onMounted(async () => {
  await loadLocks()
  await load()
})
</script>

<style scoped>
.header-row { display: flex; justify-content: space-between; align-items: center; }
.filters { margin-bottom: 8px; }
.sub { font-size: 12px; color: #999; }
.pager { margin-top: 16px; display: flex; justify-content: flex-end; }
</style>
