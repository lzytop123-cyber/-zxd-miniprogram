<template>
  <el-card class="page-card" shadow="never">
    <template #header>
      <div class="header-row">
        <span>预约订单</span>
        <div>
          <el-button type="primary" @click="openCreate">代同学预约</el-button>
          <el-button @click="load">刷新</el-button>
        </div>
      </div>
    </template>

    <!-- 手机端快捷搜索栏 -->
    <div v-if="isMobile" class="m-filter-bar">
      <el-input
        v-model="filters.keyword"
        placeholder="手机 / 昵称 / 订单号"
        clearable
        @keyup.enter="search"
        @clear="search"
      />
      <el-input
        v-model="filters.seat_code"
        placeholder="座位"
        clearable
        class="m-seat-input"
        @keyup.enter="search"
        @clear="search"
      />
      <el-button type="primary" @click="search">查</el-button>
      <el-button @click="showMobileFilters = !showMobileFilters">
        {{ showMobileFilters ? '收起' : '筛选' }}
      </el-button>
    </div>

    <el-form v-show="!isMobile || showMobileFilters" inline class="filters" @submit.prevent>
      <el-form-item v-if="!isMobile" label="搜索">
        <el-input
          v-model="filters.keyword"
          placeholder="手机号 / 昵称 / 订单号"
          clearable
          style="width:200px"
          @keyup.enter="search"
        />
      </el-form-item>
      <el-form-item v-if="!isMobile" label="座位">
        <el-input
          v-model="filters.seat_code"
          placeholder="座位号，如 18 / A01"
          clearable
          style="width:140px"
          @keyup.enter="search"
          @clear="search"
        />
      </el-form-item>
      <el-form-item label="用户ID">
        <el-input-number v-model="filters.user_id" :min="1" controls-position="right" style="width:110px" />
      </el-form-item>
      <el-form-item label="门店">
        <el-select v-model="filters.store_id" clearable placeholder="全部" style="width:130px" @change="reloadForStore">
          <el-option v-for="s in stores" :key="s.id" :label="s.name" :value="s.id" />
        </el-select>
      </el-form-item>
      <el-form-item label="支付">
        <el-select v-model="filters.pay_status" clearable placeholder="全部" style="width:100px">
          <el-option label="待付款" :value="0" />
          <el-option label="已付款" :value="1" />
          <el-option label="已退款" :value="2" />
          <el-option label="退款待确认" value="refund_pending" />
        </el-select>
      </el-form-item>
      <el-form-item label="状态">
        <el-select v-model="filters.status" clearable placeholder="全部" style="width:100px">
          <el-option label="已预约" :value="0" />
          <el-option label="使用中" :value="1" />
          <el-option label="已完成" :value="2" />
          <el-option label="已取消" :value="3" />
        </el-select>
      </el-form-item>
      <el-form-item>
        <el-button type="primary" @click="search">查询</el-button>
        <el-button @click="filterUnpaid">待付款</el-button>
        <el-button @click="reset">重置</el-button>
      </el-form-item>
    </el-form>

    <el-alert
      v-if="!isMobile"
      type="info"
      :closable="true"
      show-icon
      title="预约时段内自动入座；到店开门也会标为使用中。已付款订单可在本页换座。"
      class="tip"
    />

    <!-- 手机端卡片列表 -->
    <div v-if="isMobile" v-loading="loading" class="m-card-list">
      <div v-for="row in list" :key="row.id" class="m-card">
        <div class="m-card-head">
          <div>
            <div class="m-card-title">
              {{ row.user_nickname || '同学' }}
              <span class="m-seat-badge" v-if="row.seat_code">{{ row.seat_code }}</span>
            </div>
            <div class="m-card-sub">ID {{ row.user_id }} · {{ row.store_name || '-' }}</div>
          </div>
          <div class="m-card-tags">
            <el-tag :type="row.pay_status === 1 ? 'success' : row.pay_status === 2 ? 'info' : 'warning'" size="small">
              {{ refundLabels[row.refund_state] || ['待付', '已付', '退款'][row.pay_status] || row.pay_status }}
            </el-tag>
            <el-tag :type="statusTagType(row.status)" size="small">
              {{ row.status_label || statusLabel(row.status) }}
            </el-tag>
            <el-tag v-if="row.on_leave_today" type="warning" effect="dark" size="small">请假中</el-tag>
          </div>
        </div>
        <div class="m-card-grid">
          <div class="m-card-field">
            <span class="k">套餐 / 金额</span>
            <span class="v">{{ row.usage_label || row.bill_type_label || billLabel(row.bill_type) }} · <b>{{ priceText(row) }}</b></span>
          </div>
          <div class="m-card-field">
            <span class="k">来源</span>
            <span class="v">{{ row.pay_source_label || payTypeLabel(row.pay_type) }}</span>
          </div>
          <div class="m-card-field full">
            <span class="k">预约时段</span>
            <span class="v tnum">{{ formatTime(row.start_time) }} 至 {{ formatTime(row.end_time) }}</span>
          </div>
          <div class="m-card-field" v-if="row.check_in_time">
            <span class="k">入座时间</span>
            <span class="v tnum">{{ formatTime(row.check_in_time) }}</span>
          </div>
          <div class="m-card-field full">
            <span class="k">订单号</span>
            <span class="v tnum">{{ row.order_no }}</span>
          </div>
        </div>
        <div
          v-if="canRemoteUnlock(row) || canChangeSeat(row) || canManageLeave(row) || row.status === 1 || canCancel(row) || row.refund_state === 'pending' || (row.pay_status === 1 && row.refund_state !== 'pending')"
          class="m-card-actions"
        >
          <el-button
            v-if="canRemoteUnlock(row) && !row.on_leave_today"
            size="small"
            type="success"
            plain
            :loading="unlockingIds.has(row.id)"
            @click="remoteUnlock(row)"
          >远程开门</el-button>
          <el-button
            v-if="canManageLeave(row)"
            size="small"
            type="warning"
            plain
            @click="openLeave(row)"
          >请假 ({{ row.leave_used || 0 }}/{{ row.leave_limit || 3 }})</el-button>
          <el-button
            v-if="canChangeSeat(row)"
            size="small"
            type="primary"
            plain
            @click="openChangeSeat(row)"
          >换座</el-button>
          <el-button
            v-if="row.status === 1"
            size="small"
            type="warning"
            plain
            @click="forceCheckout(row)"
          >强制离座</el-button>
          <el-button
            v-if="row.refund_state === 'pending'"
            size="small"
            type="warning"
            plain
            :loading="retryingRefunds.has(row.id)"
            @click="retryRefund(row)"
          >重试退款</el-button>
          <el-button
            v-if="row.pay_status === 1 && row.refund_state !== 'pending'"
            size="small"
            plain
            @click="openRefund(row)"
          >登记退款</el-button>
          <el-button
            v-if="canCancel(row)"
            size="small"
            type="danger"
            plain
            @click="cancelOrder(row)"
          >取消</el-button>
        </div>
      </div>
      <div v-if="!loading && !list.length" class="m-empty">暂无预约订单</div>
    </div>

    <el-table
      v-else
      :data="list"
      v-loading="loading"
      stripe
      size="small"
      border
      :max-height="tableMaxHeight"
      class="order-table"
    >
      <el-table-column prop="order_no" label="订单号" width="158" :fixed="isMobile ? false : true" />
      <el-table-column label="用户" width="108">
        <template #default="{ row }">
          <div class="cell-main">{{ row.user_nickname || '-' }}</div>
          <div class="sub">ID {{ row.user_id }}</div>
        </template>
      </el-table-column>
      <el-table-column prop="store_name" label="门店" width="100" show-overflow-tooltip />
      <el-table-column label="座位" width="88">
        <template #default="{ row }">
          <div class="cell-main">{{ row.seat_code || '-' }}</div>
          <div v-if="row.zone_name" class="sub">{{ row.zone_name }}</div>
        </template>
      </el-table-column>
      <el-table-column label="套餐" min-width="100" show-overflow-tooltip>
        <template #default="{ row }">{{ row.usage_label || row.bill_type_label || billLabel(row.bill_type) }}</template>
      </el-table-column>
      <el-table-column label="来源" width="96" show-overflow-tooltip>
        <template #default="{ row }">{{ row.pay_source_label || payTypeLabel(row.pay_type) }}</template>
      </el-table-column>
      <el-table-column label="金额" width="86">
        <template #default="{ row }">{{ priceText(row) }}</template>
      </el-table-column>
      <el-table-column label="支付" width="78">
        <template #default="{ row }">
          <el-tag :type="row.pay_status === 1 ? 'success' : row.pay_status === 2 ? 'info' : 'warning'" size="small">
            {{ refundLabels[row.refund_state] || ['待付', '已付', '退款'][row.pay_status] || row.pay_status }}
          </el-tag>
          <div v-if="row.refund_remark" class="sub">{{ row.refund_remark }}</div>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="92">
        <template #default="{ row }">
          <el-tag :type="statusTagType(row.status)" size="small">
            {{ row.status_label || statusLabel(row.status) }}
          </el-tag>
          <div v-if="row.on_leave_today" style="margin-top:4px">
            <el-tag type="warning" effect="dark" size="small">请假中</el-tag>
          </div>
        </template>
      </el-table-column>
      <el-table-column label="预约时段" width="148">
        <template #default="{ row }">
          <div>{{ formatTime(row.start_time) }}</div>
          <div class="sub">至 {{ formatTime(row.end_time) }}</div>
        </template>
      </el-table-column>
      <el-table-column label="入座" width="132" show-overflow-tooltip>
        <template #default="{ row }">{{ formatTime(row.check_in_time) }}</template>
      </el-table-column>
      <el-table-column label="说明" min-width="120" show-overflow-tooltip>
        <template #default="{ row }">{{ row.status_hint || '-' }}</template>
      </el-table-column>
      <el-table-column label="操作" width="280" :fixed="isMobile ? false : 'right'">
        <template #default="{ row }">
          <el-button
            v-if="canRemoteUnlock(row) && !row.on_leave_today"
            link
            type="success"
            :loading="unlockingIds.has(row.id)"
            @click="remoteUnlock(row)"
          >远程开门</el-button>
          <el-button
            v-if="canManageLeave(row)"
            link
            type="warning"
            @click="openLeave(row)"
          >请假({{ row.leave_used || 0 }}/{{ row.leave_limit || 3 }})</el-button>
          <el-button
            v-if="canChangeSeat(row)"
            link
            type="primary"
            @click="openChangeSeat(row)"
          >换座</el-button>
          <el-button
            v-if="row.status === 1"
            link
            type="warning"
            @click="forceCheckout(row)"
          >强制离座</el-button>
          <el-button
            v-if="canCancel(row)"
            link
            type="danger"
            @click="cancelOrder(row)"
          >取消</el-button>
          <el-button
            v-if="row.refund_state === 'pending'"
            link
            type="warning"
            :loading="retryingRefunds.has(row.id)"
            @click="retryRefund(row)"
          >重试退款</el-button>
          <el-button
            v-if="row.pay_status === 1 && row.refund_state !== 'pending'"
            link
            type="info"
            @click="openRefund(row)"
          >登记退款</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="changeSeatVisible" title="换座" width="820px" destroy-on-close @closed="resetChangeSeat">
      <div v-if="changeSeatRow" class="change-seat-meta">
        <div>订单 <strong>{{ changeSeatRow.order_no }}</strong> · {{ changeSeatRow.user_nickname || '同学' }} ID {{ changeSeatRow.user_id }}</div>
        <div class="sub">
          当前座位 <strong>{{ seatOptions.current_seat_code || changeSeatRow.seat_code }}</strong>
          · {{ formatTime(seatOptions.start_time) }} 至 {{ formatTime(seatOptions.end_time) }}
        </div>
      </div>
      <el-alert v-if="seatOptions.hint" type="info" :closable="false" show-icon :title="seatOptions.hint" class="tip" />
      <div class="seat-legend">
        <span><i class="dot current"></i>当前</span>
        <span><i class="dot free"></i>空座</span>
        <span><i class="dot swap"></i>可对调</span>
        <span><i class="dot busy"></i>占用</span>
        <span><i class="dot off"></i>停用</span>
      </div>
      <div v-loading="seatOptionsLoading" class="floor-map">
        <div
          v-for="s in mappedSeats"
          :key="s.id"
          class="map-seat"
          :class="seatClass(s)"
          :style="mapSeatStyle(s)"
          :title="seatTitle(s)"
          @click="pickSeat(s)"
        >
          {{ s.seat_code }}
        </div>
      </div>
      <el-select
        v-if="!seatOptionsLoading && !mappedSeats.length && seatOptions.seats.length"
        v-model="changeSeatTargetId"
        filterable
        placeholder="选择座位"
        style="width:100%;margin-top:8px"
      >
        <el-option
          v-for="s in seatOptions.seats"
          :key="s.id"
          :label="`${s.seat_code} · ${s.zone_name}${s.reason ? '（' + s.reason + '）' : ''}`"
          :value="s.id"
          :disabled="!s.selectable && !s.can_swap"
        />
      </el-select>
      <div v-if="selectedSeat" class="seat-picked">
        <template v-if="selectedSeat.can_swap && selectedSeat.occupied_by">
          将与 <strong>{{ selectedSeat.occupied_by.nickname }}</strong>
          （ID {{ selectedSeat.occupied_by.user_id }} · {{ selectedSeat.seat_code }} · {{ selectedSeat.occupied_by.end_label }}）对调
        </template>
        <template v-else>
          换到空座 <strong>{{ selectedSeat.seat_code }}</strong>
          <span v-if="selectedSeat.zone_name"> · {{ selectedSeat.zone_name }}</span>
        </template>
      </div>
      <div v-else class="sub" style="margin-top:10px">点击空座换座，或点击橙色座位与对方对调。</div>
      <template #footer>
        <el-button @click="changeSeatVisible = false">取消</el-button>
        <el-button type="primary" :loading="changeSeatSubmitting" :disabled="!changeSeatTargetId" @click="submitChangeSeat">
          {{ selectedSeat?.can_swap ? '确认对调' : '确认换座' }}
        </el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="createVisible" title="代同学预约" width="640px" destroy-on-close @closed="resetCreate">
      <el-form label-width="88px">
        <el-form-item label="同学">
          <div class="create-user-row">
            <el-input v-model="createForm.keyword" placeholder="学号或手机号" clearable @keyup.enter="searchUser" />
            <el-button type="primary" :loading="userSearching" @click="searchUser">搜索</el-button>
          </div>
          <div v-if="createForm.user" class="create-user-picked">
            {{ createForm.user.nickname || '未设置昵称' }} · ID {{ createForm.user.id }}
            <span v-if="createForm.user.phone"> · {{ createForm.user.phone }}</span>
          </div>
        </el-form-item>
        <el-form-item label="门店">
          <el-select v-model="createForm.store_id" placeholder="选择门店" style="width:100%" @change="clearPreview">
            <el-option v-for="s in stores" :key="s.id" :label="s.name" :value="s.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="套餐">
          <el-select v-model="createForm.bill_type" style="width:100%" @change="clearPreview">
            <el-option v-for="item in createBillTypes" :key="item.value" :label="item.label" :value="item.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="开始">
          <el-date-picker
            v-model="createForm.start_time"
            type="datetime"
            placeholder="开始时间"
            format="YYYY-MM-DD HH:mm"
            value-format="YYYY-MM-DDTHH:mm:ss"
            style="width:100%"
            @change="clearPreview"
          />
        </el-form-item>
        <el-form-item label="结束">
          <el-date-picker
            v-model="createForm.end_time"
            type="datetime"
            placeholder="可空：按套餐自动算"
            format="YYYY-MM-DD HH:mm"
            value-format="YYYY-MM-DDTHH:mm:ss"
            style="width:100%"
            @change="clearPreview"
          />
        </el-form-item>
        <el-form-item>
          <el-button :loading="previewLoading" @click="previewCreate">预览价格和空座</el-button>
        </el-form-item>
        <template v-if="createPreview">
          <el-form-item label="时段">
            <span>{{ formatTime(createPreview.start_time) }} 至 {{ formatTime(createPreview.end_time) }}</span>
          </el-form-item>
          <el-form-item label="系统价">¥{{ createPreview.original_price }}</el-form-item>
          <el-form-item label="座位">
            <el-select v-model="createForm.seat_id" filterable placeholder="选择空座" style="width:100%">
              <el-option
                v-for="s in createPreview.seats"
                :key="s.id"
                :label="`${s.seat_code}${s.zone_name ? ' · ' + s.zone_name : ''}${s.available ? '' : '（已被占）'}`"
                :value="s.id"
                :disabled="!s.available"
              />
            </el-select>
          </el-form-item>
          <el-form-item label="实收金额">
            <el-input-number v-model="createForm.final_price" :min="0" :precision="2" :step="1" />
            <el-button link type="primary" @click="createForm.final_price = 0">免单</el-button>
          </el-form-item>
        </template>
      </el-form>
      <template #footer>
        <el-button @click="createVisible = false">取消</el-button>
        <el-button type="primary" :loading="createSubmitting" :disabled="!canSubmitCreate" @click="submitCreate">
          确认预约（前台收款）
        </el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="refundVisible" title="登记退款" width="420px">
      <p v-if="refundRow" class="sub">{{ reservationStoreName(refundRow) }} · 订单 {{ refundRow.order_no }} · ¥{{ refundRow.final_price ?? 0 }}</p>
      <el-input v-model="refundRemark" type="textarea" :rows="3" placeholder="退款原因/备注（人工登记，非微信自动退款）" />
      <template #footer>
        <el-button @click="refundVisible = false">取消</el-button>
        <el-button type="primary" :loading="refundSubmitting" @click="submitRefund">确认登记</el-button>
      </template>
    </el-dialog>

    <!-- 月卡请假弹窗 -->
    <el-dialog v-model="leaveVisible" title="月卡请假 / 顺延管理" width="560px" destroy-on-close @closed="resetLeave">
      <div v-loading="leaveLoading">
        <div v-if="leaveRow" class="leave-meta">
          <div>
            订单 <strong>{{ leaveRow.order_no }}</strong> · {{ leaveRow.user_nickname || '同学' }} · 座位 <strong>{{ leaveRow.seat_code || '-' }}</strong>
          </div>
          <div class="sub">
            当前预约期：{{ leaveInfo.start_time || formatTime(leaveRow.start_time) }} 至 {{ leaveInfo.end_time || formatTime(leaveRow.end_time) }}
            · 已请假 <strong>{{ leaveInfo.used_count }}/{{ leaveInfo.limit }}</strong> 次
          </div>
        </div>

        <template v-if="leaveInfo.eligible && leaveInfo.used_count < leaveInfo.limit">
          <div class="leave-section-title">办理新请假（方案 A：释放请假期间座位，结束日期按天顺延）</div>
          <el-form label-width="96px">
            <el-form-item label="开始日期">
              <el-date-picker
                v-model="leaveForm.start_date"
                type="date"
                value-format="YYYY-MM-DD"
                placeholder="选择请假开始日"
                style="width:100%"
                @change="clearLeavePreview"
              />
            </el-form-item>
            <el-form-item label="结束日期">
              <el-date-picker
                v-model="leaveForm.end_date"
                type="date"
                value-format="YYYY-MM-DD"
                placeholder="选择请假结束日（含当天）"
                style="width:100%"
                @change="clearLeavePreview"
              />
            </el-form-item>
            <el-form-item label="请假原因">
              <el-input v-model="leaveForm.reason" placeholder="可选，如回家/生病/出差" maxlength="200" />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" plain :loading="leavePreviewLoading" @click="previewLeave">
                检测顺延与座位
              </el-button>
            </el-form-item>

            <template v-if="leavePreview">
              <el-alert
                :type="leavePreview.original_seat_available ? 'success' : 'warning'"
                :closable="false"
                show-icon
                class="tip"
                :title="`本次请假 ${leavePreview.days} 天，结束时间顺延至 ${leavePreview.new_end_time}`"
                :description="
                  leavePreview.original_seat_available
                    ? `原座位 ${leavePreview.original_seat_code} 在顺延时段空闲，将自动沿用原座。`
                    : `原座位 ${leavePreview.original_seat_code} 在顺延时段已被订单 ${leavePreview.conflict_order_no} 占用，请在下方选择同店替代座位。`
                "
              />
              <el-form-item v-if="!leavePreview.original_seat_available" label="替代座位" required>
                <el-select
                  v-model="leaveForm.target_seat_id"
                  placeholder="请选择同店可用座位"
                  filterable
                  style="width:100%"
                >
                  <el-option
                    v-for="s in leavePreview.alternative_seats"
                    :key="s.id"
                    :label="`${s.seat_code}${s.zone_name ? ' · ' + s.zone_name : ''}`"
                    :value="s.id"
                  />
                </el-select>
                <div v-if="!leavePreview.alternative_seats.length" class="sub" style="color:#dc2626;margin-top:4px">
                  顺延时段该门店暂无全时段空闲替代座，需先协调排座后再办理。
                </div>
              </el-form-item>
            </template>
          </el-form>
        </template>
        <el-alert
          v-else-if="!leaveLoading"
          type="info"
          :closable="false"
          show-icon
          class="tip"
          :title="leaveInfo.used_count >= leaveInfo.limit ? `该月卡已用完 ${leaveInfo.limit} 次请假额度` : '当前订单状态不可新增请假'"
        />

        <div class="leave-section-title">请假记录</div>
        <div v-if="leaveInfo.leaves.length" class="leave-list">
          <div v-for="lv in leaveInfo.leaves" :key="lv.id" class="leave-item">
            <div class="leave-item-main">
              <div>
                <strong>{{ lv.start_date }} 至 {{ lv.end_date }}</strong>
                <span class="sub">（{{ lv.days }} 天）</span>
                <el-tag :type="lv.status === 'active' ? (lv.is_ongoing ? 'warning' : 'success') : 'info'" size="small" style="margin-left:6px">
                  {{ lv.status === 'cancelled' ? '已撤销' : lv.is_ongoing ? '请假中' : '生效中' }}
                </el-tag>
              </div>
              <div class="sub">
                顺延至 {{ lv.new_end_time }}
                <template v-if="lv.target_seat_code && lv.target_seat_code !== lv.original_seat_code">
                  · 换座 {{ lv.original_seat_code }} → {{ lv.target_seat_code }}
                </template>
                <template v-if="lv.reason"> · {{ lv.reason }}</template>
              </div>
            </div>
            <el-button
              v-if="lv.can_cancel"
              size="small"
              type="danger"
              plain
              :loading="cancellingLeaveId === lv.id"
              @click="cancelLeave(lv)"
            >{{ lv.is_ongoing ? '提前恢复' : '撤销请假' }}</el-button>
          </div>
        </div>
        <div v-else class="sub">暂无请假记录</div>
      </div>
      <template #footer>
        <el-button @click="leaveVisible = false">关闭</el-button>
        <el-button
          v-if="leaveInfo.eligible && leaveInfo.used_count < leaveInfo.limit"
          type="primary"
          :loading="leaveSubmitting"
          :disabled="!canSubmitLeave"
          @click="submitLeave"
        >确认办理请假</el-button>
      </template>
    </el-dialog>

    <div class="pager">
      <el-pagination
        v-model:current-page="page"
        v-model:page-size="pageSize"
        :total="total"
        :page-sizes="[10, 20, 50]"
        :layout="isMobile ? 'prev, pager, next' : 'total, sizes, prev, pager, next'"
        @current-change="load"
        @size-change="onPageSizeChange"
      />
    </div>
  </el-card>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { onWorkingStoreChange, resolveFilterStoreId } from '../utils/workingStore'
