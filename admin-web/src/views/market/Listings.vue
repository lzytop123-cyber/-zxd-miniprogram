<template>
  <div class="page">
    <el-card>
      <template #header>
        <div class="header">
          <span>内容审核</span>
          <el-radio-group v-model="status" @change="load">
            <el-radio-button label="pending">待审核</el-radio-button>
            <el-radio-button label="published">已发布</el-radio-button>
            <el-radio-button label="">全部</el-radio-button>
          </el-radio-group>
        </div>
      </template>
      <el-table :data="items" v-loading="loading" stripe>
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column prop="title" label="标题" min-width="160" />
        <el-table-column prop="store_name" label="门店" width="120" />
        <el-table-column prop="exam_category_name" label="考试" width="90" />
        <el-table-column prop="material_category_name" label="类型" width="100" />
        <el-table-column prop="price" label="价格" width="80" />
        <el-table-column prop="status" label="状态" width="100" />
        <el-table-column label="操作" width="260" fixed="right">
          <template #default="{ row }">
            <el-button v-if="row.status==='pending'" size="small" type="success" @click="review(row, true)">通过</el-button>
            <el-button v-if="row.status==='pending'" size="small" type="warning" @click="review(row, false)">驳回</el-button>
            <el-button size="small" type="danger" @click="forceOff(row)">下架</el-button>
          </template>
        </el-table-column>
      </el-table>
      <div class="pager">
        <el-pagination
          background
          layout="prev, pager, next, total"
          :total="total"
          v-model:current-page="page"
          :page-size="pageSize"
          @current-change="load"
        />
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import http from '../../api/http'
import { parsePageResult } from '../../utils/pageData'

const loading = ref(false)
const items = ref<any[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = 20
const status = ref('pending')

async function load() {
  loading.value = true
  try {
    const params: Record<string, any> = { page: page.value, page_size: pageSize }
    if (status.value) params.status = status.value
    const res: any = await http.get('/admin/market/listings', { params })
    const pageData = parsePageResult(res)
    items.value = pageData.items
    total.value = pageData.total
  } finally {
    loading.value = false
  }
}

async function review(row: any, approve: boolean) {
  let reject_reason: string | undefined
  if (!approve) {
    const { value } = await ElMessageBox.prompt('驳回原因', '驳回', { inputPattern: /.+/, inputErrorMessage: '必填' })
    reject_reason = value
  }
  await http.post(`/admin/market/listings/${row.id}/review`, { approve, reject_reason })
  ElMessage.success(approve ? '已通过' : '已驳回')
  load()
}

async function forceOff(row: any) {
  await ElMessageBox.confirm('确认下架该内容？', '下架')
  await http.post(`/admin/market/listings/${row.id}/off`, { violation: true, note: '后台下架' })
  ElMessage.success('已下架')
  load()
}

onMounted(load)
</script>

<style scoped>
.header { display: flex; justify-content: space-between; align-items: center; gap: 12px; }
.pager { margin-top: 16px; display: flex; justify-content: flex-end; }
</style>
