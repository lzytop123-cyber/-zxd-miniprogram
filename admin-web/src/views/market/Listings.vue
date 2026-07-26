<template>
  <div class="page">
    <el-card>
      <template #header>
        <div class="header">
          <span>内容审核</span>
          <el-radio-group v-model="status" @change="onStatusChange">
            <el-radio-button label="pending">待审核</el-radio-button>
            <el-radio-button label="published">已发布</el-radio-button>
            <el-radio-button label="">全部</el-radio-button>
          </el-radio-group>
        </div>
      </template>
      <el-table :data="items" v-loading="loading" stripe>
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column label="封面" width="96">
          <template #default="{ row }">
            <el-image
              v-if="row.cover || (row.images && row.images[0])"
              :src="row.cover || row.images[0]"
              :preview-src-list="row.images || []"
              fit="cover"
              class="thumb"
              preview-teleported
            />
            <span v-else class="no-img">无图</span>
          </template>
        </el-table-column>
        <el-table-column prop="title" label="标题" min-width="140" />
        <el-table-column prop="store_name" label="门店" width="140" show-overflow-tooltip />
        <el-table-column prop="exam_category_name" label="考试" width="80" />
        <el-table-column prop="material_category_name" label="类型" width="90" />
        <el-table-column prop="price" label="价格" width="80" />
        <el-table-column prop="status" label="状态" width="100" />
        <el-table-column label="操作" width="300" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="openDetail(row)">详情</el-button>
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

    <el-drawer v-model="detailVisible" title="资料详情" size="480px">
      <template v-if="current">
        <div class="detail-title">{{ current.title }}</div>
        <div class="detail-meta">
          {{ current.store_name }} · {{ current.exam_category_name }} · {{ current.material_category_name }}
          · ¥{{ current.price }} · {{ current.status }}
        </div>
        <div class="detail-desc">{{ current.description }}</div>
        <div class="detail-images" v-if="current.images && current.images.length">
          <el-image
            v-for="(img, idx) in current.images"
            :key="idx"
            :src="img"
            :preview-src-list="current.images"
            :initial-index="idx"
            fit="cover"
            class="detail-img"
            preview-teleported
          />
        </div>
        <el-empty v-else description="没有上传图片" />
        <div class="detail-actions" v-if="current.status==='pending'">
          <el-button type="success" @click="review(current, true)">通过</el-button>
          <el-button type="warning" @click="review(current, false)">驳回</el-button>
        </div>
      </template>
    </el-drawer>
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
const detailVisible = ref(false)
const current = ref<any>(null)

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

function onStatusChange() {
  page.value = 1
  load()
}

function openDetail(row: any) {
  current.value = row
  detailVisible.value = true
}

async function review(row: any, approve: boolean) {
  let reject_reason: string | undefined
  if (!approve) {
    const { value } = await ElMessageBox.prompt('驳回原因', '驳回', { inputPattern: /.+/, inputErrorMessage: '必填' })
    reject_reason = value
  }
  await http.post(`/admin/market/listings/${row.id}/review`, { approve, reject_reason })
  ElMessage.success(approve ? '已通过' : '已驳回')
  detailVisible.value = false
  load()
}

async function forceOff(row: any) {
  await ElMessageBox.confirm('确认下架该内容？', '下架')
  await http.post(`/admin/market/listings/${row.id}/off`, { violation: true, note: '后台下架' })
  ElMessage.success('已下架')
  detailVisible.value = false
  load()
}

onMounted(load)
</script>

<style scoped>
.header { display: flex; justify-content: space-between; align-items: center; gap: 12px; }
.pager { margin-top: 16px; display: flex; justify-content: flex-end; }
.thumb { width: 64px; height: 64px; border-radius: 8px; background: #f2f4f3; }
.no-img { color: #999; font-size: 12px; }
.detail-title { font-size: 18px; font-weight: 700; margin-bottom: 8px; }
.detail-meta { color: #888; font-size: 13px; margin-bottom: 16px; }
.detail-desc { white-space: pre-wrap; line-height: 1.6; margin-bottom: 16px; }
.detail-images { display: flex; flex-wrap: wrap; gap: 10px; }
.detail-img { width: 120px; height: 120px; border-radius: 8px; background: #f2f4f3; }
.detail-actions { margin-top: 24px; display: flex; gap: 8px; }
</style>