import { useIsMobile } from '../composables/useIsMobile'
import http from '../api/http'

const route = useRoute()
const isMobile = useIsMobile()
const showMobileFilters = ref(false)

const billTypeMap: Record<string, string> = {
  hourly: '按小时',
  daily: '天卡',
  weekly: '周卡',
  monthly: '月卡',
  quarterly: '季卡',
  session: '次卡',
  night: '夜读',
  night_monthly: '夜读月卡',
}

const payTypeMap: Record<string, string> = {
  wechat: '微信',
  balance: '余额',
  period_card: '期限卡',
  admin: '前台收款',
}

function billLabel(v: string) {
  return billTypeMap[v] || v
}

function payTypeLabel(v: string) {
  return payTypeMap[v] || v || '-'
}

function priceText(row: any) {
  if (row.pay_type === 'admin') {
    return Number(row.final_price) === 0 ? '前台免单' : `¥${row.final_price ?? 0}`
  }
  if (row.pay_type === 'period_card' || (Number(row.final_price) === 0 && row.pay_status === 1)) {
    return row.card_name ? `期限卡 · ${row.card_name}` : '期限卡抵扣'
  }
  return `¥${row.final_price ?? 0}`
}

function statusLabel(status: number) {
  return ['已预约', '使用中', '已完成', '已取消'][status] || String(status)
}

