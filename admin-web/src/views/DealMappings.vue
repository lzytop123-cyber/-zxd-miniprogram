<template>
  <el-card>
    <template #header>
      <div class="header-row">
        <span>美团团购映射</span>
        <el-button type="primary" @click="openAdd()">新增映射</el-button>
      </div>
    </template>

    <el-alert
      v-if="pendingList.length"
      type="warning"
      :closable="false"
      show-icon
      title="有待配置的团购"
      :description="`共 ${pendingList.length} 条：用户兑换时验券成功但缺映射，券未被核销，配置后让用户重试即可。`"
      class="pending-alert"
    />

    <el-table v-if="pendingList.length" :data="pendingList" stripe class="pending-table">
      <el-table-column prop="deal_id" label="Deal ID" width="130" />
      <el-table-column prop="deal_name" label="团购名称" min-width="180" />
      <el-table-column label="建议权益" width="160">
        <template #default="{ row }">
          {{ row.suggested_reward_type }} / {{ row.suggested_reward_value }}
        </template>
      </el-table-column>
      <el-table-column prop="hit_count" label="触发次数" width="90" />
      <el-table-column prop="last_coupon_code" label="最近券码" width="140" />
      <el-table-column label="操作" width="160" fixed="right">
        <template #default="{ row }">
          <el-button type="primary" link @click="openResolve(row)">一键配置</el-button>
          <el-button type="info" link @click="dismiss(row)">忽略</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-divider v-if="pendingList.length" />

    <el-table :data="list" v-loading="loading" stripe>
      <el-table-column prop="deal_id" label="Deal ID" width="130" />
      <el-table-column prop="deal_name" label="商品名称" />
      <el-table-column prop="reward_type" label="权益类型" width="120" />
      <el-table-column prop="reward_value" label="数值" width="80" />
      <el-table-column prop="is_active" label="状态" width="80">
        <template #default="{ row }">
          <el-tag :type="row.is_active ? 'success' : 'info'">{{ row.is_active ? '启用' : '停用' }}</el-tag>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="showAdd" :title="dialogTitle" width="480px">
      <el-form :model="form" label-width="100px">
        <el-form-item label="Deal ID"><el-input v-model="form.deal_id" :disabled="!!resolveId" /></el-form-item>
        <el-form-item label="商品名称"><el-input v-model="form.deal_name" /></el-form-item>
        <el-form-item label="权益类型">
          <el-select v-model="form.reward_type" style="width:100%">
            <el-option v-for="t in rewardTypes" :key="t" :label="t" :value="t" />
          </el-select>
        </el-form-item>
        <el-form-item label="数值"><el-input-number v-model="form.reward_value" :min="1" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showAdd = false">取消</el-button>
        <el-button type="primary" @click="submit">保存</el-button>
      </template>
    </el-dialog>
  </el-card>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import http from '../api/http'

const list = ref<any[]>([])
const pendingList = ref<any[]>([])
const loading = ref(false)
const showAdd = ref(false)
const resolveId = ref<number | null>(null)
const rewardTypes = ['hours', 'day_pass', 'week_pass', 'month_pass', 'quarter_pass', 'night_monthly', 'session']
const form = reactive({
  deal_id: '',
  deal_name: '',
  reward_type: 'hours',
  reward_value: 4,
  store_id: 1,
})

const dialogTitle = computed(() => (resolveId.value ? '配置待处理团购' : '新增团购映射'))

async function load() {
  loading.value = true
  try {
    const [mappings, pending] = await Promise.all([
      http.get('/admin/deal-mappings'),
      http.get('/admin/deal-mappings/pending'),
    ])
    list.value = mappings.data
    pendingList.value = pending.data
  } finally {
    loading.value = false
  }
}

function openAdd() {
  resolveId.value = null
  form.deal_id = ''
  form.deal_name = ''
  form.reward_type = 'hours'
  form.reward_value = 4
  showAdd.value = true
}

function openResolve(row: any) {
  resolveId.value = row.id
  form.deal_id = row.deal_id
  form.deal_name = row.deal_name || ''
  form.reward_type = row.suggested_reward_type || 'day_pass'
  form.reward_value = row.suggested_reward_value || 1
  showAdd.value = true
}

async function submit() {
  if (resolveId.value) {
    await http.post(`/admin/deal-mappings/pending/${resolveId.value}/resolve`, {
      store_id: form.store_id,
      deal_name: form.deal_name,
      reward_type: form.reward_type,
      reward_value: form.reward_value,
    })
    ElMessage.success('已配置，可让用户重新兑换')
  } else {
    await http.post('/admin/deal-mappings', form)
    ElMessage.success('已添加')
  }
  showAdd.value = false
  resolveId.value = null
  load()
}

async function dismiss(row: any) {
  await http.post(`/admin/deal-mappings/pending/${row.id}/dismiss`)
  ElMessage.success('已忽略')
  load()
}

onMounted(load)
</script>

<style scoped>
.header-row { display: flex; justify-content: space-between; align-items: center; }
.pending-alert { margin-bottom: 16px; }
.pending-table { margin-bottom: 8px; }
</style>
