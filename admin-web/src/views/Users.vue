<template>
  <el-card>
    <template #header>
      <div class="header-row">
        <span>用户管理</span>
        <div class="filters">
          <el-select v-model="studyGoal" placeholder="备考方向" clearable style="width:120px" @change="search">
            <el-option label="全部方向" value="" />
            <el-option label="考研" value="kaoyan" />
            <el-option label="考公" value="kaogong" />
            <el-option label="其他" value="other" />
            <el-option label="未填写" value="unset" />
          </el-select>
          <el-input v-model="keyword" placeholder="ID / 手机号 / 昵称" clearable style="width:220px" @keyup.enter="search">
            <template #append>
              <el-button @click="search">搜索</el-button>
            </template>
          </el-input>
        </div>
      </div>
    </template>

    <el-row :gutter="12" class="stats-row" v-if="stats">
      <el-col :span="6" v-for="item in stats.breakdown" :key="item.key">
        <div class="mini-stat" :class="{ active: studyGoal === item.key }" @click="filterByGoal(item.key)">
          <div class="mini-label">{{ item.label }}</div>
          <div class="mini-value">{{ item.count }}</div>
        </div>
      </el-col>
    </el-row>

    <el-table :data="list" v-loading="loading" stripe @row-click="openDetail">
      <el-table-column prop="id" label="学号" width="70" />
      <el-table-column prop="nickname" label="昵称" min-width="120" />
      <el-table-column prop="phone" label="手机号" width="130" />
      <el-table-column label="备考方向" width="100">
        <template #default="{ row }">
          <el-tag v-if="row.study_goal_label" :type="goalTagType(row.study_goal)" size="small">
            {{ row.study_goal_label }}
          </el-tag>
          <span v-else class="muted">未填写</span>
        </template>
      </el-table-column>
      <el-table-column label="资料" width="90">
        <template #default="{ row }">
          <el-tag v-if="row.needs_profile_setup" type="warning" size="small">待完善</el-tag>
          <el-tag v-else type="success" size="small">已完善</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="title" label="称号" width="80" />
      <el-table-column prop="balance" label="余额" width="90">
        <template #default="{ row }">¥{{ row.balance }}</template>
      </el-table-column>
      <el-table-column prop="total_points" label="积分" width="80" />
      <el-table-column prop="invite_code" label="邀请码" width="100" />
      <el-table-column prop="created_at" label="注册时间" width="170" />
      <el-table-column label="操作" width="90" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click.stop="openDetail(row)">详情</el-button>
        </template>
      </el-table-column>
    </el-table>

    <div class="pager">
      <el-pagination
        v-model:current-page="page"
        :total="total"
        layout="total, prev, pager, next"
        @current-change="load"
      />
    </div>

    <el-drawer v-model="showDetail" :title="`用户 #${detail?.id || ''}`" size="420px">
      <template v-if="detail">
        <el-descriptions :column="1" border>
          <el-descriptions-item label="学号 ID">{{ detail.id }}</el-descriptions-item>
          <el-descriptions-item label="昵称">{{ detail.nickname || '-' }}</el-descriptions-item>
          <el-descriptions-item label="手机号">{{ detail.phone || '-' }}</el-descriptions-item>
          <el-descriptions-item label="资料状态">
            <el-tag v-if="detail.needs_profile_setup" type="warning" size="small">待完善</el-tag>
            <el-tag v-else type="success" size="small">已完善</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="备考方向">
            <el-select v-model="editStudyGoal" placeholder="未填写" clearable style="width:160px">
              <el-option label="考研" value="kaoyan" />
              <el-option label="考公" value="kaogong" />
              <el-option label="其他" value="other" />
            </el-select>
            <el-button type="primary" link style="margin-left:8px" @click="saveStudyGoal">保存</el-button>
          </el-descriptions-item>
          <el-descriptions-item label="余额">¥{{ detail.balance }}</el-descriptions-item>
          <el-descriptions-item label="积分">{{ detail.total_points }}</el-descriptions-item>
          <el-descriptions-item label="已付订单">{{ detail.paid_order_count }}</el-descriptions-item>
          <el-descriptions-item label="有效期限卡">{{ detail.active_card_count }}</el-descriptions-item>
          <el-descriptions-item label="邀请码">{{ detail.invite_code || '-' }}</el-descriptions-item>
          <el-descriptions-item label="注册时间">{{ detail.created_at || '-' }}</el-descriptions-item>
        </el-descriptions>

        <div class="section-title">调整余额</div>
        <el-form inline>
          <el-form-item>
            <el-input-number v-model="adjustAmount" :precision="2" :step="10" />
          </el-form-item>
          <el-form-item>
            <el-input v-model="adjustRemark" placeholder="备注" style="width:160px" />
          </el-form-item>
          <el-form-item>
            <el-button type="primary" @click="adjustBalance">确认调整</el-button>
          </el-form-item>
        </el-form>
        <p class="hint">正数充值，负数扣减（如 -10 表示扣 10 元）</p>
      </template>
    </el-drawer>
  </el-card>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import http from '../api/http'

