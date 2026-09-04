<template>
  <el-card>
    <template #header>
      <div class="header-row">
        <span>错题本</span>
        <div class="filters">
          <el-input
            v-model="userId"
            placeholder="用户 ID"
            clearable
            style="width: 120px"
            @keyup.enter="search"
          />
          <el-select v-model="status" placeholder="状态" clearable style="width: 120px" @change="search">
            <el-option label="全部状态" value="" />
            <el-option label="未掌握" :value="0" />
            <el-option label="仍然错" :value="1" />
            <el-option label="已掌握" :value="2" />
          </el-select>
          <el-input
            v-model="keyword"
            placeholder="昵称 / 手机 / OCR / 错因"
            clearable
            style="width: 240px"
            @keyup.enter="search"
          >
            <template #append>
              <el-button @click="search">搜索</el-button>
            </template>
          </el-input>
        </div>
      </div>
    </template>

    <el-table :data="list" v-loading="loading" stripe>
      <el-table-column label="缩略图" width="88">
        <template #default="{ row }">
          <el-image
            v-if="thumbOf(row)"
            :src="mediaUrl(thumbOf(row))"
            :preview-src-list="(row.image_urls || []).map(mediaUrl)"
            fit="cover"
            class="thumb"
            preview-teleported
          />
          <span v-else class="muted">无图</span>
        </template>
      </el-table-column>
      <el-table-column prop="id" label="ID" width="70" />
      <el-table-column label="用户" min-width="140">
        <template #default="{ row }">
          <div>{{ row.user_nickname || '-' }}</div>
          <div class="sub">#{{ row.user_id }} {{ row.user_phone || '' }}</div>
        </template>
      </el-table-column>
      <el-table-column prop="subject_name" label="学科" width="100" />
      <el-table-column label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="statusTagType(row.status)" size="small">
            {{ row.status_label || statusLabel(row.status) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="reason" label="错因" min-width="140" show-overflow-tooltip />
      <el-table-column prop="updated_at" label="更新时间" width="170" />
      <el-table-column label="操作" width="140" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="openDetail(row)">详情</el-button>
          <el-button link type="danger" @click="remove(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <div class="pager">
      <el-pagination
        v-model:current-page="page"
        :total="total"
        :page-size="20"
        layout="total, prev, pager, next"
        @current-change="load"
      />
    </div>

    <el-drawer v-model="showDetail" :title="`错题 #${form.id || ''}`" size="560px">
      <template v-if="form.id">
        <el-descriptions :column="2" border class="mb">
          <el-descriptions-item label="用户">
            {{ form.user_nickname || '-' }}（#{{ form.user_id }}）
          </el-descriptions-item>
          <el-descriptions-item label="手机">{{ form.user_phone || '-' }}</el-descriptions-item>
          <el-descriptions-item label="复习次数">{{ form.review_count ?? 0 }}</el-descriptions-item>
          <el-descriptions-item label="更新时间">{{ form.updated_at || '-' }}</el-descriptions-item>
        </el-descriptions>

        <div class="section-title">题干图片</div>
        <div class="img-row" v-if="(form.image_urls || []).length">
          <el-image
            v-for="(img, idx) in form.image_urls"
            :key="'q' + idx"
            :src="mediaUrl(img)"
            :preview-src-list="(form.image_urls || []).map(mediaUrl)"
            :initial-index="idx"
            fit="cover"
            class="preview"
            preview-teleported
          />
        </div>
        <div v-else class="muted mb">无题干图</div>

        <div class="section-title">答案图片</div>
        <div class="img-row" v-if="(form.answer_image_urls || []).length">
          <el-image
            v-for="(img, idx) in form.answer_image_urls"
            :key="'a' + idx"
            :src="mediaUrl(img)"
            :preview-src-list="(form.answer_image_urls || []).map(mediaUrl)"
            :initial-index="idx"
            fit="cover"
            class="preview"
            preview-teleported
          />
        </div>
        <div v-else class="muted mb">无答案图</div>

        <el-form label-width="80px" class="edit-form">
          <el-form-item label="学科">
            <el-select v-model="form.subject_id" placeholder="选择学科" style="width: 100%">
              <el-option
                v-for="s in subjects"
                :key="s.id"
                :label="s.name"
                :value="s.id"
              />
            </el-select>
          </el-form-item>
          <el-form-item label="状态">
            <el-select v-model="form.status" style="width: 100%">
              <el-option label="未掌握" :value="0" />
              <el-option label="仍然错" :value="1" />
              <el-option label="已掌握" :value="2" />
            </el-select>
          </el-form-item>
          <el-form-item label="OCR">
            <el-input v-model="form.ocr_text" type="textarea" :rows="4" />
          </el-form-item>
          <el-form-item label="答案">
            <el-input v-model="form.answer_text" type="textarea" :rows="3" />
          </el-form-item>
          <el-form-item label="错因">
            <el-input v-model="form.reason" maxlength="200" show-word-limit />
          </el-form-item>
          <el-form-item label="标签">
            <el-input
              v-model="tagsText"
              placeholder="多个标签用逗号分隔"
            />
          </el-form-item>
        </el-form>

        <div class="drawer-actions">
          <el-button type="primary" :loading="saving" @click="save">保存</el-button>
          <el-button type="danger" plain @click="remove(form)">删除</el-button>
        </div>
      </template>
    </el-drawer>
  </el-card>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import http from '../api/http'
import { parsePageResult } from '../utils/pageData'

type Subject = { id: number; name: string }

const list = ref<any[]>([])
const loading = ref(false)
const page = ref(1)
const total = ref(0)
const keyword = ref('')
const userId = ref('')
const status = ref<number | ''>('')

const showDetail = ref(false)
const form = ref<any>({})
const subjects = ref<Subject[]>([])
const tagsText = ref('')
const saving = ref(false)

function mediaUrl(path: string): string {
  if (!path) return ''
  if (/^https?:\/\//i.test(path)) return path
  const apiBase = (import.meta.env.VITE_API_BASE as string) || '/api'
  if (apiBase.startsWith('http')) {
    const origin = apiBase.replace(/\/api\/?$/, '')
    return origin + (path.startsWith('/') ? path : `/${path}`)
  }
  return path.startsWith('/') ? path : `/${path}`
}

function thumbOf(row: any): string {
  return row.thumb_url || (row.image_urls && row.image_urls[0]) || ''
}

function statusLabel(s: number) {
  return ({ 0: '未掌握', 1: '仍然错', 2: '已掌握' } as Record<number, string>)[s] || '未掌握'
}

function statusTagType(s: number) {
  if (s === 2) return 'success'
  if (s === 1) return 'danger'
  return 'warning'
}

function search() {
  page.value = 1
  load()
}

async function load() {
  loading.value = true
  try {
    const params: Record<string, unknown> = { page: page.value, page_size: 20 }
    if (keyword.value.trim()) params.keyword = keyword.value.trim()
    if (userId.value.trim()) params.user_id = Number(userId.value.trim())
    if (status.value !== '' && status.value !== null && status.value !== undefined) {
      params.status = status.value
    }
    const res = await http.get('/admin/wrongbook/questions', { params })
    const pageData = parsePageResult(res)
    list.value = pageData.items
    total.value = pageData.total
  } catch (e: any) {
    ElMessage.error(e?.message || '加载失败')
  } finally {
    loading.value = false
  }
}

async function openDetail(row: any) {
  try {
    const res = await http.get(`/admin/wrongbook/questions/${row.id}`)
    form.value = { ...(res.data || {}) }
    tagsText.value = Array.isArray(form.value.tags) ? form.value.tags.join(', ') : ''
    subjects.value = []
    if (form.value.user_id) {
      const subRes = await http.get('/admin/wrongbook/subjects', {
        params: { user_id: form.value.user_id },
      })
      subjects.value = Array.isArray(subRes.data) ? subRes.data : []
    }
    showDetail.value = true
  } catch (e: any) {
    ElMessage.error(e?.message || '加载详情失败')
  }
}

async function save() {
  if (!form.value.id) return
  saving.value = true
  try {
    const tags = tagsText.value
      .split(/[,，]/)
      .map((t) => t.trim())
      .filter(Boolean)
    const res = await http.put(`/admin/wrongbook/questions/${form.value.id}`, {
      subject_id: form.value.subject_id,
      ocr_text: form.value.ocr_text ?? '',
      answer_text: form.value.answer_text ?? '',
      reason: form.value.reason ?? '',
      tags,
      status: form.value.status,
    })
    form.value = { ...(res.data || form.value) }
    tagsText.value = Array.isArray(form.value.tags) ? form.value.tags.join(', ') : tagsText.value
    ElMessage.success('已保存')
    load()
  } catch (e: any) {
    ElMessage.error(e?.message || '保存失败')
  } finally {
    saving.value = false
  }
}

async function remove(row: any) {
  try {
    await ElMessageBox.confirm(`确定删除错题 #${row.id}？此操作不可恢复。`, '删除错题', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })
    await http.delete(`/admin/wrongbook/questions/${row.id}`)
    ElMessage.success('已删除')
    if (showDetail.value && form.value.id === row.id) showDetail.value = false
    load()
  } catch (e: any) {
    if (e === 'cancel' || e === 'close') return
    ElMessage.error(e?.message || '删除失败')
  }
}

onMounted(load)
</script>

<style scoped>
.header-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}
.filters {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
.pager {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}
.thumb {
  width: 56px;
  height: 56px;
  border-radius: 4px;
}
.sub {
  color: #999;
  font-size: 12px;
}
.muted {
  color: #999;
}
.mb {
  margin-bottom: 12px;
}
.section-title {
  font-weight: 600;
  margin: 12px 0 8px;
}
.img-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 12px;
}
.preview {
  width: 96px;
  height: 96px;
  border-radius: 4px;
}
.edit-form {
  margin-top: 8px;
}
.drawer-actions {
  display: flex;
  gap: 8px;
  margin-top: 16px;
}
</style>
