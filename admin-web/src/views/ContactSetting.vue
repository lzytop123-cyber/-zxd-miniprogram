<template>
  <el-card>
    <template #header>
      <div class="header-row">
        <span>联系店长海报</span>
        <el-button type="primary" :disabled="!storeId || loading || uploading" :loading="saving" @click="save">保存文案</el-button>
      </div>
    </template>
    <el-select v-model="storeId" placeholder="选择门店" :disabled="loading || saving || uploading" @change="load" style="margin-bottom: 16px">
      <el-option v-for="store in stores" :key="store.id" :label="store.name" :value="store.id" />
    </el-select>

    <el-alert
      type="info"
      :closable="false"
      show-icon
      title="请为所选门店上传对应店长的微信二维码（≤2MB）。小程序可按定位推荐门店，用户也可手动切换。"
      style="margin-bottom: 16px"
    />

    <el-form :disabled="!storeId || loading || saving || uploading" label-width="100px" style="max-width: 640px" v-loading="loading">
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
              :disabled="!storeId || loading || saving || uploading"
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
const stores = ref<{ id: number; name: string }[]>([])
const storeId = ref<number>()
const contactUrl = () => `/admin/contact-setting?store_id=${storeId.value}`
const form = reactive({
  poster_url: '' as string,
  title: '联系店长',
  hint: '长按识别二维码，添加店长微信咨询',
})

async function load() {
  if (!storeId.value) return
  loading.value = true
  form.poster_url = ''
  form.title = '联系店长'
  form.hint = '长按识别二维码，添加店长微信咨询'
  try {
    const res = await http.get(contactUrl())
    form.poster_url = res.data?.poster_url || ''
    form.title = res.data?.title || '联系店长'
    form.hint = res.data?.hint || '长按识别二维码，添加店长微信咨询'
  } catch (_) {
    storeId.value = undefined
    ElMessage.error('配置加载失败，请重新选择门店')
  } finally {
    loading.value = false
  }
}

async function save() {
  if (!storeId.value) return
  saving.value = true
  try {
    await http.put(contactUrl(), {
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
  if (!storeId.value) return
  uploading.value = true
  try {
    const fd = new FormData()
    fd.append('file', options.file)
    const res = await http.post(`/admin/contact-setting/upload?store_id=${storeId.value}`, fd, {
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
    await http.put(contactUrl(), { poster_url: '' })
    form.poster_url = ''
    ElMessage.success('已清除海报')
  } finally {
    saving.value = false
  }
}

onMounted(async () => {
  try {
    const res = await http.get('/admin/stores')
    stores.value = res.data || []
    storeId.value = stores.value[0]?.id
    await load()
  } catch (_) { ElMessage.error('门店配置加载失败，请刷新重试') }
})
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