function statusTagType(status: number) {
  if (status === 1) return 'success'
  if (status === 2) return 'info'
  if (status === 3) return 'info'
  return 'warning'
}

function formatTime(v: string | null | undefined) {
  if (!v) return '-'
  return String(v).replace('T', ' ').slice(0, 16)
}

const list = ref<any[]>([])
const loading = ref(false)
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)
const viewportH = ref(typeof window !== 'undefined' ? window.innerHeight : 900)
const tableMaxHeight = computed(() => Math.max(320, viewportH.value - 310))

function onResize() {
  viewportH.value = window.innerHeight
}

const refundLabels: Record<string, string> = {
  pending: '退款待确认',
  wechat_confirmed: '微信已确认退款',
  manual: '人工登记退款',
  recorded: '已退款（来源未核实）',
}
const filters = reactive<{ keyword: string; seat_code: string; user_id: number | null; store_id: number | null; pay_status: number | 'refund_pending' | null; status: number | null }>({
  keyword: '',
  seat_code: '',
  user_id: null,
  store_id: null,
  pay_status: null,
  status: null,
})
const stores = ref<any[]>([])

const createBillTypes = [
  { value: 'hourly', label: '按小时' },
  { value: 'daily', label: '天卡' },
  { value: 'weekly', label: '周卡' },
  { value: 'monthly', label: '月卡' },
  { value: 'quarterly', label: '季卡' },
  { value: 'session', label: '次卡' },
  { value: 'night', label: '夜读' },
]

