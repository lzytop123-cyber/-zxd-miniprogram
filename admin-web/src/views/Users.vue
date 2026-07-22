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
      <el-table-column label="操作" width="240" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click.stop="openDetail(row, 'balance')">编辑</el-button>
          <el-button link type="success" @click.stop="openDetail(row, 'balance')">余额</el-button>
          <el-button link @click.stop="openDetail(row, 'orders')">详情</el-button>
          <el-button link type="danger" @click.stop="removeUser(row)">删除</el-button>
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

    <el-drawer v-model="showDetail" :title="`用户 #${detail?.id || ''}`" size="640px">
      <template v-if="detail">
        <el-descriptions :column="2" border>
          <el-descriptions-item label="学号 ID">{{ detail.id }}</el-descriptions-item>
          <el-descriptions-item label="昵称">{{ detail.nickname || '-' }}</el-descriptions-item>
          <el-descriptions-item label="手机号">{{ detail.phone || '-' }}</el-descriptions-item>
          <el-descriptions-item label="余额">¥{{ detail.balance }}</el-descriptions-item>
          <el-descriptions-item label="积分">{{ detail.total_points }}</el-descriptions-item>
          <el-descriptions-item label="已付订单">{{ detail.paid_order_count }}</el-descriptions-item>
          <el-descriptions-item label="有效期限卡">{{ detail.active_card_count }}</el-descriptions-item>
          <el-descriptions-item label="邀请码">{{ detail.invite_code || '-' }}</el-descriptions-item>
        </el-descriptions>

        <el-tabs v-model="detailTab" class="detail-tabs">
          <el-tab-pane label="余额调整" name="balance">
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
            <p class="hint">正数充值，负数扣减</p>

            <div class="section-title">调整积分</div>
            <el-form inline>
              <el-form-item>
                <el-input-number v-model="adjustPointsDelta" :step="10" />
              </el-form-item>
              <el-form-item>
                <el-input v-model="adjustPointsRemark" placeholder="备注" style="width:160px" />
              </el-form-item>
              <el-form-item>
                <el-button type="primary" @click="adjustPoints">确认调整</el-button>
              </el-form-item>
            </el-form>
            <p class="hint">正数增加，负数扣减</p>

            <div class="section-title">备考方向</div>
            <el-select v-model="editStudyGoal" placeholder="未填写" clearable style="width:160px">
              <el-option label="考研" value="kaoyan" />
              <el-option label="考公" value="kaogong" />
              <el-option label="其他" value="other" />
            </el-select>
            <el-button type="primary" link style="margin-left:8px" @click="saveStudyGoal">保存</el-button>

            <div class="danger-zone">
              <div class="section-title">危险操作</div>
              <p class="hint">删除后不可恢复，将一并清除该用户的预约、期限卡、余额/积分流水等。</p>
              <el-button type="danger" :loading="deleting" @click="removeUser(detail)">删除该用户</el-button>
            </div>
          </el-tab-pane>

          <el-tab-pane label="订单" name="orders">
            <el-table :data="overview.orders || []" size="small" stripe max-height="360">
              <el-table-column prop="order_no" label="订单号" width="150" />
              <el-table-column prop="seat_code" label="座位" width="70" />
              <el-table-column label="套餐" min-width="100" show-overflow-tooltip>
                <template #default="{ row }">{{ row.usage_label || row.bill_type_label || row.bill_type }}</template>
              </el-table-column>
              <el-table-column label="来源" width="100" show-overflow-tooltip>
                <template #default="{ row }">{{ row.pay_source_label || ['待付','已付','退款'][row.pay_status] }}</template>
              </el-table-column>
              <el-table-column prop="status_label" label="状态" width="90" />
              <el-table-column prop="start_time" label="开始" min-width="140" />
            </el-table>
          </el-tab-pane>

          <el-tab-pane label="期限卡" name="cards">
            <div class="tab-actions">
              <el-button type="success" size="small" @click="goIssueCard">手动发期限卡</el-button>
            </div>
            <el-table :data="overview.cards || []" size="small" stripe max-height="360">
              <el-table-column prop="card_name" label="名称" min-width="120" />
              <el-table-column prop="card_type" label="类型" width="90" />
              <el-table-column label="效期" min-width="160" show-overflow-tooltip>
                <template #default="{ row }">{{ row.validity_range || (row.start_date && row.end_date ? `${row.start_date} ~ ${row.end_date}` : '-') }}</template>
              </el-table-column>
              <el-table-column label="余量" width="100">
                <template #default="{ row }">
                  <span v-if="row.remaining_hours != null">{{ row.remaining_hours }}h</span>
                  <span v-else-if="row.remaining_sessions != null">{{ row.remaining_sessions }}次</span>
                  <span v-else>-</span>
                </template>
              </el-table-column>
              <el-table-column prop="status" label="状态" width="70">
                <template #default="{ row }">{{ row.status === 1 ? '有效' : '失效' }}</template>
              </el-table-column>
            </el-table>
          </el-tab-pane>

          <el-tab-pane label="兑换记录" name="exchanges">
            <el-table :data="overview.exchanges || []" size="small" stripe max-height="360">
              <el-table-column prop="coupon_code" label="券码" width="120" />
              <el-table-column prop="deal_name" label="团购" min-width="140" />
              <el-table-column prop="status" label="状态" width="90" />
              <el-table-column prop="created_at" label="时间" min-width="140" />
            </el-table>
          </el-tab-pane>

          <el-tab-pane label="钱包流水" name="wallet">
            <el-table :data="overview.wallet_logs || []" size="small" stripe max-height="360">
              <el-table-column prop="type" label="类型" width="80" />
              <el-table-column prop="amount" label="金额" width="80" />
              <el-table-column prop="remark" label="备注" min-width="140" />
              <el-table-column prop="created_at" label="时间" min-width="140" />
            </el-table>
          </el-tab-pane>
        </el-tabs>
      </template>
    </el-drawer>
  </el-card>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import http from '../api/http'
