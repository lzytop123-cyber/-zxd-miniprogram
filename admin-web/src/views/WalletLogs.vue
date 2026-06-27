<template>
  <el-card>
    <template #header>
      <div class="header-row">
        <span>钱包流水</span>
        <div class="right">
          <el-input-number v-model="userId" :min="1" controls-position="right" style="width:120px" />
          <el-select v-model="logType" clearable placeholder="类型" style="width:110px; margin-left:8px">
            <el-option label="充值" value="recharge" />
            <el-option label="消费" value="consume" />
            <el-option label="退款" value="refund" />
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
      <el-table-column prop="type" label="类型" width="90">
        <template #default="{ row }">{{ typeLabel(row.type) }}</template>
      </el-table-column>
      <el-table-column prop="amount" label="金额" width="90">
        <template #default="{ row }">
          <span :class="row.type === 'consume' ? 'minus' : 'plus'">
            {{ row.type === 'consume' ? '-' : '+' }}¥{{ row.amount }}
          </span>
        </template>
      </el-table-column>
      <el-table-column prop="balance_after" label="余额后" width="90">
        <template #default="{ row }">¥{{ row.balance_after }}</template>
      </el-table-column>
      <el-table-column prop="remark" label="备注" min-width="160" />
      <el-table-column prop="ref_order" label="关联订单" width="160" />
      <el-table-column prop="created_at" label="时间" width="170" />
    </el-table>

    <div class="pager">
      <el-pagination v-model:current-page="page" :total="total" layout="total, prev, pager, next" @current-change="load" />
    </div>
  </el-card>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import http from '../api/http'

const typeMap: Record<string, string> = { recharge: '充值', consume: '消费', refund: '退款' }
function typeLabel(v: string) { return typeMap[v] || v }

const list = ref<any[]>([])
const loading = ref(false)
const page = ref(1)
const total = ref(0)
const userId = ref<number | null>(null)
const logType = ref<string | null>(null)

async function load() {
  loading.value = true
  try {
    const params: Record<string, unknown> = { page: page.value, page_size: 20 }
    if (userId.value) params.user_id = userId.value
    if (logType.value) params.log_type = logType.value
    const res = await http.get('/admin/wallet-logs', { params })
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
.plus { color: #52B788; }
.minus { color: #E74C3C; }
</style>
