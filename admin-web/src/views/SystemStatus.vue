<template>
  <div>
    <el-card style="margin-bottom:16px">
      <template #header>
        <div class="header-row">
          <span>系统状态</span>
          <el-tag :type="info.all_ok ? 'success' : 'warning'">
            {{ info.all_ok ? '全部就绪' : '有待配置项' }}
          </el-tag>
        </div>
      </template>
      <el-descriptions :column="2" border>
        <el-descriptions-item label="运行环境">{{ info.app_env }}</el-descriptions-item>
        <el-descriptions-item label="API 地址">{{ info.base_url }}</el-descriptions-item>
        <el-descriptions-item label="审核模式">{{ info.pre_wechat_launch ? '是' : '否' }}</el-descriptions-item>
        <el-descriptions-item label="AppID">{{ info.wx_appid || '-' }}</el-descriptions-item>
      </el-descriptions>
    </el-card>

    <el-card>
      <template #header>集成检查</template>
      <el-table :data="checks" stripe>
        <el-table-column prop="name" label="模块" width="140" />
        <el-table-column prop="detail" label="说明" min-width="260" />
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.ok ? 'success' : 'danger'" size="small">
              {{ row.ok ? '正常' : '待配置' }}
            </el-tag>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import http from '../api/http'

const info = ref<any>({ all_ok: false, checks: [] })
const checks = ref<any[]>([])

onMounted(async () => {
  const res = await http.get('/admin/system/status')
  info.value = res.data
  checks.value = res.data.checks || []
})
</script>

<style scoped>
.header-row { display: flex; justify-content: space-between; align-items: center; }
</style>
