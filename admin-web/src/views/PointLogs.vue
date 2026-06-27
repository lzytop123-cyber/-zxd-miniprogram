<template>
  <el-card>
    <template #header>
      <div class="header-row">
        <span>积分流水</span>
        <div class="right">
          <el-input-number v-model="userId" :min="1" controls-position="right" style="width:120px" />
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
      <el-table-column prop="type_label" label="类型" width="100" />
      <el-table-column prop="points" label="积分" width="80">
        <template #default="{ row }">
          <span class="plus">+{{ row.points }}</span>
        </template>
      </el-table-column>
      <el-table-column prop="remark" label="备注" min-width="180" />
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

const list = ref<any[]>([])
const loading = ref(false)
const page = ref(1)
const total = ref(0)
const userId = ref<number | null>(null)

async function load() {
  loading.value = true
  try {
    const params: Record<string, unknown> = { page: page.value, page_size: 20 }
    if (userId.value) params.user_id = userId.value
    const res = await http.get('/admin/point-logs', { params })
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
.plus { color: #52B788; font-weight: 600; }
</style>
