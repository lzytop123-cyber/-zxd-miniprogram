<template>
  <el-card>
    <template #header>预约订单</template>
    <el-table :data="list" v-loading="loading" stripe>
      <el-table-column prop="order_no" label="订单号" width="180" />
      <el-table-column prop="store_name" label="门店" />
      <el-table-column prop="seat_code" label="座位" width="80" />
      <el-table-column prop="bill_type" label="类型" width="100" />
      <el-table-column prop="final_price" label="金额" width="80" />
      <el-table-column prop="pay_status" label="支付" width="80">
        <template #default="{ row }">
          <el-tag :type="row.pay_status === 1 ? 'success' : 'warning'">
            {{ ['待付款', '已付款', '已退款'][row.pay_status] }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="status" label="状态" width="80">
        <template #default="{ row }">
          {{ ['待入座', '使用中', '已完成', '已取消'][row.status] }}
        </template>
      </el-table-column>
      <el-table-column prop="start_time" label="开始时间" width="170" />
    </el-table>
  </el-card>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import http from '../api/http'

const list = ref<any[]>([])
const loading = ref(false)

onMounted(async () => {
  loading.value = true
  try {
    const res = await http.get('/admin/reservations', { params: { page: 1, page_size: 50 } })
    list.value = res.data.items
  } finally {
    loading.value = false
  }
})
</script>
