<template>
  <el-card style="margin-bottom:12px">
    <template #header>
      <div class="header-row">
        <span>核销来源统计</span>
        <el-select v-model="statsDays" style="width:120px" @change="loadStats">
          <el-option label="近 7 天" :value="7" />
          <el-option label="近 30 天" :value="30" />
          <el-option label="近 90 天" :value="90" />
          <el-option label="近 365 天" :value="365" />
        </el-select>
      </div>
    </template>
    <div v-loading="statsLoading" class="stat-grid">
      <div class="stat-tile meituan">
        <div class="stat-label">美团（含大众点评）</div>
        <div class="stat-amt">¥{{ stats.meituan?.amount ?? 0 }}</div>
        <div class="stat-sub">
          {{ stats.meituan?.count ?? 0 }} 笔
          <span v-if="stats.meituan?.refund_amount" class="refund-tag">退 ¥{{ stats.meituan.refund_amount }}</span>
        </div>
      </div>
      <div class="stat-tile douyin">
        <div class="stat-label">抖音</div>
        <div class="stat-amt">¥{{ stats.douyin?.amount ?? 0 }}</div>
        <div class="stat-sub">
          {{ stats.douyin?.count ?? 0 }} 笔
          <span v-if="stats.douyin?.refund_amount" class="refund-tag">退 ¥{{ stats.douyin.refund_amount }}</span>
        </div>
      </div>
      <div class="stat-tile wechat">
        <div class="stat-label">
          微信支付
          <el-tooltip v-if="stats.wechat_pay?.detail" placement="top">
            <template #content>
              <div>买卡 ¥{{ stats.wechat_pay.detail.card_purchase.amount }}（{{ stats.wechat_pay.detail.card_purchase.count }} 笔，退 ¥{{ stats.wechat_pay.detail.card_purchase.refund_amount }}）</div>
              <div>预约 ¥{{ stats.wechat_pay.detail.reservation.amount }}（{{ stats.wechat_pay.detail.reservation.count }} 笔，退 ¥{{ stats.wechat_pay.detail.reservation.refund_amount }}）</div>
              <div>充值 ¥{{ stats.wechat_pay.detail.recharge.amount }}（{{ stats.wechat_pay.detail.recharge.count }} 笔，退 ¥{{ stats.wechat_pay.detail.recharge.refund_amount }}）</div>
            </template>
            <el-icon style="vertical-align:middle;color:#999"><QuestionFilled /></el-icon>
          </el-tooltip>
        </div>
        <div class="stat-amt">¥{{ stats.wechat_pay?.amount ?? 0 }}</div>
        <div class="stat-sub">
          {{ stats.wechat_pay?.count ?? 0 }} 笔
          <span v-if="stats.wechat_pay?.refund_amount" class="refund-tag">退 ¥{{ stats.wechat_pay.refund_amount }}</span>
        </div>
      </div>
      <div class="stat-tile refund">
        <div class="stat-label">退款合计</div>
        <div class="stat-amt">¥{{ stats.refund?.amount ?? 0 }}</div>
        <div class="stat-sub">{{ stats.refund?.count ?? 0 }} 笔</div>
      </div>
      <div class="stat-tile total">
        <div class="stat-label">净收入（收入 − 退款）</div>
        <div class="stat-amt">¥{{ stats.total?.amount ?? 0 }}</div>
        <div class="stat-sub">毛收入 ¥{{ stats.total?.gross ?? 0 }}</div>
      </div>
    </div>
  </el-card>

  <el-card>
    <template #header>
      <div class="header-row">
        <div class="title-block">
          <span>团购兑换记录</span>
          <span class="month-sum">本月核销 ¥{{ monthAmount }}（{{ monthCount }} 笔）</span>
        </div>
        <div class="right">
          <el-input-number v-model="userId" :min="1" controls-position="right" style="width:120px" />
          <el-select v-model="status" clearable placeholder="状态" style="width:110px; margin-left:8px">
            <el-option label="已核销" value="verified" />
            <el-option label="待处理" value="pending" />
            <el-option label="已退款" value="refunded" />
          </el-select>
          <el-button style="margin-left:8px" @click="backfillPrices" :loading="backfilling">回填金额</el-button>
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
      <el-table-column label="返回价" width="100">
        <template #default="{ row }">
          <span v-if="row.deal_price != null">¥{{ row.deal_price }}</span>
          <span v-else class="sub">—</span>
        </template>
      </el-table-column>
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
import { ElMessage } from 'element-plus'
import { QuestionFilled } from '@element-plus/icons-vue'
import http from '../api/http'

const list = ref<any[]>([])
const loading = ref(false)
const page = ref(1)
const total = ref(0)
const userId = ref<number | null>(null)
const status = ref<string | null>(null)
const monthAmount = ref(0)
const monthCount = ref(0)
const backfilling = ref(false)
const statsDays = ref(30)
const stats = ref<any>({})
const statsLoading = ref(false)

async function loadStats() {
  statsLoading.value = true
  try {
    const res = await http.get('/admin/stats/verify-by-source', { params: { days: statsDays.value } })
    stats.value = res.data || {}
  } finally {
    statsLoading.value = false
  }
}

async function load() {
  loading.value = true
  try {
    const params: Record<string, unknown> = { page: page.value, page_size: 20 }
    if (userId.value) params.user_id = userId.value
    if (status.value) params.status = status.value
    const res = await http.get('/admin/exchange-records', { params })
    list.value = res.data.items
    total.value = res.data.total
    monthAmount.value = res.data.month_verify_amount ?? 0
    monthCount.value = res.data.month_verify_count ?? 0
  } finally {
    loading.value = false
  }
}

async function backfillPrices() {
  backfilling.value = true
  try {
    const res = await http.post('/admin/exchange-records/backfill-prices')
    ElMessage.success(res.message || '回填完成')
    await load()
  } catch (e: any) {
    ElMessage.error(e?.message || '回填失败')
  } finally {
    backfilling.value = false
  }
}

function search() {
  page.value = 1
  load()
}

onMounted(() => {
  load()
  loadStats()
})
</script>

<style scoped>
.header-row { display: flex; justify-content: space-between; align-items: center; gap: 12px; flex-wrap: wrap; }
.title-block { display: flex; align-items: baseline; gap: 12px; }
.month-sum { font-size: 13px; color: #67c23a; font-weight: 600; }
.right { display: flex; align-items: center; }
.sub { font-size: 12px; color: #999; }
.pager { margin-top: 16px; display: flex; justify-content: flex-end; }
.stat-grid { display: grid; grid-template-columns: repeat(5, 1fr); gap: 12px; }
.stat-tile { padding: 14px 16px; border-radius: 8px; background: #f5f7fa; border-left: 4px solid #dcdfe6; }
.stat-tile.meituan { border-left-color: #ffd100; }
.stat-tile.douyin { border-left-color: #000; }
.stat-tile.wechat { border-left-color: #07c160; }
.stat-tile.refund { border-left-color: #f56c6c; background: #fef0f0; }
.stat-tile.total { border-left-color: #409eff; background: #ecf5ff; }
.stat-label { font-size: 13px; color: #606266; margin-bottom: 6px; }
.stat-amt { font-size: 22px; font-weight: 700; color: #303133; }
.stat-tile.refund .stat-amt { color: #f56c6c; }
.stat-tile.total .stat-amt { color: #409eff; }
.stat-sub { font-size: 12px; color: #909399; margin-top: 2px; }
.refund-tag { color: #f56c6c; margin-left: 6px; }
</style>