const createVisible = ref(false)
const userSearching = ref(false)
const previewLoading = ref(false)
const createSubmitting = ref(false)
const createPreview = ref<any>(null)
const createForm = reactive({
  keyword: '',
  user: null as any,
  store_id: null as number | null,
  bill_type: 'daily',
  start_time: '',
  end_time: '',
  seat_id: null as number | null,
  final_price: 0,
})

const canSubmitCreate = computed(() => {
  return !!(createForm.user && createForm.store_id && createForm.seat_id && createPreview.value)
})

function resetCreate() {
  createForm.keyword = ''
  createForm.user = null
  createForm.store_id = stores.value[0]?.id || null
  createForm.bill_type = 'daily'
  createForm.start_time = ''
  createForm.end_time = ''
  createForm.seat_id = null
  createForm.final_price = 0
  createPreview.value = null
}

function openCreate() {
  resetCreate()
  createVisible.value = true
}

function clearPreview() {
  createPreview.value = null
  createForm.seat_id = null
}

async function searchUser() {
  const keyword = createForm.keyword.trim()
  if (!keyword) {
    ElMessage.warning('请输入学号或手机号')
    return
  }
  userSearching.value = true
  try {
    const res = await http.get('/admin/users', { params: { keyword, page: 1, page_size: 8 } })
    const items = res.data?.items || []
    if (!items.length) {
      createForm.user = null
      ElMessage.warning('没有找到已注册用户')
      return
    }
    createForm.user = items[0]
    if (items.length > 1) {
      ElMessage.success(`已选中 ${createForm.user.nickname || createForm.user.id}，共 ${items.length} 条匹配，默认取第一条`)
    }
  } finally {
    userSearching.value = false
  }
}

