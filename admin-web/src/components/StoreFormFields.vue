<template>
  <el-form :model="form" label-width="110px">
    <el-form-item label="门店名称">
      <el-input v-model="form.name" />
    </el-form-item>
    <el-form-item label="地址">
      <el-input v-model="form.address" type="textarea" :rows="2" />
      <div class="field-hint">与高德地图「知行岛·自习室」认证地址保持一致</div>
    </el-form-item>

    <el-form-item label="地图坐标">
      <div class="coord-row">
        <el-input
          v-model="coordPaste"
          placeholder="粘贴高德拾取器坐标，如 112.517856,37.820712"
          clearable
          @keyup.enter="applyCoordPaste"
        />
        <el-button type="primary" plain @click="applyCoordPaste">填入</el-button>
      </div>
      <div class="field-hint">
        打开
        <a href="https://lbs.amap.com/tools/picker" target="_blank" rel="noopener">高德坐标拾取器</a>
        ，搜索门店或点 <strong>B604 门口</strong>，复制「经度,纬度」粘贴上方。
        <strong>只改地址不会更新距离和导航，必须填坐标。</strong>
      </div>
    </el-form-item>

    <el-form-item label="纬度">
      <el-input-number v-model="form.latitude" :precision="6" :step="0.000001" style="width:100%" />
    </el-form-item>
    <el-form-item label="经度">
      <el-input-number v-model="form.longitude" :precision="6" :step="0.000001" style="width:100%" />
    </el-form-item>

    <el-form-item label="封面图">
      <div class="cover-block">
        <div v-if="form.cover_images?.length" class="cover-list">
          <div v-for="(url, idx) in form.cover_images" :key="url" class="cover-item">
            <el-image :src="url" fit="cover" class="cover-preview" />
            <el-button link type="danger" @click="$emit('remove', form, idx)">移除</el-button>
          </div>
        </div>
        <el-upload
          v-if="(form.cover_images?.length || 0) < 5"
          :show-file-list="false"
          accept="image/jpeg,image/png,image/webp,image/gif"
          :http-request="(opt) => $emit('upload', opt, form)"
          :disabled="uploading"
        >
          <el-button type="primary" plain :loading="uploading">上传封面</el-button>
        </el-upload>
        <div class="field-hint">最多 5 张，首张用于首页门店卡片；建议横图 16:9，单张 ≤ 2MB</div>
      </div>
    </el-form-item>

    <el-form-item label="开门时间">
      <el-input v-model="form.open_time" placeholder="08:00" />
    </el-form-item>
    <el-form-item label="关门时间">
      <el-input v-model="form.close_time" placeholder="23:00" />
    </el-form-item>
    <el-form-item label="WiFi 名称">
      <el-input v-model="form.wifi_name" />
    </el-form-item>
    <el-form-item label="WiFi 密码">
      <el-input v-model="form.wifi_password" />
    </el-form-item>
    <el-form-item label="美团门店 ID">
      <el-input v-model="form.meituan_shop_id" placeholder="团购验券用，可留空" />
    </el-form-item>
    <el-form-item v-if="showStatus" label="状态">
      <el-switch v-model="form.status" :active-value="1" :inactive-value="0" active-text="营业" inactive-text="停用" />
    </el-form-item>
  </el-form>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { ElMessage } from 'element-plus'

const props = defineProps<{
  form: Record<string, any>
  uploading?: boolean
  showStatus?: boolean
}>()

defineEmits<{
  upload: [options: any, form: Record<string, any>]
  remove: [form: Record<string, any>, index: number]
}>()

const coordPaste = ref('')

function applyCoordPaste() {
  const text = coordPaste.value.trim()
  if (!text) {
    ElMessage.warning('请先粘贴坐标')
    return
  }
  const parts = text.split(/[,，\s]+/).map((s) => s.trim()).filter(Boolean)
  if (parts.length < 2) {
    ElMessage.warning('格式应为：经度,纬度（例如 112.517856,37.820712）')
    return
  }
  const lng = Number(parts[0])
  const lat = Number(parts[1])
  if (Number.isNaN(lng) || Number.isNaN(lat) || Math.abs(lat) > 90 || Math.abs(lng) > 180) {
    ElMessage.warning('坐标数值无效，请检查是否经度在前、纬度在后')
    return
  }
  props.form.longitude = lng
  props.form.latitude = lat
  ElMessage.success('坐标已填入，请保存门店')
}
</script>

<style scoped>
.cover-block { width: 100%; }
.cover-list { display: flex; flex-wrap: wrap; gap: 12px; margin-bottom: 12px; }
.cover-item { display: flex; flex-direction: column; align-items: center; gap: 4px; }
.cover-preview { width: 120px; height: 72px; border-radius: 8px; border: 1px solid #eee; }
.coord-row { display: flex; gap: 8px; width: 100%; }
.coord-row .el-input { flex: 1; }
.field-hint { font-size: 12px; color: #999; margin-top: 8px; line-height: 1.6; }
.field-hint a { color: #409eff; }
</style>
