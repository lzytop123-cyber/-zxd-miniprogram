<template>
  <div>
    <el-card style="margin-bottom:16px">
      <template #header>
        <div class="header-row">
          <span>系统状态</span>
          <div class="header-actions">
            <el-button :loading="migrating" @click="runMigrate">检查数据库结构</el-button>
            <el-tag :type="info.all_ok ? 'success' : 'warning'">
              {{ info.all_ok ? '全部就绪' : '有待配置项' }}
            </el-tag>
          </div>
        </div>
      </template>
      <el-descriptions :column="2" border>
        <el-descriptions-item label="运行环境">{{ info.app_env }}</el-descriptions-item>
        <el-descriptions-item label="API 地址">{{ info.base_url }}</el-descriptions-item>
        <el-descriptions-item label="审核模式">{{ info.pre_wechat_launch ? '是' : '否' }}</el-descriptions-item>
        <el-descriptions-item label="AppID">{{ info.wx_appid || '-' }}</el-descriptions-item>
        <el-descriptions-item label="健康告警 Webhook">
          {{ info.health_alert_webhook ? '已配置' : '未配置（设置 HEALTH_ALERT_WEBHOOK）' }}
        </el-descriptions-item>
      </el-descriptions>
    </el-card>

    <el-card v-if="opsTodos" style="margin-bottom:16px">
      <template #header>运营待办</template>
      <el-row :gutter="12">
        <el-col :span="8">
          <div class="todo-item">
            <div class="todo-label">待付款订单</div>
            <div class="todo-val">{{ opsTodos.unpaid_orders || 0 }}</div>
          </div>
        </el-col>
        <el-col :span="8">
          <div class="todo-item">
            <div class="todo-label">待配置团购</div>
            <div class="todo-val">{{ opsTodos.pending_deal_mappings || 0 }}</div>
          </div>
        </el-col>
        <el-col :span="8">
          <div class="todo-item">
            <div class="todo-label">座位不完整门店</div>
            <div class="todo-val">{{ (opsTodos.incomplete_seat_stores || []).length }}</div>
          </div>
        </el-col>
      </el-row>
      <el-alert
        v-for="s in opsTodos.incomplete_seat_stores || []"
        :key="s.store_id"
        type="warning"
        :closable="false"
        show-icon
        class="store-alert"
        :title="`${s.store_name}：${s.actual_count}/${s.expected_count} 座，缺 ${(s.missing_codes || []).join('、')}`"
        description="请前往「座位管理」点击「补全标准座位」。"
      />
      <div v-if="migration" class="migration-box">
        <div class="migration-title">最近数据库升级</div>
        <div>状态：{{ migration.status }} · 回填小时卡 {{ migration.backfill_hours || 0 }} 条</div>
        <div v-if="migration.errors?.length" class="migration-errors">异常：{{ migration.errors.join('；') }}</div>
      </div>
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
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import http from '../api/http'

const info = ref<any>({ all_ok: false, checks: [], ops_todos: {}, migration: {} })
const checks = ref<any[]>([])
const migrating = ref(false)

const opsTodos = computed(() => info.value.ops_todos || {})
const migration = computed(() => info.value.migration || {})

async function load() {
  const res = await http.get('/admin/system/status')
  info.value = res.data
  checks.value = res.data.checks || []
}

async function runMigrate() {
  migrating.value = true
  try {
    const res = await http.post('/admin/system/migrate')
    ElMessage.success(res.message || '完成')
    await load()
  } finally {
    migrating.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.header-row { display: flex; justify-content: space-between; align-items: center; gap: 12px; }
.header-actions { display: flex; align-items: center; gap: 12px; }
.todo-item { padding: 12px 16px; background: #f5f7fa; border-radius: 8px; }
.todo-label { font-size: 13px; color: #888; }
.todo-val { font-size: 24px; font-weight: 700; margin-top: 4px; }
.store-alert { margin-top: 12px; }
.migration-box { margin-top: 16px; padding: 12px 16px; background: #fafafa; border-radius: 8px; font-size: 13px; color: #666; }
.migration-title { font-weight: 700; color: #333; margin-bottom: 4px; }
.migration-errors { color: #c45656; margin-top: 4px; }
</style>
