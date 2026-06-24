<template>
  <el-card>
    <template #header>
      <div class="header">
        <span>座位管理（门店 {{ storeId }}）</span>
        <el-tag type="info">共 {{ list.length }} 座 · 启用 {{ enabledCount }} 座</el-tag>
      </div>
    </template>
    <el-table :data="list" v-loading="loading" stripe>
      <el-table-column prop="seat_code" label="编号" width="90" />
      <el-table-column prop="zone_name" label="区域" width="80" />
      <el-table-column prop="seat_type" label="类型" width="90">
        <template #default="{ row }">
          {{ seatTypeLabel(row.seat_type) }}
        </template>
      </el-table-column>
      <el-table-column label="设施" width="120">
        <template #default="{ row }">
          <el-tag v-if="row.has_outlet" size="small">插座</el-tag>
          <el-tag v-if="row.has_curtain" size="small" type="warning">帘位</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="pos_x" label="X" width="60" />
      <el-table-column prop="pos_y" label="Y" width="60" />
      <el-table-column prop="status" label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="row.status === 1 ? 'success' : 'info'">
            {{ row.status === 1 ? '启用' : '停用' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="120">
        <template #default="{ row }">
          <el-button
            link
            :type="row.status === 1 ? 'danger' : 'success'"
            @click="toggle(row)"
          >
            {{ row.status === 1 ? '停用' : '启用' }}
          </el-button>
        </template>
      </el-table-column>
    </el-table>
  </el-card>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import http from '../api/http'

const list = ref<any[]>([])
const loading = ref(false)
const storeId = 1

const enabledCount = computed(() => list.value.filter((s) => s.status === 1).length)

const seatTypeLabels: Record<string, string> = { standard: '标准', window: '靠窗' }
function seatTypeLabel(t: string) {
  return seatTypeLabels[t] || t
}

async function load() {
  loading.value = true
  try {
    const res = await http.get('/admin/seats', { params: { store_id: storeId } })
    list.value = res.data
  } finally {
    loading.value = false
  }
}

async function toggle(row: any) {
  const status = row.status === 1 ? 0 : 1
  await http.patch(`/admin/seats/${row.id}/status`, null, { params: { status } })
  ElMessage.success(status === 1 ? '已启用' : '已停用')
  load()
}

onMounted(load)
</script>

<style scoped>
.header { display: flex; justify-content: space-between; align-items: center; }
</style>