async function previewCreate() {
  if (!createForm.store_id || !createForm.start_time) {
    ElMessage.warning('请选择门店和开始时间')
    return
  }
  previewLoading.value = true
  try {
    const res = await http.post('/admin/reservations/preview', {
      store_id: createForm.store_id,
      bill_type: createForm.bill_type,
      start_time: createForm.start_time,
      end_time: createForm.end_time || null,
    })
    createPreview.value = res.data
    createForm.final_price = Number(res.data.original_price || 0)
    const first = (res.data.seats || []).find((s: any) => s.available)
    createForm.seat_id = first ? first.id : null
  } catch (e: any) {
    createPreview.value = null
    ElMessage.error(e?.response?.data?.detail || e?.message || '预览失败')
  } finally {
    previewLoading.value = false
  }
}

async function submitCreate() {
  if (!canSubmitCreate.value) return
  createSubmitting.value = true
  try {
    const res = await http.post('/admin/reservations/create', {
      user_id: createForm.user.id,
      store_id: createForm.store_id,
      bill_type: createForm.bill_type,
      start_time: createForm.start_time,
      end_time: createForm.end_time || null,
      seat_id: createForm.seat_id,
      final_price: createForm.final_price,
    })
    ElMessage.success(res.message || '已预约')
    createVisible.value = false
    load()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || e?.message || '下单失败')
  } finally {
    createSubmitting.value = false
  }
}

let listRequest = 0
async function load() {
  const requestId = ++listRequest
  loading.value = true
  try {
    const params: Record<string, unknown> = { page: page.value, page_size: pageSize.value }
    if (filters.keyword.trim()) params.keyword = filters.keyword.trim()
    if (filters.seat_code.trim()) params.seat_code = filters.seat_code.trim()
    if (filters.user_id) params.user_id = filters.user_id
    if (filters.store_id) params.store_id = filters.store_id
    if (filters.pay_status === 'refund_pending') params.refund_pending = true
    else if (typeof filters.pay_status === 'number') params.pay_status = filters.pay_status
    if (filters.status !== null && filters.status !== undefined) params.status = filters.status
    const res = await http.get('/admin/reservations', { params })
    if (requestId !== listRequest) return
    list.value = res.data.items || []
    total.value = res.data.total || 0
  } catch (e: any) {
    if (requestId !== listRequest) return
    list.value = []
    total.value = 0
    ElMessage.error(e?.response?.data?.detail || e?.message || '加载订单失败')
  } finally {
    if (requestId === listRequest) loading.value = false
  }
}

function search() {
  page.value = 1
  load()
}

function onPageSizeChange() {
  page.value = 1
  load()
}

function reset() {
  filters.keyword = ''
  filters.seat_code = ''
  filters.user_id = null
  filters.store_id = resolveFilterStoreId()
  filters.pay_status = null
  filters.status = null
  search()
}

function filterUnpaid() {
  filters.pay_status = 0
  filters.status = 0
  search()
}

function canRemoteUnlock(row: any) {
  return row.pay_status === 1 && (row.status === 0 || row.status === 1)
}

function canManageLeave(row: any) {
  return !!(row.leave_eligible || (row.leave_limit > 0 && row.leave_used > 0))
}

