<template>
  <el-card>
    <template #header>
      <div class="header-row">
        <span>兑换规则</span>
        <el-button type="primary" :loading="saving" @click="save">保存</el-button>
      </div>
    </template>
    <GlobalConfigHint />

    <el-alert
      type="info"
      :closable="false"
      show-icon
      title="旧版小程序兑换页可能不传门店。设置默认门店后，未选店的兑换会落到该营业店；清空则仅在「全站只剩一家营业店」时自动落入。保存后立即生效，无需小程序提审。"
      style="margin-bottom: 16px"
    />

    <el-form label-width="140px" style="max-width: 560px" v-loading="loading">
      <el-form-item label="默认兑换门店">
        <el-select
          v-model="form.default_store_id"
          clearable
          placeholder="不固定（仅唯一营业店时自动）"
          style="width: 100%"
        >
          <el-option
            v-for="s in openStores"
            :key="s.id"
            :label="s.name"
            :value="s.id"
          />
        </el-select>
      </el-form-item>
      <el-form-item label="说明">
        <div class="hint">
          <p>仅列出营业中门店。停业店不能设为默认。</p>
          <p>两家都营业且未设默认时，未带门店的兑换会提示「请选择门店」。</p>
        </div>
      </el-form-item>
    </el-form>
  </el-card>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import GlobalConfigHint from '../components/GlobalConfigHint.vue'
import http from '../api/http'

const loading = ref(false)
const saving = ref(false)
const stores = ref<any[]>([])
const form = reactive<{ default_store_id: number | null }>({
  default_store_id: null,
})

const openStores = computed(() => (stores.value || []).filter((s) => s.status === 1))

async function load() {
  loading.value = true
  try {
    const [settingRes, storesRes] = await Promise.all([
      http.get('/admin/exchange-setting'),
      http.get('/admin/stores'),
    ])
    stores.value = storesRes.data || []
    const data = settingRes.data || {}
    form.default_store_id = data.default_store_id ?? null
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || e?.message || '加载失败')
  } finally {
    loading.value = false
  }
}

async function save() {
  saving.value = true
  try {
    await http.put('/admin/exchange-setting', {
      default_store_id: form.default_store_id,
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
.hint {
  color: #666;
  font-size: 13px;
  line-height: 1.6;
}
.hint p {
  margin: 0 0 6px;
}
</style>
