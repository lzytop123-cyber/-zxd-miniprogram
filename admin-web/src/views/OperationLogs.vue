<template>
  <el-card>
    <template #header>
      <div class="header-row">
        <span>操作日志</span>
        <el-input v-model="action" placeholder="按动作筛选" clearable style="width:200px" @keyup.enter="search">
          <template #append>
            <el-button @click="search">搜索</el-button>
          </template>
        </el-input>
      </div>
    </template>

    <el-table :data="list" v-loading="loading" stripe>
      <el-table-column prop="created_at" label="时间" width="170" />
      <el-table-column prop="admin_username" label="管理员" width="100" />
      <el-table-column prop="action" label="动作" width="160" />
      <el-table-column prop="target_type" label="对象类型" width="100" />
      <el-table-column prop="target_id" label="对象ID" width="120" />
      <el-table-column prop="detail" label="详情" min-width="200" show-overflow-tooltip />
    </el-table>

    <div class="pager">
      <el-pagination
        v-model:current-page="page"
        :total="total"
        layout="total, prev, pager, next"
        @current-change="load"
      />
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
const action = ref('')

async function load() {
  loading.value = true
  try {
    const params: Record<string, unknown> = { page: page.value, page_size: 20 }
    if (action.value.trim()) params.action = action.value.trim()
    const res = await http.get('/admin/operation-logs', { params })
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
.pager { margin-top: 16px; display: flex; justify-content: flex-end; }
</style>
