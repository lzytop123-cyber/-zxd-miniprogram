<template>
  <el-card>
    <template #header>
      <div class="header-row">
        <span>预约规则</span>
        <el-button type="primary" :loading="saving" @click="save">保存</el-button>
      </div>
    </template>

    <el-alert
      type="info"
      :closable="false"
      show-icon
      title="限制「预约开始日」最多可提前多少天，防止远期占座。暑期座位紧可设 3，淡季可设 7；保存后立即对小程序生效，无需重新提审。"
      style="margin-bottom: 16px"
    />

    <el-form label-width="160px" style="max-width: 520px" v-loading="loading">
      <el-form-item label="开始日最多提前">
        <el-input-number
          v-model="form.start_max_advance_days"
          :min="minDays"
          :max="maxDays"
          :step="1"
          controls-position="right"
        />
        <span class="unit">天</span>
      </el-form-item>
      <el-form-item label="说明">
        <div class="hint">
          <p>例：今天是 7 月 26 日、设为 3 → 开始日只能选 7/26～7/29。</p>
          <p>月卡/周卡仍可一次约满连续天数，只是不能把开始日拉得太远。</p>
          <p>可选范围：{{ minDays }}～{{ maxDays }}（0 = 只能约从今天开始）。</p>
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
const minDays = ref(0)
const maxDays = ref(365)
const form = reactive({
  start_max_advance_days: 3,
})

async function load() {
  loading.value = true
  try {
    const res = await http.get('/admin/booking-setting')
    const data = res.data || {}
    form.start_max_advance_days = Number(data.start_max_advance_days ?? 3)
    minDays.value = Number(data.min_days ?? 0)
    maxDays.value = Number(data.max_days ?? 365)
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || e?.message || '加载失败')
  } finally {
    loading.value = false
  }
}

async function save() {
  saving.value = true
  try {
    await http.put('/admin/booking-setting', {
      start_max_advance_days: form.start_max_advance_days,
    })
    ElMessage.success('已保存，立即生效')
    await load()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || e?.message || '保存失败')
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
.unit {
  margin-left: 8px;
  color: #666;
}
.hint {
  color: #666;
  font-size: 13px;
  line-height: 1.7;
}
.hint p {
  margin: 0 0 4px;
}
</style>
