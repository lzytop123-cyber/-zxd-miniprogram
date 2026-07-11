<template>
  <el-card>
    <template #header>
      <div class="header-row">
        <div>
          <span>AI 知识库</span>
          <el-tag type="info" style="margin-left:8px">{{ chars }} 字</el-tag>
          <el-tag v-if="rag.enabled" type="success" style="margin-left:8px">
            RAG · {{ rag.documents }} 文档 / {{ rag.chunks }} 片段
          </el-tag>
        </div>
        <div>
          <el-button @click="load">重新加载</el-button>
          <el-button type="primary" :loading="saving" @click="save">保存补充说明</el-button>
        </div>
      </div>
    </template>

    <p class="hint">
      上传多份 Word / Markdown 文档后，AI 会按用户问题自动检索相关片段回答。
      下方文本框可写「补充说明」，保存后也会进入向量库。
    </p>

    <div class="upload-row">
      <el-upload
        :show-file-list="false"
        accept=".md,.markdown,.txt,.docx,text/plain,text/markdown,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        :http-request="uploadDocument"
        :disabled="uploading"
      >
        <el-button type="primary" :loading="uploading">上传文档入库</el-button>
      </el-upload>
      <span class="upload-tip">支持 .md / .txt / .docx，单文件 ≤ 2MB；点击文档名可预览</span>
    </div>

    <el-table v-if="documents.length" :data="documents" size="small" class="doc-table">
      <el-table-column prop="filename" label="文档" min-width="180">
        <template #default="{ row }">
          <el-button link type="primary" :loading="previewingId === row.id" @click="openPreview(row)">
            {{ row.filename }}
          </el-button>
        </template>
      </el-table-column>
      <el-table-column prop="source" label="来源" width="90">
        <template #default="{ row }">
          {{ sourceLabel(row.source) }}
        </template>
      </el-table-column>
      <el-table-column prop="chunks" label="片段" width="70" />
      <el-table-column prop="chars" label="字数" width="80" />
      <el-table-column prop="updated_at" label="更新时间" min-width="160">
        <template #default="{ row }">
          {{ formatTime(row.updated_at || row.created_at) }}
        </template>
      </el-table-column>
      <el-table-column label="操作" width="90" fixed="right">
        <template #default="{ row }">
          <el-button link type="danger" :loading="deletingId === row.id" @click="removeDoc(row)">
            删除
          </el-button>
        </template>
      </el-table-column>
    </el-table>
    <el-empty v-else description="暂无已入库文档，请先上传" :image-size="72" />

    <div class="section-title">补充说明（可选）</div>
    <el-input
      v-model="content"
      type="textarea"
      :rows="14"
      placeholder="可在此补充门店 FAQ、临时公告等；保存后会同步进向量库..."
      class="editor"
    />

    <el-dialog v-model="previewVisible" :title="previewTitle" width="720px" destroy-on-close>
      <div class="preview-meta" v-if="previewMeta">
        {{ previewMeta }}
      </div>
      <el-scrollbar max-height="480px">
        <pre class="preview-content">{{ previewContent }}</pre>
      </el-scrollbar>
    </el-dialog>
  </el-card>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { UploadRequestOptions } from 'element-plus'
import http from '../api/http'

type KnowledgeDoc = {
  id: string
  filename: string
  source: string
  chars: number
  chunks: number
  created_at?: string
  updated_at?: string
}

type RagStats = {
  enabled: boolean
  documents: number
  chunks: number
}

const content = ref('')
const chars = ref(0)
const saving = ref(false)
const uploading = ref(false)
const deletingId = ref('')
const previewingId = ref('')
const previewVisible = ref(false)
const previewTitle = ref('文档预览')
const previewContent = ref('')
const previewMeta = ref('')
const documents = ref<KnowledgeDoc[]>([])
const rag = ref<RagStats>({ enabled: false, documents: 0, chunks: 0 })

function sourceLabel(source: string) {
  if (source === 'manual') return '手动'
  if (source === 'legacy') return '导入'
  return '上传'
}

function formatTime(value?: string) {
  if (!value) return '-'
  try {
    return new Date(value).toLocaleString()
  } catch {
    return value
  }
}

async function load() {
  const res = await http.get('/admin/knowledge')
  content.value = res.data.content || ''
  chars.value = res.data.chars || 0
  documents.value = res.data.documents || []
  rag.value = res.data.rag || { enabled: false, documents: 0, chunks: 0 }
}

async function save() {
  saving.value = true
  try {
    const res = await http.put('/admin/knowledge', { content: content.value })
    chars.value = res.data.chars || content.value.length
    documents.value = res.data.documents || documents.value
    rag.value = res.data.rag || rag.value
    ElMessage.success(res.message || '已保存')
  } finally {
    saving.value = false
  }
}

async function uploadDocument(options: UploadRequestOptions) {
  uploading.value = true
  try {
    const fd = new FormData()
    fd.append('file', options.file)
    const res = await http.post('/admin/knowledge/upload', fd, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    documents.value = res.data.documents || documents.value
    rag.value = res.data.rag || rag.value
    ElMessage.success(res.message || '文档已入库')
    options.onSuccess?.(res as any)
  } catch (e: any) {
    const msg = e?.message || '上传失败'
    ElMessage.error(msg)
    options.onError?.(e)
  } finally {
    uploading.value = false
  }
}

async function openPreview(row: KnowledgeDoc) {
  previewingId.value = row.id
  try {
    const res = await http.get(`/admin/knowledge/documents/${row.id}`)
    previewTitle.value = res.data.document?.filename || row.filename
    previewContent.value = res.data.content || ''
    const doc = res.data.document || row
    previewMeta.value = `${doc.chunks || 0} 个片段 · ${res.data.chars || 0} 字`
    previewVisible.value = true
  } catch (e: any) {
    ElMessage.error(e?.message || '预览失败')
  } finally {
    previewingId.value = ''
  }
}

async function removeDoc(row: KnowledgeDoc) {
  try {
    await ElMessageBox.confirm(`确定删除「${row.filename}」？相关向量片段会一并移除。`, '删除文档', {
      type: 'warning',
    })
  } catch {
    return
  }
  deletingId.value = row.id
  try {
    const res = await http.delete(`/admin/knowledge/documents/${row.id}`)
    documents.value = res.data.documents || []
    rag.value = res.data.rag || rag.value
    if (row.id === 'manual') content.value = ''
    ElMessage.success('已删除')
  } finally {
    deletingId.value = ''
  }
}

onMounted(load)
</script>

<style scoped>
.header-row { display: flex; justify-content: space-between; align-items: center; }
.hint { color: #888; font-size: 13px; margin: 0 0 12px; }
.upload-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
  margin-bottom: 16px;
}
.upload-tip { color: #999; font-size: 12px; }
.doc-table { margin-bottom: 20px; }
.section-title {
  font-size: 14px;
  font-weight: 600;
  color: #303133;
  margin-bottom: 8px;
}
.editor :deep(textarea) { font-family: Consolas, monospace; font-size: 13px; line-height: 1.6; }
.preview-meta { color: #888; font-size: 12px; margin-bottom: 12px; }
.preview-content {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
  font-family: Consolas, monospace;
  font-size: 13px;
  line-height: 1.7;
  color: #303133;
}
</style>
