<template>
  <el-card>
    <template #header>
      <div class="header-row">
        <span>优惠券管理</span>
        <el-button type="primary" @click="showAdd = true">发放优惠券</el-button>
      </div>
    </template>
    <el-table :data="list" v-loading="loading" stripe>
      <el-table-column prop="id" label="ID" width="70" />
      <el-table-column prop="user_id" label="用户ID" width="90" />
      <el-table-column prop="coupon_name" label="名称" />
      <el-table-column prop="discount_type" label="类型" width="90" />
      <el-table-column prop="discount_val" label="面值" width="80" />
      <el-table-column prop="min_amount" label="门槛" width="80" />
      <el-table-column prop="expire_date" label="过期" width="120" />
      <el-table-column prop="status" label="状态" width="80">
        <template #default="{ row }">
          {{ row.status === 0 ? '未使用' : '已使用' }}
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="showAdd" title="发放优惠券" width="480px">
      <el-form :model="form" label-width="100px">
        <el-form-item label="用户ID"><el-input-number v-model="form.user_id" :min="1" /></el-form-item>
        <el-form-item label="名称"><el-input v-model="form.coupon_name" /></el-form-item>
        <el-form-item label="类型">
          <el-select v-model="form.discount_type" style="width:100%">
            <el-option label="满减" value="amount" />
            <el-option label="折扣%" value="percent" />
          </el-select>
        </el-form-item>
        <el-form-item label="面值"><el-input-number v-model="form.discount_val" :min="0" /></el-form-item>
        <el-form-item label="门槛"><el-input-number v-model="form.min_amount" :min="0" /></el-form-item>
        <el-form-item label="有效天数"><el-input-number v-model="form.expire_days" :min="1" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showAdd = false">取消</el-button>
        <el-button type="primary" @click="submit">发放</el-button>
      </template>
    </el-dialog>
  </el-card>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import http from '../api/http'

const list = ref<any[]>([])
const loading = ref(false)
const showAdd = ref(false)
const form = reactive({
  user_id: 1,
  coupon_name: '满50减10',
  discount_type: 'amount',
  discount_val: 10,
  min_amount: 50,
  expire_days: 30,
})

async function load() {
  loading.value = true
  try {
    const res = await http.get('/admin/coupons')
    list.value = res.data
  } finally {
    loading.value = false
  }
}

async function submit() {
  await http.post('/admin/coupons', form)
  ElMessage.success('已发放')
  showAdd.value = false
  load()
}

onMounted(load)
</script>

<style scoped>
.header-row { display: flex; justify-content: space-between; align-items: center; }
</style>
