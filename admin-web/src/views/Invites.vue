<template>
  <div>
    <el-row :gutter="16" style="margin-bottom:16px">
      <el-col :span="12">
        <el-card shadow="hover">
          <div class="stat-label">累计邀请成功</div>
          <div class="stat-value">{{ stats.total_invites }}</div>
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card shadow="hover">
          <div class="stat-label">有邀请记录的用户</div>
          <div class="stat-value">{{ stats.inviter_count }}</div>
        </el-card>
      </el-col>
    </el-row>

    <el-card>
      <template #header>邀请记录</template>
      <el-table :data="list" v-loading="loading" stripe>
        <el-table-column label="被邀请人" min-width="120">
          <template #default="{ row }">
            <div>{{ row.nickname || '-' }}</div>
            <div class="sub">ID {{ row.user_id }}</div>
          </template>
        </el-table-column>
        <el-table-column prop="phone" label="手机" width="130" />
        <el-table-column label="邀请人" min-width="120">
          <template #default="{ row }">
            <div>{{ row.inviter_nickname || '-' }}</div>
            <div class="sub">{{ row.inviter_code }}</div>
          </template>
        </el-table-column>
        <el-table-column prop="invited_at" label="注册时间" width="170" />
      </el-table>
      <div class="pager">
        <el-pagination v-model:current-page="page" :total="total" layout="total, prev, pager, next" @current-change="load" />
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import http from '../api/http'

const list = ref<any[]>([])
const stats = ref({ total_invites: 0, inviter_count: 0 })
const loading = ref(false)
const page = ref(1)
const total = ref(0)

async function load() {
  loading.value = true
  try {
    const res = await http.get('/admin/invites', { params: { page: page.value, page_size: 20 } })
    list.value = res.data.items
    stats.value = res.data.stats
    total.value = res.data.total
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.stat-label { color: #888; font-size: 14px; }
.stat-value { font-size: 28px; font-weight: bold; margin-top: 8px; }
.sub { font-size: 12px; color: #999; }
.pager { margin-top: 16px; display: flex; justify-content: flex-end; }
</style>
