<template>
  <el-card>
    <template #header>
      <div class="header-row">
        <span>团购兑换记录</span>
        <div class="right">
          <el-input-number v-model="userId" :min="1" controls-position="right" style="width:120px" />
          <el-select v-model="status" clearable placeholder="状态" style="width:110px; margin-left:8px">
            <el-option label="已核销" value="verified" />
            <el-option label="待处理" value="pending" />
            <el-option label="已退款" value="refunded" />
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
      <el-table-column prop="deal_name" label="商品" min-width="160" />
      <el-table-column prop="coupon_code" label="券码" width="140" />
      <el-table-column prop="deal_type" label="类型" width="100" />
      <el-table-column prop="status" label="状态" width="90">
        <template #default="{ row }">
          <el-tag :type="row.status === 'verified' ? 'success' : 'info'" size="small">{{ row.status }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="verified_at" label="核销时间" width="170" />
      <el-table-column prop="created_at" label="创建时间" width="170" />
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
const status = ref<string | null>(null)

async function load() {
  loading.value = true
  try {
    const params: Record<string, unknown> = { page: page.value, page_size: 20 }
    if (userId.value) params.user_id = userId.value
    if (status.value) params.status = status.value
    const res = await http.get('/admin/exchange-records', { params })
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
