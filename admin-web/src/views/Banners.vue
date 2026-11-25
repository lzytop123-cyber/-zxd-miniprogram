<template>
  <el-card>
    <template #header>
      <div class="header-row">
        <span>首页活动</span>
        <el-button type="primary" @click="openAdd">新增活动</el-button>
      </div>
    </template>
    <GlobalConfigHint />
    <p class="hint">
      启用中的活动组成首页轮播，每条可独立选布局。「排序」越小越靠前。
      全屏铺满模式下图片直接覆盖 Hero 绿色区域，高度统一不跳动。
    </p>

    <el-card shadow="never" class="settings-card">
      <template #header>
        <div class="settings-header">
          <span>轮播设置</span>
          <el-button type="primary" size="small" :loading="savingCarousel" @click="saveCarousel">保存设置</el-button>
        </div>
      </template>
      <el-form :model="carousel" label-width="90px" class="carousel-form">
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="展示模式">
              <el-radio-group v-model="carousel.hero_mode">
                <el-radio value="fullscreen">全屏铺满</el-radio>
                <el-radio value="card">卡片嵌入</el-radio>
              </el-radio-group>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="区域高度">
              <el-slider v-model="carousel.hero_height" :min="480" :max="880" :step="20" show-input />
              <span class="field-hint">推荐 640–720 rpx，越高越有沉浸感</span>
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="6">
            <el-form-item label="自动轮播">
              <el-switch v-model="carousel.autoplay" />
            </el-form-item>
          </el-col>
          <el-col :span="6">
            <el-form-item label="间隔">
              <el-input-number v-model="carouselIntervalSec" :min="2" :max="20" /> 秒
            </el-form-item>
          </el-col>
          <el-col :span="6">
            <el-form-item label="循环">
              <el-switch v-model="carousel.circular" />
            </el-form-item>
          </el-col>
          <el-col :span="6">
            <el-form-item label="指示点">
              <el-switch v-model="carousel.indicator_dots" />
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>
    </el-card>

    <el-card shadow="never" class="settings-card">
      <template #header>
        <div class="settings-header">
          <span>小程序微信分享卡片设置</span>
          <el-button type="primary" size="small" :loading="savingCarousel" @click="saveCarousel">保存分享设置</el-button>
        </div>
      </template>
      <el-row :gutter="24" align="middle">
        <el-col :xs="24" :md="14">
          <el-form :model="carousel" label-width="96px" class="carousel-form">
            <el-form-item label="转发标题">
              <el-input
                v-model="carousel.share_title"
                maxlength="40"
                show-word-limit
                clearable
                placeholder="留空则使用默认：沉浸自习，来知行岛"
              />
              <div class="field-hint">建议 8–16 字，简洁有记忆点（顶部灰字已自带小程序名）</div>
            </el-form-item>
            <el-form-item label="5:4 封面图">
              <div class="share-upload-actions">
                <el-upload
                  :show-file-list="false"
                  accept="image/jpeg,image/png,image/webp"
                  :http-request="uploadShareImage"
                >
                  <el-button :loading="uploadingShare" type="primary" plain size="small">上传封面图</el-button>
                </el-upload>
                <el-button
                  v-if="carousel.share_image_url"
                  size="small"
                  @click="carousel.share_image_url = ''"
                >恢复内置默认图</el-button>
              </div>
              <div class="field-hint">推荐比例 5:4（如 750×600 px），小于 2MB；修改保存后小程序无需重新提审即可生效</div>
            </el-form-item>
          </el-form>
        </el-col>
        <el-col :xs="24" :md="10">
          <div class="wx-share-preview">
            <div class="wx-share-app">
              <span class="wx-share-dot"></span>
              <span>知行岛自习空间</span>
            </div>
            <div class="wx-share-title">{{ carousel.share_title?.trim() || '沉浸自习，来知行岛' }}</div>
            <div class="wx-share-img-wrap">
              <img v-if="carousel.share_image_url" :src="carousel.share_image_url" class="wx-share-img" alt="分享封面预览" />
              <div v-else class="wx-share-img wx-share-img--default">使用小程序内置默认 5:4 封面图</div>
            </div>
            <div class="wx-share-foot">小程序</div>
          </div>
        </el-col>
      </el-row>
    </el-card>

    <el-table :data="list" v-loading="loading" stripe class="banner-table">
      <el-table-column prop="sort_order" label="排序" width="70" />
      <el-table-column label="样式" width="100">
        <template #default="{ row }">{{ layoutLabel(row.layout_type) }}</template>
      </el-table-column>
      <el-table-column prop="ribbon" label="标签" width="100">
        <template #default="{ row }">{{ row.ribbon || '—' }}</template>
      </el-table-column>
      <el-table-column label="标题" min-width="140">
        <template #default="{ row }">
          {{ [row.title_line1, row.title_line2].filter(Boolean).join(' / ') || '—' }}
        </template>
      </el-table-column>
      <el-table-column label="图片" width="80">
        <template #default="{ row }">
          <el-image v-if="row.image_url" :src="row.image_url" fit="cover" class="thumb" />
          <span v-else>—</span>
        </template>
      </el-table-column>
      <el-table-column prop="is_active" label="状态" width="80">
        <template #default="{ row }">
          <el-tag :type="row.is_active === 1 ? 'success' : 'info'" size="small">
            {{ row.is_active === 1 ? '启用' : '停用' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="90">
        <template #default="{ row }">
          <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="showDialog" :title="editingId ? '编辑活动' : '新增活动'" width="560px">
      <el-form :model="form" label-width="90px">
        <el-form-item label="展示样式">
          <el-radio-group v-model="form.layout_type">
            <el-radio value="text">纯文字</el-radio>
            <el-radio value="image">纯图片</el-radio>
            <el-radio value="image_text">图片+文字</el-radio>
          </el-radio-group>
        </el-form-item>

        <el-form-item label="活动图片" v-if="form.layout_type !== 'text'">
          <div class="upload-box">
            <el-upload
              :show-file-list="false"
              accept="image/*"
              :http-request="uploadImage"
            >
              <img v-if="form.image_url" :src="form.image_url" class="preview" />
              <el-button v-else :loading="uploading">上传图片</el-button>
            </el-upload>
            <el-button v-if="form.image_url" link type="danger" @click="form.image_url = ''">移除</el-button>
          </div>
          <p class="field-hint">建议宽 750px 左右，jpg/png/webp，不超过 2MB</p>
        </el-form-item>

        <el-form-item label="跳转路径">
          <el-input
            v-model="form.link_path"
            placeholder="如 /pages/exchange/index，留空则按钮跳转最近门店"
            clearable
          />
        </el-form-item>

        <el-divider v-if="form.layout_type !== 'image'" content-position="left">文字内容（留空不显示）</el-divider>

        <template v-if="form.layout_type !== 'image'">
          <el-form-item label="标签">
            <el-input v-model="form.ribbon" placeholder="留空则不显示" clearable />
          </el-form-item>
          <el-form-item label="标题行1">
            <el-input v-model="form.title_line1" placeholder="留空则不显示" clearable />
          </el-form-item>
          <el-form-item label="标题行2">
            <el-input v-model="form.title_line2" placeholder="留空则不显示" clearable />
          </el-form-item>
          <el-form-item label="日期标签">
            <el-input v-model="form.date_label" placeholder="留空则不显示" clearable />
          </el-form-item>
          <el-form-item label="日期范围">
            <el-input v-model="form.date_range" placeholder="留空则不显示" clearable />
          </el-form-item>
          <el-form-item label="按钮文字">
            <el-input v-model="form.cta_text" placeholder="留空则不显示" clearable />
          </el-form-item>
        </template>

        <el-form-item label="排序"><el-input-number v-model="form.sort_order" :min="0" /></el-form-item>
        <el-form-item label="启用"><el-switch v-model="form.is_active" :active-value="1" :inactive-value="0" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showDialog = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submit">保存</el-button>
      </template>
    </el-dialog>
  </el-card>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import GlobalConfigHint from '../components/GlobalConfigHint.vue'
import http from '../api/http'

const list = ref<any[]>([])
const loading = ref(false)
const saving = ref(false)
const savingCarousel = ref(false)
const uploading = ref(false)
const uploadingShare = ref(false)
const showDialog = ref(false)
const editingId = ref<number | null>(null)
const form = reactive<any>({})
const carousel = reactive({
  autoplay: true,
  interval: 5000,
  circular: true,
  indicator_dots: true,
  hero_height: 680,
  hero_mode: 'fullscreen',
  share_title: '',
  share_image_url: '',
})

const carouselIntervalSec = computed({
  get: () => Math.round(carousel.interval / 1000),
  set: (value: number) => {
    carousel.interval = value * 1000
  },
})

const layoutMap: Record<string, string> = {
  text: '纯文字',
  image: '纯图片',
  image_text: '图片+文字',
}

function layoutLabel(type: string) {
  return layoutMap[type] || '纯文字'
}

function resetForm() {
  Object.assign(form, {
    ribbon: '',
    title_line1: '',
    title_line2: '',
    date_label: '',
    date_range: '',
    cta_text: '',
    layout_type: 'text',
    image_url: '',
    link_path: '',
    sort_order: 0,
    is_active: 1,
  })
}

function trimField(value: unknown) {
  return typeof value === 'string' ? value.trim() : ''
}

async function uploadImage(options: { file: File }) {
  uploading.value = true
  try {
    const fd = new FormData()
    fd.append('file', options.file)
    const res = await http.post('/admin/banners/upload-image', fd, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    form.image_url = res.data.url
    ElMessage.success('图片已上传')
  } finally {
    uploading.value = false
  }
}

async function uploadShareImage(options: { file: File }) {
  uploadingShare.value = true
  try {
    const fd = new FormData()
    fd.append('file', options.file)
    const res = await http.post('/admin/banners/upload-image', fd, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    carousel.share_image_url = res.data.url
    ElMessage.success('分享封面已上传，请点击「保存分享设置」生效')
  } finally {
    uploadingShare.value = false
  }
}

async function loadCarousel() {
  const res = await http.get('/admin/banners/carousel-settings')
  Object.assign(carousel, res.data)
}

async function saveCarousel() {
  savingCarousel.value = true
  try {
    await http.put('/admin/banners/carousel-settings', carousel)
    ElMessage.success('轮播设置已保存')
  } finally {
    savingCarousel.value = false
  }
}

async function load() {
  loading.value = true
  try {
    const res = await http.get('/admin/banners')
    list.value = res.data
  } finally {
    loading.value = false
  }
}

function openAdd() {
  editingId.value = null
  resetForm()
  showDialog.value = true
}

function openEdit(row: any) {
  editingId.value = row.id
  Object.assign(form, {
    ...row,
    layout_type: row.layout_type || 'text',
    image_url: row.image_url || '',
    link_path: row.link_path || '',
  })
  showDialog.value = true
}

async function submit() {
  if (form.layout_type !== 'text' && !trimField(form.image_url)) {
    ElMessage.warning('请上传活动图片')
    return
  }

  saving.value = true
  const payload = {
    ribbon: trimField(form.ribbon),
    title_line1: trimField(form.title_line1),
    title_line2: trimField(form.title_line2),
    date_label: trimField(form.date_label),
    date_range: trimField(form.date_range),
    cta_text: trimField(form.cta_text),
    layout_type: form.layout_type || 'text',
    image_url: trimField(form.image_url) || null,
    link_path: trimField(form.link_path) || null,
    sort_order: form.sort_order,
    is_active: form.is_active,
  }
  try {
    if (editingId.value) {
      await http.put(`/admin/banners/${editingId.value}`, payload)
    } else {
      await http.post('/admin/banners', payload)
    }
    ElMessage.success('已保存')
    showDialog.value = false
    load()
  } finally {
    saving.value = false
  }
}

onMounted(async () => {
  await Promise.all([load(), loadCarousel()])
})
</script>

<style scoped>
.header-row { display: flex; justify-content: space-between; align-items: center; }
.hint { color: #888; font-size: 13px; margin: 0 0 12px; line-height: 1.5; }
.settings-card { margin-bottom: 16px; }
.carousel-form { margin-bottom: 0; }
.settings-header { display: flex; justify-content: space-between; align-items: center; }
.banner-table { margin-top: 4px; }
.field-hint { margin: 6px 0 0; color: #999; font-size: 12px; }
.thumb { width: 48px; height: 48px; border-radius: 6px; }
.upload-box { display: flex; align-items: flex-start; gap: 12px; }
.preview {
  display: block;
  max-width: 280px;
  max-height: 140px;
  border-radius: 8px;
  border: 1px solid #eee;
  cursor: pointer;
}
.share-upload-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}
.wx-share-preview {
  width: 248px;
  margin: 0 auto;
  padding: 12px;
  background: #fff;
  border: 1px solid #ebeef5;
  border-radius: 10px;
  box-shadow: 0 2px 10px rgba(0, 0, 0, 0.04);
}
.wx-share-app {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: #8c8c8c;
  margin-bottom: 6px;
}
.wx-share-dot {
  width: 16px;
  height: 16px;
  border-radius: 50%;
  background: #1f4e3d;
  display: inline-block;
}
.wx-share-title {
  font-size: 14px;
  font-weight: 600;
  color: #191919;
  line-height: 1.35;
  margin-bottom: 8px;
  word-break: break-word;
}
.wx-share-img-wrap {
  width: 100%;
  aspect-ratio: 5 / 4;
  border-radius: 4px;
  overflow: hidden;
  background: #f5f7f6;
}
.wx-share-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}
.wx-share-img--default {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 12px;
  box-sizing: border-box;
  text-align: center;
  font-size: 12px;
  color: #2d6a4f;
  background: #ebf3ee;
}
.wx-share-foot {
  margin-top: 8px;
  padding-top: 6px;
  border-top: 1px solid #f2f2f2;
  font-size: 11px;
  color: #999;
}
</style>
