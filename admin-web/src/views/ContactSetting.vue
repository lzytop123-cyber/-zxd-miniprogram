<template>
  <el-card>
    <template #header>
      <div class="header-row">
        <span>联系店长海报</span>
        <el-button type="primary" :loading="saving" @click="save">保存文案</el-button>
      </div>
    </template>

    <el-alert
      type="info"
      :closable="false"
      show-icon
      title="小程序「联系店长」会展示此处海报；用户长按图片可识别二维码。建议上传含店长微信二维码的完整海报（≤2MB）。"
      style="margin-bottom: 16px"
    />

    <el-form label-width="100px" style="max-width: 640px" v-loading="loading">
      <el-form-item label="页面标题">
        <el-input v-model="form.title" maxlength="50" show-word-limit placeholder="联系店长" />
      </el-form-item>
      <el-form-item label="提示文案">
        <el-input
          v-model="form.hint"
          maxlength="100"
          show-word-limit
          placeholder="长按识别二维码，添加店长微信咨询"
        />
      </el-form-item>
      <el-form-item label="海报图片">
        <div class="poster-box">
          <el-image
            v-if="form.poster_url"
            :src="form.poster_url"
            fit="contain"
            class="poster-preview"
            :preview-src-list="[form.poster_url]"
          />
          <div v-else class="poster-empty">尚未上传海报</div>
          <div class="poster-actions">
            <el-upload
              :show-file-list="false"
              accept="image/jpeg,image/png,image/webp,image/gif"
              :http-request="uploadPoster"
            >
              <el-button type="primary" :loading="uploading">{{ form.poster_url ? '更换海报' : '上传海报' }}</el-button>
            </el-upload>
            <el-button v-if="form.poster_url" link type="danger" @click="clearPoster">清除</el-button>
          </div>
        </div>
      </el-form-item>
    </el-form>
  </el-card>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import http from '../api/http'

const loading = ref(false)
const saving = ref(false)
const uploading = ref(false)
const form = reactive({
  poster_url: '' as string,
  title: '联系店长',
  hint: '长按识别二维码，添加店长微信咨询',
})

async function load() {
  loading.value = true
  try {
    const res = await http.get('/admin/contact-setting')
    form.poster_url = res.data?.poster_url || ''
    form.title = res.data?.title || '联系店长'
    form.hint = res.data?.hint || '长按识别二维码，添加店长微信咨询'
  } finally {
    loading.value = false
  }
}

async function save() {
  saving.value = true
  try {
    await http.put('/admin/contact-setting', {
      title: form.title,
      hint: form.hint,
    })
    ElMessage.success('已保存')
    await load()
  } finally {
    saving.value = false
  }
}

async function uploadPoster(options: { file: File }) {
  uploading.value = true
  try {
    const fd = new FormData()
    fd.append('file', options.file)
    const res = await http.post('/admin/contact-setting/upload', fd, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    form.poster_url = res.data?.poster_url || ''
    ElMessage.success(res.message || '上传成功')
  } finally {
    uploading.value = false
  }
}

async function clearPoster() {
  saving.value = true
  try {
    await http.put('/admin/contact-setting', { poster_url: '' })
    form.poster_url = ''
    ElMessage.success('已清除海报')
  } finally {
    saving.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.header-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.poster-box {
  width: 100%;
}
.poster-preview {
  width: 280px;
  max-height: 420px;
  border-radius: 12px;
  border: 1px solid #ebeef5;
  background: #f5f7fa;
}
.poster-empty {
  width: 280px;
  height: 180px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #909399;
  background: #f5f7fa;
  border-radius: 12px;
  border: 1px dashed #dcdfe6;
}
.poster-actions {
  margin-top: 12px;
  display: flex;
  align-items: center;
  gap: 8px;
}
</style>
