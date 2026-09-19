<template>
  <div class="receipts" v-loading="initialLoading">
    <div class="heading">
      <div><h2>收款管理</h2><p>美团、抖音按核销入账，微信按支付入账，微信转账手工登记。</p></div>
      <div class="actions">
        <el-button :loading="refreshing" @click="refresh">刷新并同步收款</el-button>
        <el-button type="primary" @click="openCreate">登记收款</el-button>
      </div>
    </div>

    <el-alert v-if="error" :title="error" type="error" show-icon :closable="false" />
    <div class="metrics">
      <el-card v-for="card in cards" :key="card.label" shadow="never" :class="{ 'net-card': card.net }">
        <div class="metric-label">{{ card.label }}</div>
        <div class="metric-value">{{ card.value === undefined ? '—' : `¥${money(card.value)}` }}</div>
      </el-card>
    </div>
    <div v-if="currentSummary && (currentSummary.missing_dates || currentSummary.refunds_to_review || currentSummary.platforms_to_review)" class="review-notice">
      <span>统计待核对：</span>
      <el-button v-if="currentSummary.missing_dates" link type="warning" @click="showReview('date')">
        {{ currentSummary.missing_dates }} 笔缺少收款日期，未计入汇总
      </el-button>
      <el-button v-if="currentSummary.refunds_to_review" link type="warning" @click="showReview('refund')">
        {{ currentSummary.refunds_to_review }} 笔订单标记退款，需核实实际退款
      </el-button>
      <el-button v-if="currentSummary.platforms_to_review" link type="warning" @click="showPlatformReview">
        {{ currentSummary.platforms_to_review }} 笔核销待核对，尚未自动入账
      </el-button>
    </div>

    <el-card shadow="never">
      <template #header><span>按年月查看</span></template>
      <el-form inline class="filters" @submit.prevent="search">
        <el-form-item label="年份">
          <el-input-number v-model="filters.year" :min="2000" :max="9998" :precision="0" :value-on-clear="nowYear" controls-position="right" style="width:120px" />
        </el-form-item>
        <el-form-item label="月份">
          <el-select v-model="filters.month" style="width:120px">
            <el-option label="全年" :value="0" />
            <el-option v-for="month in 12" :key="month" :label="`${month} 月`" :value="month" />
          </el-select>
        </el-form-item>
        <el-form-item label="渠道">
          <el-select v-model="filters.channel" clearable placeholder="全部渠道" style="width:170px">
            <el-option v-for="(label, key) in channels" :key="key" :label="label" :value="key" />
          </el-select>
        </el-form-item>
        <el-form-item><el-button type="primary" :loading="loading" @click="search">查询</el-button><el-button @click="reset">本月</el-button></el-form-item>
      </el-form>
      <div class="period-summary">
        <span>{{ periodLabel }}{{ applied.channel ? ` · ${channels[applied.channel]}` : '' }}</span>
        <span>收款 <b>¥{{ money(selectedSummary?.month.received) }}</b></span>
        <span>退款 <b>¥{{ money(selectedSummary?.month.refunded) }}</b></span>
        <span>净收款 <b>¥{{ money(selectedSummary?.month.net) }}</b></span>
      </div>
      <el-table :data="selectedSummary?.channels || []" v-loading="loading" stripe>
        <el-table-column label="渠道" min-width="170"><template #default="{ row }">{{ channels[row.channel as Channel] }}</template></el-table-column>
        <el-table-column label="收款（元）" min-width="120" align="right"><template #default="{ row }">{{ money(row.received) }}</template></el-table-column>
        <el-table-column label="退款（元）" min-width="120" align="right"><template #default="{ row }">{{ money(row.refunded) }}</template></el-table-column>
        <el-table-column label="净收款（元）" min-width="120" align="right"><template #default="{ row }">{{ money(row.net) }}</template></el-table-column>
      </el-table>
    </el-card>

    <el-card shadow="never">
      <el-tabs v-model="tab" @tab-change="changeTab">
        <el-tab-pane label="收款记录" name="receipts" />
        <el-tab-pane label="退款记录" name="refunds" />
        <el-tab-pane label="核销待核对" name="platforms" />
      </el-tabs>
      <div v-if="tab !== 'platforms'" class="list-tools">
        <el-input v-model="keyword" placeholder="同学姓名、流水号或收款备注" clearable maxlength="100" style="max-width:320px" @keyup.enter="searchList" @clear="searchList" />
        <el-button :loading="listLoading" @click="searchList">搜索明细</el-button>
        <el-tag v-if="review" type="warning" closable @close="clearReview">{{ review === 'date' ? '全部待补日期' : '全部待核实退款' }}（不限年月渠道）</el-tag>
        <span v-else class="muted">{{ periodLabel }} · {{ tab === 'receipts' ? '按收款日期' : '按退款日期' }}</span>
      </div>
      <div v-else class="list-tools">
        <span class="muted">显示全部待核对核销，不限年月。参考价不计入汇总；已经手工记过账的券请关联原收款。</span>
        <el-button type="primary" :loading="reconciling" :disabled="!total" @click="bulkReconcile">一键核对</el-button>
      </div>
      <el-table v-if="tab === 'receipts'" :data="receipts" v-loading="listLoading" stripe empty-text="暂无收款记录，可登记收款或切换年月查看">
        <el-table-column prop="id" label="编号" width="75" />
        <el-table-column label="收款日期" width="135"><template #default="{ row }"><span v-if="row.received_on">{{ row.received_on }}</span><el-tag v-else type="warning" size="small">待补日期</el-tag></template></el-table-column>
        <el-table-column label="渠道" width="155"><template #default="{ row }">{{ channels[row.channel as Channel] }}</template></el-table-column>
        <el-table-column prop="customer" label="同学 / 付款人" min-width="120" show-overflow-tooltip />
        <el-table-column label="收款（元）" width="115" align="right"><template #default="{ row }">{{ money(row.amount) }}</template></el-table-column>
        <el-table-column label="累计退款（元）" width="130" align="right"><template #default="{ row }">{{ money(row.refunded_amount) }}</template></el-table-column>
        <el-table-column prop="reference" label="流水号 / 订单号" min-width="180" show-overflow-tooltip />
        <el-table-column prop="remark" label="备注" min-width="140" show-overflow-tooltip />
        <el-table-column label="来源 / 状态" width="140"><template #default="{ row }"><span>{{ row.source_label }}</span><div v-if="row.refund_needs_review"><el-tag size="small" type="warning">退款待核实</el-tag></div></template></el-table-column>
        <el-table-column label="操作" width="115" fixed="right"><template #default="{ row }">
          <el-button v-if="!row.received_on" link type="primary" @click="openDate(row)">补收款日期</el-button>
          <el-button v-else-if="Number(row.remaining) > 0" link type="primary" @click="openRefund(row)">登记退款</el-button>
          <span v-else class="muted">已全额退款</span>
        </template></el-table-column>
      </el-table>
      <el-table v-else-if="tab === 'refunds'" :data="refunds" v-loading="listLoading" stripe empty-text="所选期间暂无已登记退款">
        <el-table-column prop="refunded_on" label="退款日期" width="130" />
        <el-table-column prop="receipt_id" label="原收款编号" width="105" />
        <el-table-column label="渠道" width="155"><template #default="{ row }">{{ channels[row.channel as Channel] }}</template></el-table-column>
        <el-table-column prop="customer" label="同学 / 付款人" min-width="120" />
        <el-table-column label="退款（元）" width="120" align="right"><template #default="{ row }">{{ money(row.amount) }}</template></el-table-column>
        <el-table-column prop="reference" label="原流水号 / 订单号" min-width="180" show-overflow-tooltip />
        <el-table-column prop="reason" label="退款原因" min-width="180" show-overflow-tooltip />
        <el-table-column label="状态" width="110"><template #default><el-tag type="success" size="small">已完成退款</el-tag></template></el-table-column>
      </el-table>
      <el-table v-else :data="platforms" v-loading="listLoading" stripe empty-text="暂无待核对核销">
        <el-table-column label="渠道" width="120"><template #default="{ row }">{{ row.channel ? channels[row.channel as Channel] : '待确认' }}</template></el-table-column>
        <el-table-column prop="received_on" label="核销日期" width="125" />
        <el-table-column prop="customer" label="同学" width="110" />
        <el-table-column prop="deal_name" label="团购名称" min-width="150" show-overflow-tooltip />
        <el-table-column prop="reference" label="券码 / 流水号" min-width="160" show-overflow-tooltip />
        <el-table-column label="接口实付（元）" width="135" align="right"><template #default="{ row }">{{ row.amount === null ? '待核对' : money(row.amount) }}</template></el-table-column>
        <el-table-column label="参考价（元）" width="125" align="right"><template #default="{ row }">{{ row.reference_price === null ? '—' : money(row.reference_price) }}</template></el-table-column>
        <el-table-column prop="reason" label="待核对原因" min-width="240" />
        <el-table-column label="操作" width="100" fixed="right"><template #default="{ row }"><el-button link type="primary" @click="openPlatform(row)">核对入账</el-button></template></el-table-column>
      </el-table>
      <div class="pager"><el-pagination v-model:current-page="page" :page-size="20" :total="total" layout="total, prev, pager, next" @current-change="loadList" /></div>
    </el-card>
    <p class="footnote">净收款 = 已入账金额 − 已登记退款。美团、抖音按核销日期及已确认金额统计，不是扣佣后的到账额，平台后续结算不再重复入账。微信支付包含预约、购卡、充值，余额消费不重复计收款。退款登记不自动退钱，也不变更余额、套餐或预约权益。</p>

    <el-dialog v-model="createVisible" title="登记收款" width="min(520px, 94vw)" :close-on-click-modal="false">
      <el-alert v-if="createForm.channel !== 'wechat_transfer'" title="平台核销会自动同步；待核对的券请在「核销待核对」中处理。这里只补记未收录的款项，请勿重复登记平台结算款。" type="warning" :closable="false" />
      <el-form label-width="100px" @submit.prevent="saveReceipt">
        <el-form-item label="收款渠道" required><el-select v-model="createForm.channel" style="width:100%"><el-option v-for="channel in manualChannels" :key="channel" :label="channels[channel]" :value="channel" /></el-select></el-form-item>
        <el-form-item label="实收金额" required><el-input-number v-model="createForm.amount" :min="0.01" :max="99999999.99" :precision="2" :step="1" style="width:100%" /></el-form-item>
        <el-form-item label="收款日期" required><el-date-picker v-model="createForm.received_on" type="date" value-format="YYYY-MM-DD" :disabled-date="futureDate" style="width:100%" /></el-form-item>
        <el-form-item label="同学 / 付款人"><el-input v-model="createForm.customer" maxlength="100" placeholder="例如：小王" /></el-form-item>
        <el-form-item label="流水号"><el-input v-model="createForm.reference" maxlength="100" placeholder="平台请填券码，用于识别重复登记" /></el-form-item>
        <el-form-item label="备注"><el-input v-model="createForm.remark" type="textarea" maxlength="500" show-word-limit placeholder="例如：9 月月卡" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="createVisible = false">取消</el-button><el-button type="primary" :loading="saving" @click="saveReceipt">保存收款</el-button></template>
    </el-dialog>

    <el-dialog v-model="refundVisible" title="登记已完成退款" width="min(520px, 94vw)" :close-on-click-modal="false">
      <el-alert title="请先在实际收款渠道完成退款，再来登记。本操作只记账，不会自动退钱。" type="info" show-icon :closable="false" />
      <p>原收款 #{{ activeReceipt?.id }} · {{ activeReceipt?.customer || '未填写付款人' }}<br />收款 ¥{{ money(activeReceipt?.amount) }}，剩余可登记退款 ¥{{ money(activeReceipt?.remaining) }}</p>
      <el-form label-width="90px" @submit.prevent="saveRefund">
        <el-form-item label="退款金额" required><el-input-number v-model="refundForm.amount" :min="0.01" :max="Number(activeReceipt?.remaining || 0)" :precision="2" style="width:100%" /></el-form-item>
        <el-form-item label="退款日期" required><el-date-picker v-model="refundForm.refunded_on" type="date" value-format="YYYY-MM-DD" :disabled-date="invalidRefundDate" style="width:100%" /></el-form-item>
        <el-form-item label="退款原因" required><el-input v-model="refundForm.reason" type="textarea" maxlength="500" show-word-limit /></el-form-item>
        <el-form-item><el-checkbox v-model="refundForm.completed">我确认这笔钱已经实际退给同学</el-checkbox></el-form-item>
      </el-form>
      <template #footer><el-button @click="refundVisible = false">取消</el-button><el-button type="primary" :loading="saving" :disabled="!refundForm.completed" @click="saveRefund">保存退款记录</el-button></template>
    </el-dialog>

    <el-dialog v-model="platformVisible" title="核对平台核销入账" width="min(540px, 94vw)" :close-on-click-modal="false">
      <el-alert :title="activePlatform?.reason || '请核对本次核销金额'" type="warning" show-icon :closable="false" />
      <p>{{ activePlatform?.deal_name }} · {{ activePlatform?.reference }}<br />参考价：{{ activePlatform?.reference_price === null ? '无' : `¥${money(activePlatform?.reference_price)}` }}（不会自动用作入账金额）</p>
      <el-form label-width="120px" @submit.prevent="savePlatform">
        <el-form-item label="渠道" required><el-select v-model="platformForm.channel" :disabled="!!activePlatform?.channel"><el-option label="美团" value="meituan" /><el-option label="抖音" value="douyin" /></el-select></el-form-item>
        <el-form-item label="确认金额（元）" required><el-input-number v-model="platformForm.amount" :min="0.01" :max="99999999.99" :precision="2" /></el-form-item>
        <el-form-item label="核销入账日期" required><el-date-picker v-model="platformForm.received_on" type="date" value-format="YYYY-MM-DD" :disabled-date="futureDate" /></el-form-item>
        <el-form-item label="原收款编号"><el-input-number v-model="platformForm.existing_receipt_id" :min="1" :precision="0" :disabled="!!activePlatform?.existing_receipt_id" placeholder="未记过账则留空" /></el-form-item>
        <p class="muted">已经手工记账时填写原收款编号，仅建立关联，不增加收入；渠道、金额、日期必须与原记录一致。</p>
        <el-form-item><el-checkbox v-model="platformForm.confirmed">已核对本次核销金额及是否重复记账</el-checkbox></el-form-item>
      </el-form>
      <template #footer><el-button @click="platformVisible = false">取消</el-button><el-button type="primary" :loading="saving" :disabled="!platformForm.confirmed" @click="savePlatform">确认入账 / 关联</el-button></template>
    </el-dialog>

    <el-dialog v-model="dateVisible" title="补全实际收款日期" width="min(460px, 94vw)" :close-on-click-modal="false">
      <p>订单 {{ activeReceipt?.reference }} 未保存支付时间。请核对支付账单，填写实际收款日期，保存后纳入该月和该年统计。</p>
      <el-date-picker v-model="confirmedDate" type="date" value-format="YYYY-MM-DD" :disabled-date="futureDate" placeholder="请选择实际收款日期" />
      <template #footer><el-button @click="dateVisible = false">取消</el-button><el-button type="primary" :loading="saving" @click="saveDate">确认日期</el-button></template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import http from '../api/http'