const leaveVisible = ref(false)
const leaveLoading = ref(false)
const leavePreviewLoading = ref(false)
const leaveSubmitting = ref(false)
const cancellingLeaveId = ref<number | null>(null)
const leaveRow = ref<any>(null)
const leavePreview = ref<any>(null)
const leaveInfo = reactive<{
  eligible: boolean
  used_count: number
  limit: number
  start_time: string
  end_time: string
  leaves: any[]
}>({
  eligible: false,
  used_count: 0,
  limit: 3,
  start_time: '',
  end_time: '',
  leaves: [],
})
const leaveForm = reactive<{
  start_date: string
  end_date: string
  target_seat_id: number | null
  reason: string
}>({
  start_date: '',
  end_date: '',
  target_seat_id: null,
  reason: '',
})

const canSubmitLeave = computed(() => {
  if (!leavePreview.value) return false
  if (leavePreview.value.original_seat_available) return true
  return !!leaveForm.target_seat_id
})

function clearLeavePreview() {
  leavePreview.value = null
  leaveForm.target_seat_id = null
}

function resetLeave() {
  leaveRow.value = null
  leavePreview.value = null
  leaveForm.start_date = ''
  leaveForm.end_date = ''
  leaveForm.target_seat_id = null
  leaveForm.reason = ''
  leaveInfo.eligible = false
  leaveInfo.used_count = 0
  leaveInfo.limit = 3
  leaveInfo.start_time = ''
  leaveInfo.end_time = ''
  leaveInfo.leaves = []
}

async function refreshLeaveInfo() {
  if (!leaveRow.value) return
  leaveLoading.value = true
  try {
    const res = await http.get(`/admin/reservations/${leaveRow.value.id}/leaves`)
    const d = res.data || {}
    leaveInfo.eligible = !!d.eligible
    leaveInfo.used_count = Number(d.used_count || 0)
    leaveInfo.limit = Number(d.limit || 3)
    leaveInfo.start_time = d.start_time || ''
    leaveInfo.end_time = d.end_time || ''
    leaveInfo.leaves = d.leaves || []
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || e?.message || '加载请假信息失败')
  } finally {
    leaveLoading.value = false
  }
}

async function openLeave(row: any) {
  resetLeave()
  leaveRow.value = row
  leaveVisible.value = true
  await refreshLeaveInfo()
}

async function previewLeave() {
  if (!leaveRow.value) return
  if (!leaveForm.start_date || !leaveForm.end_date) {
    ElMessage.warning('请先选择请假开始日期和结束日期')
    return
  }
  leavePreviewLoading.value = true
  try {
    const res = await http.post(`/admin/reservations/${leaveRow.value.id}/leaves/preview`, {
      start_date: leaveForm.start_date,
      end_date: leaveForm.end_date,
    })
    leavePreview.value = res.data
    leaveForm.target_seat_id = null
  } catch (e: any) {
    leavePreview.value = null
    ElMessage.error(e?.response?.data?.detail || e?.message || '检测失败')
  } finally {
    leavePreviewLoading.value = false
  }
}

async function submitLeave() {
  if (!leaveRow.value || !canSubmitLeave.value) return
  leaveSubmitting.value = true
  try {
    const res = await http.post(`/admin/reservations/${leaveRow.value.id}/leaves`, {
      start_date: leaveForm.start_date,
      end_date: leaveForm.end_date,
      target_seat_id: leavePreview.value?.original_seat_available ? null : leaveForm.target_seat_id,
      reason: leaveForm.reason.trim() || null,
    })
    ElMessage.success(res.message || '月卡请假已办理')
    leaveForm.start_date = ''
    leaveForm.end_date = ''
    leaveForm.reason = ''
    clearLeavePreview()
    await refreshLeaveInfo()
    await load()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || e?.message || '办理请假失败')
  } finally {
    leaveSubmitting.value = false
  }
}

async function cancelLeave(lv: any) {
  if (!leaveRow.value) return
  const title = lv.is_ongoing ? '提前恢复月卡' : '撤销请假'
  const msg = lv.is_ongoing
    ? `确定从今日起提前恢复月卡使用吗？将扣回未休天数的顺延时间（${lv.start_date} 起已休天数保留）。`
    : `确定撤销 ${lv.start_date} 至 ${lv.end_date} 的请假吗？将扣回顺延的 ${lv.days} 天并退回 1 次请假额度。`
  try {
    await ElMessageBox.confirm(msg, title, { type: 'warning', confirmButtonText: '确定', cancelButtonText: '取消' })
  } catch {
    return
  }
  cancellingLeaveId.value = lv.id
  try {
    const res = await http.post(`/admin/reservations/${leaveRow.value.id}/leaves/${lv.id}/cancel`)
    ElMessage.success(res.message || '已处理')
    await refreshLeaveInfo()
    await load()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || e?.message || '操作失败')
  } finally {
    cancellingLeaveId.value = null
  }
}

const unlockingIds = ref(new Set<number>())
async function remoteUnlock(row: any) {
  if (!canRemoteUnlock(row) || unlockingIds.value.has(row.id)) return
  try {
    await ElMessageBox.confirm(
      `确定为「${reservationStoreName(row)}」订单 ${row.order_no}（${row.user_nickname || '同学'} · 座位 ${row.seat_code || '-'}）执行远程开门吗？`,
      '远程开门',
      { type: 'warning', confirmButtonText: '确认开门', cancelButtonText: '取消' },
    )
  } catch {
    return
  }
  unlockingIds.value.add(row.id)
  try {
    const res = await http.post(`/admin/reservations/${row.id}/remote-unlock`)
    ElMessage.success(res.message || '远程开门成功')
    await load()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || e?.message || '远程开门失败')
  } finally {
    unlockingIds.value.delete(row.id)
  }
}

function canCancel(row: any) {
  if (row.status === 3 || row.status === 2) return false
  if (row.status === 1) return false
  return row.status === 0
}

