<template>
  <el-card>
    <template #header>
      <div class="header-row">
        <span>套餐购买订单</span>
        <el-button @click="load">刷新</el-button>
      </div>
    </template>

    <el-form inline class="filters">
      <el-form-item label="订单号">
        <el-input v-model="filters.order_no" placeholder="CRD 开头" clearable style="width:160px" />
      </el-form-item>
      <el-form-item label="用户ID">
        <el-input-number v-model="filters.user_id" :min="1" controls-position="right" style="width:120px" />
      </el-form-item>
      <el-form-item label="支付">
        <el-select v-model="filters.pay_status" clearable placeholder="全部" style="width:110px">
          <el-option label="待付款" :value="0" />
          <el-option label="已付款" :value="1" />
        </el-select>
      </el-form-item>
      <el-form-item>
        <el-button type="primary" @click="search">查询</el-button>
        <el-button @click="reset">重置</el-button>
      </el-form-item>
    </el-form>

    <el-table :data="list" v-loading="loading" stripe>
      <el-table-column prop="order_no" label="订单号" width="200" />
      <el-table-column label="用户" width="120">
        <template #default="{ row }">
          <div>{{ row.user_nickname || '-' }}</div>
          <div class="sub">ID {{ row.user_id }}</div>
        </template>
      </el-table-column>
      <el-table-column prop="store_name" label="门店" width="140" />
      <el-table-column prop="bill_type_label" label="套餐" width="100" />
      <el-table-column prop="amount" label="金额" width="80">
        <template #default="{ row }">¥{{ row.amount }}</template>
      </el-table-column>
      <el-table-column prop="pay_type" label="支付方式" width="100">
        <template #default="{ row }">{{ payTypeLabel(row.pay_type) }}</template>
      </el-table-column>
      <el-table-column prop="pay_status" label="支付" width="90">
        <template #default="{ row }">
          <el-tag :type="row.pay_status === 1 ? 'success' : 'warning'" size="small">
            {{ row.pay_status === 1 ? '已付款' : '待付款' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="card_name" label="发放卡" min-width="160" show-overflow-tooltip />
      <el-table-column prop="created_at" label="下单时间" width="170" />
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
import { onMounted, reactive, ref } from 'vue'
import http from '../api/http'

const payTypeMap: Record<string, string> = {
  wechat: '微信支付',
  balance: '余额支付',
  period_card: '期限卡',
}

function payTypeLabel(v: string) {
  return payTypeMap[v] || v || '-'
}

const list = ref<any[]>([])
const loading = ref(false)
const page = ref(1)
const total = ref(0)
const filters = reactive<{ order_no: string; user_id: number | null; pay_status: number | null }>({
  order_no: '',
  user_id: null,
  pay_status: null,
})

async function load() {
  loading.value = true
  try {
    const params: Record<string, unknown> = { page: page.value, page_size: 20 }
    if (filters.order_no) params.order_no = filters.order_no
    if (filters.user_id) params.user_id = filters.user_id
    if (filters.pay_status !== null && filters.pay_status !== undefined) params.pay_status = filters.pay_status
    const res = await http.get('/admin/card-purchase-orders', { params })
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

function reset() {
  filters.order_no = ''
  filters.user_id = null
  filters.pay_status = null
  search()
}

onMounted(load)
</script>

<style scoped>
.header-row { display: flex; justify-content: space-between; align-items: center; }
.filters { margin-bottom: 12px; }
.sub { font-size: 12px; color: #999; }
.pager { margin-top: 16px; display: flex; justify-content: flex-end; }
</style>
