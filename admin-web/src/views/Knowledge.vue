<template>
  <el-card>
    <template #header>
      <div class="header-row">
        <div>
          <span>AI 知识库</span>
          <el-tag type="info" style="margin-left:8px">{{ chars }} 字</el-tag>
        </div>
        <div>
          <el-button @click="load">重新加载</el-button>
          <el-button type="primary" :loading="saving" @click="save">保存</el-button>
        </div>
      </div>
    </template>

    <p class="hint">修改后 AI 学习助手「小岛」会立即使用最新内容回答门店相关问题。文件路径：{{ filePath }}</p>

    <el-input
      v-model="content"
      type="textarea"
      :rows="28"
      placeholder="在此编辑 Markdown 知识库..."
      class="editor"
    />
  </el-card>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import http from '../api/http'

const content = ref('')
const chars = ref(0)
const filePath = ref('')
const saving = ref(false)

async function load() {
  const res = await http.get('/admin/knowledge')
  content.value = res.data.content || ''
  chars.value = res.data.chars || 0
  filePath.value = res.data.path || ''
}

async function save() {
  saving.value = true
  try {
    const res = await http.put('/admin/knowledge', { content: content.value })
    chars.value = res.data.chars || content.value.length
    ElMessage.success(res.message || '已保存')
  } finally {
    saving.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.header-row { display: flex; justify-content: space-between; align-items: center; }
.hint { color: #888; font-size: 13px; margin: 0 0 12px; }
.editor :deep(textarea) { font-family: Consolas, monospace; font-size: 13px; line-height: 1.6; }
</style>