const retryingRefunds = ref(new Set<number>())
async function retryRefund(row: any) {
  if (row.refund_state !== 'pending' || retryingRefunds.value.has(row.id)) return
  const storeId = filters.store_id
  try {
    await ElMessageBox.confirm(`重试订单 ${row.order_no} 的微信退款？`, '重试退款', { type: 'warning' })
  } catch {
    return
  }
  if (storeId !== filters.store_id || retryingRefunds.value.has(row.id)) return
  retryingRefunds.value.add(row.id)
  try {
    await http.post(`/admin/reservations/${row.id}/cancel`)
    ElMessage.success('退款已确认')
    await load()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || e?.message || '退款待确认，请稍后重试')
  } finally {
    retryingRefunds.value.delete(row.id)
  }
}

async function cancelOrder(row: any) {
  const msg = row.pay_status === 0
    ? `确定取消未支付订单 ${row.order_no} 吗？座位将立即释放。`
    : row.pay_type === 'admin'
      ? `确定取消订单 ${row.order_no} 吗？前台收款不退款，仅释放座位。`
      : `确定取消订单 ${row.order_no} 吗？已付款将尝试退款。`
  const storeId = filters.store_id
  await ElMessageBox.confirm(`「${reservationStoreName(row)}」${msg}`, '取消订单', { type: 'warning' })
  if (storeId !== filters.store_id) return
  await http.post(`/admin/reservations/${row.id}/cancel`)
  ElMessage.success('已取消')
  load()
}

async function forceCheckout(row: any) {
  await ElMessageBox.confirm(`确定强制结束订单 ${row.order_no} 吗？`, '强制离座', { type: 'warning' })
  const res = await http.post(`/admin/reservations/${row.id}/force-checkout`)
  ElMessage.success(res.message || '已离座')
  load()
}

const changeSeatVisible = ref(false)
const changeSeatRow = ref<any>(null)
const changeSeatTargetId = ref<number | null>(null)
const changeSeatSubmitting = ref(false)
const seatOptionsLoading = ref(false)
type SeatOption = {
  id: number
  seat_code: string
  zone_name: string
  pos_x?: number | null
  pos_y?: number | null
  selectable: boolean
  can_swap?: boolean
  reason: string | null
  occupied_by?: { reservation_id: number; user_id: number; nickname: string; end_label: string } | null
}

const seatOptions = reactive<{
  current_seat_code: string | null
  current_seat_id: number | null
  start_time: string
  end_time: string
  hint: string
  seats: SeatOption[]
}>({
  current_seat_code: null,
  current_seat_id: null,
  start_time: '',
  end_time: '',
  hint: '',
  seats: [],
})

const selectedSeat = computed(() => seatOptions.seats.find((s) => s.id === changeSeatTargetId.value) || null)
const mappedSeats = computed(() => seatOptions.seats.filter((s) => s.pos_x != null && s.pos_y != null))

function mapSeatStyle(seat: { pos_x?: number | null; pos_y?: number | null }) {
  const x = Number(seat.pos_x) || 0
  const y = Number(seat.pos_y) || 0
  const left = x <= 100 ? x : x / 9
  const top = y <= 100 ? y : y / 7
  return { left: `${left}%`, top: `${top}%` }
}

function seatClass(s: SeatOption) {
  return {
    current: s.id === seatOptions.current_seat_id,
    free: s.selectable,
    swap: !!s.can_swap,
    busy: !s.selectable && !s.can_swap && s.reason !== '座位已停用' && s.id !== seatOptions.current_seat_id,
    off: s.reason === '座位已停用',
    on: s.id === changeSeatTargetId.value,
  }
}

function seatTitle(s: SeatOption) {
  if (s.id === seatOptions.current_seat_id) return `${s.seat_code} 当前座位`
  if (s.selectable) return `${s.seat_code} 空座`
  return `${s.seat_code} ${s.reason || ''}`
}

function pickSeat(s: SeatOption) {
  if (s.id === seatOptions.current_seat_id) return
  if (s.selectable || s.can_swap) {
    changeSeatTargetId.value = s.id
    return
  }
  ElMessage.warning(s.reason || '该座位不可选')
}

function canChangeSeat(row: any) {
  if (row.pay_status !== 1) return false
  if (row.status !== 0 && row.status !== 1) return false
  if (!row.end_time) return true
  return new Date(row.end_time).getTime() > Date.now()
}

function resetChangeSeat() {
  changeSeatRow.value = null
  changeSeatTargetId.value = null
  seatOptions.current_seat_code = null
  seatOptions.current_seat_id = null
  seatOptions.start_time = ''
  seatOptions.end_time = ''
  seatOptions.hint = ''
  seatOptions.seats = []
}

async function openChangeSeat(row: any) {
  changeSeatRow.value = row
  changeSeatTargetId.value = null
  changeSeatVisible.value = true
  seatOptionsLoading.value = true
  try {
    const res = await http.get(`/admin/reservations/${row.id}/seat-options`)
    if (!changeSeatVisible.value || changeSeatRow.value !== row) return
    seatOptions.current_seat_code = res.data.current_seat_code
    seatOptions.current_seat_id = res.data.current_seat_id
    seatOptions.start_time = res.data.start_time
    seatOptions.end_time = res.data.end_time
    seatOptions.hint = res.data.hint || ''
    seatOptions.seats = res.data.seats || []
  } catch (e: any) {
    if (!changeSeatVisible.value || changeSeatRow.value !== row) return
    ElMessage.error(e?.response?.data?.detail || '加载座位失败')
    changeSeatVisible.value = false
  } finally {
    if (changeSeatRow.value === row) seatOptionsLoading.value = false
  }
}

async function submitChangeSeat() {
  if (!changeSeatRow.value || !changeSeatTargetId.value) return
  const row = changeSeatRow.value
  const seatId = changeSeatTargetId.value
  const target = selectedSeat.value
  const occupiedBy = target?.occupied_by
  const swapping = !!(target?.can_swap && occupiedBy)
  const tip = swapping
    ? `确定将 ${changeSeatRow.value.seat_code} 与 ${target.seat_code}（${occupiedBy?.nickname} ID ${occupiedBy?.user_id}，${occupiedBy?.end_label}）对调吗？两人只换座位，订单还在各自名下。对方若是月卡，整段都会换到当前座位。`
    : `确定将订单 ${changeSeatRow.value.order_no} 从 ${changeSeatRow.value.seat_code} 换到 ${target?.seat_code || changeSeatTargetId.value} 吗？`
  await ElMessageBox.confirm(tip, swapping ? '确认对调' : '确认换座', { type: 'warning' })
  if (!changeSeatVisible.value || changeSeatRow.value !== row) return
  changeSeatSubmitting.value = true
  try {
    const res = swapping && occupiedBy
      ? await http.post(`/admin/reservations/${row.id}/swap-seats`, {
          other_reservation_id: occupiedBy.reservation_id,
        })
      : await http.post(`/admin/reservations/${row.id}/change-seat`, {
          seat_id: seatId,
        })
    ElMessage.success(res.message || '换座成功')
    changeSeatVisible.value = false
    load()
  } finally {
    changeSeatSubmitting.value = false
  }
}