import { parsePageResult } from '../utils/pageData'

const router = useRouter()

const list = ref<any[]>([])
const loading = ref(false)
const deleting = ref(false)
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
const adjustPointsDelta = ref(0)
const adjustPointsRemark = ref('管理员调整积分')
const detailTab = ref('balance')
const overview = ref<any>({ orders: [], cards: [], exchanges: [], wallet_logs: [] })

function goalTagType(goal: string) {
  if (goal === 'kaoyan') return 'success'
  if (goal === 'kaogong') return 'primary'
  return 'info'
}

async function loadStats() {
  try {
    const res = await http.get('/admin/users/study-goal-stats')
    stats.value = res.data
  } catch {
    stats.value = null
  }
}

async function load() {
  loading.value = true
  try {
    const params: Record<string, unknown> = { page: page.value, page_size: 20 }
    if (keyword.value.trim()) params.keyword = keyword.value.trim()
    if (studyGoal.value) params.study_goal = studyGoal.value
    const res = await http.get('/admin/users', { params })
    const pageData = parsePageResult(res)
    list.value = pageData.items
    total.value = pageData.total
  } catch (e: any) {
    list.value = []
    total.value = 0
    ElMessage.error(e?.message || '加载用户失败，请检查登录状态或到系统状态执行数据库迁移')
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

async function openDetail(row: any, tab = 'balance') {
  const res = await http.get(`/admin/users/${row.id}`)
  detail.value = res.data
  editStudyGoal.value = res.data.study_goal || null
  adjustAmount.value = 0
  detailTab.value = tab
  overview.value = { orders: [], cards: [], exchanges: [], wallet_logs: [] }
  showDetail.value = true
  await loadOverview()
}

async function loadOverview() {
  if (!detail.value) return
  const res = await http.get(`/admin/users/${detail.value.id}/overview`)
  overview.value = res.data
  if (res.data.profile) {
    detail.value = { ...detail.value, ...res.data.profile }
  }
}

function goIssueCard() {
  if (!detail.value) return
  router.push({ path: '/period-cards', query: { userId: String(detail.value.id) } })
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

async function adjustPoints() {
  if (!detail.value || !adjustPointsDelta.value) {
    ElMessage.warning('请输入调整积分')
    return
  }
  const res = await http.post(`/admin/users/${detail.value.id}/adjust-points`, {
    delta: adjustPointsDelta.value,
    remark: adjustPointsRemark.value,
  })
  detail.value.total_points = res.data.total_points
  ElMessage.success('积分已调整')
  load()
}

async function removeUser(row: any) {
  if (!row?.id || deleting.value) return
  try {
    await ElMessageBox.confirm(
      `确定永久删除用户「${row.nickname || row.id}」（学号 #${row.id}）吗？\n将同时删除其预约、期限卡、余额/积分流水等，不可恢复。`,
      '删除用户',
      { type: 'warning', confirmButtonText: '确认删除', cancelButtonText: '取消' },
    )
  } catch {
    return
  }
  deleting.value = true
  try {
    await http.delete(`/admin/users/${row.id}`)
    ElMessage.success('用户已删除')
    if (detail.value?.id === row.id) {
      showDetail.value = false
      detail.value = null
    }
    await loadStats()
    await load()
  } catch (e: any) {
    ElMessage.error(e?.message || '删除失败')
  } finally {
    deleting.value = false
  }
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
.detail-tabs { margin-top: 16px; }
.tab-actions { margin-bottom: 12px; }
.hint { font-size: 12px; color: #999; margin-top: 8px; }
.danger-zone {
  margin-top: 28px;
  padding-top: 8px;
  border-top: 1px dashed #f0a0a0;
}
</style>