type Channel = 'meituan' | 'douyin' | 'wechat_pay' | 'wechat_transfer'
type ManualChannel = Exclude<Channel, 'wechat_pay'>
type Totals = { received: string; refunded: string; net: string }
type Summary = { month: Totals; year: Totals; channels: (Totals & { channel: Channel })[]; missing_dates: number; refunds_to_review: number; platforms_to_review: number }
type PlatformReceipt = { id: number; channel: 'meituan' | 'douyin' | null; amount: string | null; reference_price: string | null; received_on: string | null; reference: string; customer: string; deal_name: string; reason: string; existing_receipt_id: number | null }
type Receipt = { id: number; channel: Channel; amount: string; refunded_amount: string; remaining: string; received_on: string | null; customer: string; reference: string; remark: string; automatic: boolean; refund_needs_review: boolean }
type Refund = { id: number; receipt_id: number; channel: Channel; amount: string; refunded_on: string; reason: string; customer: string; reference: string }
const channels: Record<Channel, string> = { meituan: '美团', douyin: '抖音', wechat_pay: '小程序微信支付', wechat_transfer: '微信转账' }
const manualChannels: ManualChannel[] = ['meituan', 'douyin', 'wechat_transfer']
function chinaDate() {
  const parts = new Intl.DateTimeFormat('en-US', { timeZone: 'Asia/Shanghai', year: 'numeric', month: '2-digit', day: '2-digit' }).formatToParts(new Date())
  const part = (key: string) => parts.find(p => p.type === key)!.value
  return `${part('year')}-${part('month')}-${part('day')}`
}
const nowYear = Number(chinaDate().slice(0, 4)), nowMonth = Number(chinaDate().slice(5, 7))
const filters = reactive({ year: nowYear, month: nowMonth, channel: '' as Channel | '' })
const applied = reactive({ ...filters })
const currentSummary = ref<Summary>(), selectedSummary = ref<Summary>()
const initialLoading = ref(true), refreshing = ref(false), loading = ref(false), listLoading = ref(false), saving = ref(false), reconciling = ref(false)
const error = ref(''), tab = ref('receipts'), keyword = ref(''), appliedKeyword = ref(''), page = ref(1), total = ref(0)
const review = ref<'' | 'date' | 'refund'>('')
const receipts = ref<Receipt[]>([]), refunds = ref<Refund[]>([])
const platforms = ref<PlatformReceipt[]>([]), activePlatform = ref<PlatformReceipt>(), platformVisible = ref(false)
const platformForm = reactive({ channel: '' as 'meituan' | 'douyin' | '', amount: undefined as number | undefined, received_on: '', existing_receipt_id: undefined as number | undefined, confirmed: false })
const createVisible = ref(false), refundVisible = ref(false), dateVisible = ref(false)
const activeReceipt = ref<Receipt>(), confirmedDate = ref('')
function requestId() {
  const bytes = crypto.getRandomValues(new Uint8Array(16))
  bytes[6] = (bytes[6] & 15) | 64; bytes[8] = (bytes[8] & 63) | 128
  const hex = Array.from(bytes, b => b.toString(16).padStart(2, '0')).join('')
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`
}
const createForm = reactive({ channel: 'wechat_transfer' as ManualChannel, amount: undefined as number | undefined, received_on: chinaDate(), customer: '', reference: '', remark: '', request_id: '' })
const refundForm = reactive({ amount: undefined as number | undefined, refunded_on: chinaDate(), reason: '', completed: false, request_id: '' })
const periodLabel = computed(() => `${applied.year} 年${applied.month ? ` ${applied.month} 月` : '全年'}`)
const cards = computed(() => [
  { label: '本月收款', value: currentSummary.value?.month.received },
  { label: '本月退款', value: currentSummary.value?.month.refunded },
  { label: '本月净收款', value: currentSummary.value?.month.net, net: true },
  { label: '今年收款', value: currentSummary.value?.year.received },
  { label: '今年退款', value: currentSummary.value?.year.refunded },
  { label: '今年净收款', value: currentSummary.value?.year.net, net: true },
])
function money(value?: string) { return value === undefined ? '—' : Number(value).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) }
function dateOf(value: Date) { return `${value.getFullYear()}-${String(value.getMonth() + 1).padStart(2, '0')}-${String(value.getDate()).padStart(2, '0')}` }
function futureDate(value: Date) { return dateOf(value) > chinaDate() }
function invalidRefundDate(value: Date) { return futureDate(value) || dateOf(value) < (activeReceipt.value?.received_on || '') }
function message(err: any) {
  const detail = err?.response?.data?.detail
  return typeof detail === 'string' ? detail : Array.isArray(detail) ? detail.map((d: any) => d.msg).join('；') : err?.message || '请求失败，请重试'
}
function params() { return { year: applied.year, month: applied.month || undefined, channel: applied.channel || undefined } }
let summaryRequest = 0, listRequest = 0
async function loadSummary() {
  const id = ++summaryRequest
  loading.value = true
  try {
    const result = await http.get<Summary>('/admin/receipts/summary', { params: params() })
    if (id === summaryRequest) selectedSummary.value = result.data
  } finally { if (id === summaryRequest) loading.value = false }
}
async function loadCurrent() {
  const today = chinaDate()
  currentSummary.value = (await http.get<Summary>('/admin/receipts/summary', { params: { year: Number(today.slice(0, 4)), month: Number(today.slice(5, 7)) } })).data
}
async function loadList() {
  const id = ++listRequest, currentTab = tab.value
  listLoading.value = true
  try {
    if (currentTab === 'platforms') {
      const result = await http.get<{ items: PlatformReceipt[]; total: number }>('/admin/receipts/platform-review', { params: { page: page.value, page_size: 20 } })
      if (id === listRequest) { platforms.value = result.data.items; total.value = result.data.total }
      return
    }
    const query = { ...(review.value ? {} : params()), page: page.value, page_size: 20, keyword: appliedKeyword.value || undefined, needs_date: review.value === 'date', needs_refund: review.value === 'refund' }
    const result = await http.get<{ items: Receipt[] | Refund[]; total: number }>(currentTab === 'receipts' ? '/admin/receipts' : '/admin/receipts/refunds', { params: query })
    if (id !== listRequest) return
    if (currentTab === 'receipts') receipts.value = result.data.items as Receipt[]
    else refunds.value = result.data.items as Refund[]
    total.value = result.data.total
  } catch (err) {
    if (id === listRequest) { receipts.value = []; refunds.value = []; platforms.value = []; total.value = 0; error.value = message(err) }
  } finally { if (id === listRequest) listLoading.value = false }
}
async function refresh() {
  if (refreshing.value) return
  refreshing.value = true; error.value = ''
  try {
    await http.post('/admin/receipts/sync')
    await Promise.all([loadCurrent(), loadSummary(), loadList()])
  } catch (err) { error.value = message(err) }
  finally { refreshing.value = false; initialLoading.value = false }
}
async function search() {
  if (!filters.year) { ElMessage.warning('请选择年份'); return }
  Object.assign(applied, filters); review.value = ''; page.value = 1; error.value = ''
  selectedSummary.value = undefined
  try { await Promise.all([loadSummary(), loadList()]) } catch (err) { error.value = message(err) }
}
function reset() { Object.assign(filters, { year: Number(chinaDate().slice(0, 4)), month: Number(chinaDate().slice(5, 7)), channel: '' }); keyword.value = ''; appliedKeyword.value = ''; void search() }
function searchList() { appliedKeyword.value = keyword.value.trim(); page.value = 1; void loadList() }
function changeTab() { if (tab.value !== 'receipts') review.value = ''; page.value = 1; void loadList() }
function showPlatformReview() { tab.value = 'platforms'; review.value = ''; page.value = 1; void loadList() }
async function bulkReconcile() {
  if (reconciling.value) return
  try { await ElMessageBox.confirm('将先关联已有手工登记，再用参考价把渠道/日期/金额齐全的核销批量入账。其余保持待核对。', '一键核对', { confirmButtonText: '继续', cancelButtonText: '取消', type: 'warning' }) } catch { return }
  reconciling.value = true
  try {
    const res = await http.post<{ linked: number; inserted: number; skipped: number }>('/admin/receipts/platform-review/bulk-reconcile')
    ElMessage.success(`关联 ${res.data.linked} 笔，入账 ${res.data.inserted} 笔，跳过 ${res.data.skipped} 笔`)
    await refresh()
  } catch (err) { ElMessage.error(message(err)) } finally { reconciling.value = false }
}
function openPlatform(row: PlatformReceipt) {
  activePlatform.value = row
  Object.assign(platformForm, { channel: row.channel || '', amount: row.amount === null ? undefined : Number(row.amount), received_on: row.received_on || '', existing_receipt_id: row.existing_receipt_id || undefined, confirmed: false })
  platformVisible.value = true
}
async function savePlatform() {
  if (saving.value || !activePlatform.value) return
  if (!platformForm.channel || !platformForm.amount || !platformForm.received_on || !platformForm.confirmed) { ElMessage.warning('请核对渠道、金额、日期并勾选确认'); return }
  saving.value = true
  try { await http.post(`/admin/receipts/platform-review/${activePlatform.value.id}/confirm`, { ...platformForm, amount: platformForm.amount.toFixed(2) }); platformVisible.value = false; ElMessage.success('核销已关联收款'); await refresh() }
  catch (err) { ElMessage.error(message(err)) } finally { saving.value = false }
}
function clearReview() { review.value = ''; page.value = 1; void loadList() }
function showReview(kind: 'date' | 'refund') { tab.value = 'receipts'; review.value = kind; keyword.value = ''; appliedKeyword.value = ''; page.value = 1; void loadList() }
function openCreate() { Object.assign(createForm, { channel: 'wechat_transfer', amount: undefined, received_on: chinaDate(), customer: '', reference: '', remark: '', request_id: requestId() }); createVisible.value = true }
function openRefund(row: Receipt) { activeReceipt.value = row; Object.assign(refundForm, { amount: undefined, refunded_on: chinaDate(), reason: '', completed: false, request_id: requestId() }); refundVisible.value = true }
function openDate(row: Receipt) { activeReceipt.value = row; confirmedDate.value = ''; dateVisible.value = true }
async function saveReceipt() {
  if (saving.value) return
  if (!createForm.amount || !createForm.received_on) { ElMessage.warning('请填写金额和收款日期'); return }
  saving.value = true
  try { await http.post('/admin/receipts', { ...createForm, amount: createForm.amount.toFixed(2) }); createVisible.value = false; ElMessage.success('收款已登记'); await refresh() }
  catch (err) { ElMessage.error(message(err)) } finally { saving.value = false }
}
async function saveRefund() {
  if (saving.value || !activeReceipt.value) return
  if (!refundForm.amount || !refundForm.refunded_on || !refundForm.reason.trim() || !refundForm.completed) { ElMessage.warning('请填写退款金额、日期、原因并确认已完成退款'); return }
  saving.value = true
  try { await http.post(`/admin/receipts/${activeReceipt.value.id}/refunds`, { ...refundForm, amount: refundForm.amount.toFixed(2) }); refundVisible.value = false; ElMessage.success('已登记退款，不会再次转账'); await refresh() }
  catch (err) { ElMessage.error(message(err)) } finally { saving.value = false }
}
async function saveDate() {
  if (saving.value || !activeReceipt.value) return
  if (!confirmedDate.value) { ElMessage.warning('请选择实际收款日期'); return }
  saving.value = true
  try { await http.patch(`/admin/receipts/${activeReceipt.value.id}/date`, { received_on: confirmedDate.value }); dateVisible.value = false; ElMessage.success('收款日期已补全'); await refresh() }
  catch (err) { ElMessage.error(message(err)) } finally { saving.value = false }
}
onMounted(refresh)
</script>

<style scoped>
.receipts { display: flex; flex-direction: column; gap: 18px; }
.heading { display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 12px; }
h2 { font-size: 22px; margin: 0 0 8px; }
.heading p, .muted, .footnote { color: #73767a; font-size: 13px; }
.heading p { margin: 0; }
.actions { display: flex; flex-wrap: wrap; gap: 8px; }
.actions .el-button + .el-button { margin-left: 0; }
.metrics { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 14px; }
.metric-label { font-size: 14px; color: #606266; margin-bottom: 12px; }
.metric-value { font-size: clamp(20px, 2.2vw, 30px); font-weight: 650; font-variant-numeric: tabular-nums; overflow-wrap: anywhere; }
.net-card { border-top: 3px solid #e6b800; background: #fffcf1; }
.review-notice { display: flex; align-items: center; flex-wrap: wrap; gap: 10px; padding: 12px 16px; background: #fdf6ec; border-radius: 6px; font-size: 13px; color: #8a5a15; }
.filters .el-form-item { margin-bottom: 12px; }
.period-summary { display: flex; flex-wrap: wrap; gap: 12px 24px; padding: 12px 0 20px; font-size: 14px; }
.period-summary b { font-variant-numeric: tabular-nums; }
.list-tools { display: flex; flex-wrap: wrap; align-items: center; gap: 10px; margin-bottom: 16px; }
.pager { display: flex; justify-content: flex-end; margin-top: 18px; }
.footnote { margin: 0; line-height: 1.8; }
@media (max-width: 700px) { .metrics { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
</style>