const refundVisible = ref(false)
const refundRow = ref<any>(null)
const refundRemark = ref('')
const refundSubmitting = ref(false)

function reservationStoreName(row: any) {
  return row.store_name || stores.value.find((store) => store.id === row.store_id)?.name || `门店 #${row.store_id}`
}

function openRefund(row: any) {
  refundRow.value = row
  refundRemark.value = ''
  refundVisible.value = true
}

async function submitRefund() {
  if (!refundRow.value || !refundRemark.value.trim()) {
    ElMessage.warning('请填写退款备注')
    return
  }
  refundSubmitting.value = true
  try {
    await http.post(`/admin/reservations/${refundRow.value.id}/mark-refund`, {
      remark: refundRemark.value.trim(),
    })
    ElMessage.success('已登记退款')
    refundVisible.value = false
    load()
  } finally {
    refundSubmitting.value = false
  }
}

let offWorkingStore: (() => void) | undefined

function reloadForStore() {
  list.value = []
  total.value = 0
  refundVisible.value = false
  changeSeatVisible.value = false
  changeSeatRow.value = null
  createVisible.value = false
  page.value = 1
  void load()
}

function applyRouteQuery() {
  const q = route.query
  const kw = q.keyword ?? q.order_no
  if (typeof kw === 'string' && kw.trim()) {
    filters.keyword = kw.trim()
  } else if (kw === '') {
    filters.keyword = ''
  }
  if (q.pay_status !== undefined) {
    const ps = Array.isArray(q.pay_status) ? q.pay_status[0] : q.pay_status
    if (ps === 'refund_pending') {
      filters.pay_status = 'refund_pending'
    } else if (ps !== null && ps !== '' && !Number.isNaN(Number(ps))) {
      filters.pay_status = Number(ps)
    } else {
      filters.pay_status = null
    }
  }
  if (q.status !== undefined) {
    const st = Array.isArray(q.status) ? q.status[0] : q.status
    if (st !== null && st !== '' && !Number.isNaN(Number(st))) {
      filters.status = Number(st)
    } else {
      filters.status = null
    }
  }
}

watch(
  () => route.query,
  () => {
    applyRouteQuery()
    page.value = 1
    void load()
  },
)

onMounted(async () => {
  window.addEventListener('resize', onResize)
  const res = await http.get('/admin/stores')
  stores.value = res.data || []
  filters.store_id = resolveFilterStoreId()
  applyRouteQuery()
  offWorkingStore = onWorkingStoreChange((sid) => {
    filters.store_id = sid
    reloadForStore()
  })
  load()
})

onUnmounted(() => {
  window.removeEventListener('resize', onResize)
  offWorkingStore?.()
})
</script>

<style scoped>
.page-card :deep(.el-card__body) { padding-top: 12px; }
.header-row { display: flex; justify-content: space-between; align-items: center; }
.filters { margin-bottom: 4px; }
.filters :deep(.el-form-item) { margin-bottom: 8px; margin-right: 12px; }
.tip { margin-bottom: 10px; }
.order-table { width: 100%; }
.cell-main { line-height: 1.3; }
.sub { font-size: 12px; color: #999; line-height: 1.3; }
.change-seat-meta { line-height: 1.8; }
.seat-legend { display: flex; flex-wrap: wrap; gap: 8px 14px; margin: 10px 0 8px; font-size: 12px; color: #666; }
.m-seat-badge {
  display: inline-block;
  margin-left: 6px;
  padding: 1px 6px;
  border-radius: 6px;
  background: rgba(255, 208, 0, 0.22);
  color: #7a5a00;
  font-size: 12px;
  font-weight: 700;
}
.m-seat-input {
  width: 78px;
  flex: none !important;
}
.seat-legend .dot {
  display: inline-block; width: 10px; height: 10px; border-radius: 3px; margin-right: 4px; vertical-align: -1px;
}
.seat-legend .dot.current { background: #2D6A4F; }
.seat-legend .dot.free { background: #409eff; }
.seat-legend .dot.swap { background: #e6a23c; }
.seat-legend .dot.busy { background: #f56c6c; }
.seat-legend .dot.off { background: #c0c4cc; }
.floor-map {
  position: relative;
  width: 100%;
  aspect-ratio: 900 / 700;
  background: #fafafa;
  border: 1px dashed #ddd;
  border-radius: 8px;
  overflow: hidden;
}
.map-seat {
  position: absolute;
  width: 36px;
  height: 36px;
  margin-left: -18px;
  margin-top: -18px;
  border-radius: 8px;
  background: #409eff;
  color: #fff;
  font-size: 11px;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 2px 6px rgba(0,0,0,0.12);
  cursor: pointer;
  user-select: none;
}
.map-seat.current { background: #2D6A4F; cursor: default; }
.map-seat.swap { background: #e6a23c; }
.map-seat.busy { background: #f56c6c; cursor: default; }
.map-seat.off { background: #c0c4cc; cursor: default; }
.map-seat.on { outline: 3px solid #1C2B20; outline-offset: 1px; }
.seat-picked { margin-top: 10px; font-size: 13px; color: #2D6A4F; }
.create-user-row { display: flex; gap: 8px; width: 100%; }
.create-user-picked { margin-top: 6px; color: #2D6A4F; font-size: 13px; }
.pager { margin-top: 12px; display: flex; justify-content: flex-end; }
.leave-meta {
  padding: 10px 12px;
  border-radius: 10px;
  background: #f8fafc;
  border: 1px solid #eceef2;
  margin-bottom: 14px;
  line-height: 1.7;
}
.leave-section-title {
  font-size: 13px;
  font-weight: 600;
  color: #16171d;
  margin: 14px 0 10px;
}
.leave-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.leave-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 10px 12px;
  border: 1px solid #eceef2;
  border-radius: 10px;
  background: #fff;
}
.leave-item-main {
  min-width: 0;
  line-height: 1.6;
}
</style>