const list = ref<any[]>([])
const loading = ref(false)
const page = ref(1)
const total = ref(0)
const keyword = ref('')
const studyGoal = ref('')
const stats = ref<any>(null)
const showDetail = ref(false)
const detail = ref<any>(null)
const editStudyGoal = ref<string | null>(null)
const adjustAmount = ref(0)
const adjustRemark = ref('管理员调整余额')

function goalTagType(goal: string) {
  if (goal === 'kaoyan') return 'success'
  if (goal === 'kaogong') return 'primary'
  return 'info'
}

async function loadStats() {
  const res = await http.get('/admin/users/study-goal-stats')
  stats.value = res.data
}

async function load() {
  loading.value = true
  try {
    const params: Record<string, unknown> = { page: page.value, page_size: 20 }
    if (keyword.value.trim()) params.keyword = keyword.value.trim()
    if (studyGoal.value) params.study_goal = studyGoal.value
    const res = await http.get('/admin/users', { params })
    list.value = res.data.items
    total.value = res.data.total
  } finally {
    loading.value = false
  }
}

function search() {
  page.value = 1
  load()
}

function filterByGoal(key: string) {
  studyGoal.value = studyGoal.value === key ? '' : key
  search()
}

async function openDetail(row: any) {
  const res = await http.get(`/admin/users/${row.id}`)
  detail.value = res.data
  editStudyGoal.value = res.data.study_goal || null
  adjustAmount.value = 0
  showDetail.value = true
}

async function saveStudyGoal() {
  if (!detail.value) return
  const res = await http.put(`/admin/users/${detail.value.id}/study-goal`, {
    study_goal: editStudyGoal.value || '',
  })
  detail.value = res.data
  ElMessage.success('备考方向已更新')
  loadStats()
  load()
}

async function adjustBalance() {
  if (!detail.value || !adjustAmount.value) {
    ElMessage.warning('请输入调整金额')
    return
  }
  const res = await http.post(`/admin/users/${detail.value.id}/adjust-balance`, {
    amount: adjustAmount.value,
    remark: adjustRemark.value,
  })
  detail.value = res.data
  ElMessage.success('余额已调整')
  load()
}

onMounted(async () => {
  await loadStats()
  await load()
})
</script>

<style scoped>
.header-row { display: flex; justify-content: space-between; align-items: center; gap: 12px; flex-wrap: wrap; }
.filters { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
.stats-row { margin-bottom: 16px; }
.mini-stat {
  padding: 12px 16px;
  border-radius: 8px;
  background: #f5f7fa;
  cursor: pointer;
  transition: all 0.15s;
}
.mini-stat.active { background: #ecf5ff; box-shadow: inset 0 0 0 1px #409eff; }
.mini-label { font-size: 13px; color: #888; }
.mini-value { font-size: 20px; font-weight: 700; margin-top: 4px; }
.muted { color: #999; }
.pager { margin-top: 16px; display: flex; justify-content: flex-end; }
.section-title { margin: 20px 0 12px; font-weight: 700; }
.hint { font-size: 12px; color: #999; margin-top: 8px; }
</style>
