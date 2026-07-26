<template>
  <div class="page">
    <el-row :gutter="16" class="stats">
      <el-col :span="6" v-for="item in statCards" :key="item.label">
        <el-card><div class="stat-val">{{ item.value }}</div><div class="stat-label">{{ item.label }}</div></el-card>
      </el-col>
    </el-row>

    <el-card style="margin-top: 16px">
      <template #header>举报处理</template>
      <el-table :data="reports" v-loading="loading" stripe>
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column prop="listing_id" label="资料ID" width="90" />
        <el-table-column prop="reason_code" label="原因" width="120" />
        <el-table-column prop="detail" label="说明" min-width="160" />
        <el-table-column prop="status" label="状态" width="100" />
        <el-table-column label="操作" width="200">
          <template #default="{ row }">
            <el-button v-if="row.status==='pending'" size="small" type="danger" @click="handle(row, true)">成立并下架</el-button>
            <el-button v-if="row.status==='pending'" size="small" @click="handle(row, false)">驳回举报</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-card style="margin-top: 16px">
      <template #header>
        <div class="header">
          <span>敏感词</span>
          <div>
            <el-input v-model="word" placeholder="敏感词" style="width: 160px; margin-right: 8px" />
            <el-select v-model="level" style="width: 110px; margin-right: 8px">
              <el-option label="拦截" value="block" />
              <el-option label="送审" value="review" />
            </el-select>
            <el-button type="primary" @click="addWord">添加</el-button>
          </div>
        </div>
      </template>
      <el-table :data="words" stripe>
        <el-table-column prop="word" label="词" />
        <el-table-column prop="level" label="级别" width="100" />
        <el-table-column label="操作" width="100">
          <template #default="{ row }">
            <el-button size="small" type="danger" link @click="delWord(row.id)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-card style="margin-top: 16px">
      <template #header>分类管理</template>
      <el-table :data="categories" stripe>
        <el-table-column prop="type" label="类型" width="100" />
        <el-table-column prop="code" label="编码" width="120" />
        <el-table-column prop="name" label="名称" />
        <el-table-column prop="sort_order" label="排序" width="80" />
        <el-table-column prop="status" label="状态" width="80" />
        <el-table-column label="操作" width="160">
          <template #default="{ row }">
            <el-button size="small" @click="toggleCategory(row)">{{ row.status ? '停用' : '启用' }}</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-card style="margin-top: 16px">
      <template #header>集市用户限制</template>
      <div class="ban-row">
        <el-input-number v-model="banUserId" :min="1" placeholder="用户ID" />
        <el-input v-model="banReason" placeholder="原因" style="width: 240px; margin: 0 8px" />
        <el-button type="danger" @click="setBan(true)">封禁集市</el-button>
        <el-button @click="setBan(false)">解除</el-button>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import http from '../../api/http'
import { parsePageResult } from '../../utils/pageData'

const loading = ref(false)
const stats = ref<any>({})
const reports = ref<any[]>([])
const words = ref<any[]>([])
const categories = ref<any[]>([])
const word = ref('')
const level = ref('block')
const banUserId = ref<number>()
const banReason = ref('')

const statCards = computed(() => [
  { label: '待审核', value: stats.value.pending ?? '-' },
  { label: '已发布', value: stats.value.published ?? '-' },
  { label: '浏览量', value: stats.value.views ?? '-' },
  { label: '联系次数', value: stats.value.contacts ?? '-' },
])

async function load() {
  loading.value = true
  try {
    const [s, r, w, c]: any[] = await Promise.all([
      http.get('/admin/market/stats'),
      http.get('/admin/market/reports', { params: { status: 'pending', page: 1, page_size: 50 } }),
      http.get('/admin/market/sensitive-words'),
      http.get('/admin/market/categories'),
    ])
    stats.value = s.data || {}
    reports.value = parsePageResult(r).items
    words.value = Array.isArray(w.data) ? w.data : []
    categories.value = Array.isArray(c.data) ? c.data : []
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || e?.message || '加载失败')
  } finally {
    loading.value = false
  }
}

async function handle(row: any, accept: boolean) {
  try {
    await http.post(`/admin/market/reports/${row.id}/handle`, {
      accept,
      take_down: accept,
      handle_note: accept ? '举报成立' : '不成立',
    })
    ElMessage.success('已处理')
    await load()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || e?.message || '处理失败')
  }
}

async function addWord() {
  const text = (word.value || '').trim()
  if (!text) {
    ElMessage.warning('请先输入敏感词')
    return
  }
  try {
    await http.post('/admin/market/sensitive-words', {
      word: text,
      level: level.value || 'block',
      status: 1,
    })
    word.value = ''
    ElMessage.success('已添加')
    await load()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || e?.message || '添加失败')
  }
}

async function delWord(id: number) {
  try {
    await http.delete(`/admin/market/sensitive-words/${id}`)
    ElMessage.success('已删除')
    await load()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || e?.message || '删除失败')
  }
}

async function toggleCategory(row: any) {
  try {
    await http.put(`/admin/market/categories/${row.id}`, { status: row.status ? 0 : 1 })
    ElMessage.success('已更新')
    await load()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || e?.message || '更新失败')
  }
}

async function setBan(banned: boolean) {
  if (!banUserId.value) {
    ElMessage.warning('请填写用户ID')
    return
  }
  try {
    await http.post(`/admin/market/users/${banUserId.value}/ban`, {
      banned,
      reason: banReason.value || undefined,
    })
    ElMessage.success('已更新')
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || e?.message || '操作失败')
  }
}

onMounted(load)
</script>

<style scoped>
.stat-val { font-size: 28px; font-weight: 700; color: #2D6A4F; }
.stat-label { color: #888; margin-top: 4px; }
.header { display: flex; justify-content: space-between; align-items: center; }
.ban-row { display: flex; align-items: center; }
</style>
