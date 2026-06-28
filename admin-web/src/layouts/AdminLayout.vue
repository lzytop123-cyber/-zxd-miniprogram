<template>
  <el-container class="layout">
    <el-aside width="220px" class="aside">
      <div class="logo">知行岛后台</div>
      <el-menu :default-active="route.path" router background-color="#1a1a1a" text-color="#fff" active-text-color="#FFD000">
        <el-menu-item index="/dashboard">数据总览</el-menu-item>

        <el-sub-menu index="home">
          <template #title>首页 · 运营</template>
          <el-menu-item index="/banners">首页活动</el-menu-item>
          <el-menu-item index="/announcements">消息公告</el-menu-item>
          <el-menu-item index="/stores">门店管理</el-menu-item>
          <el-menu-item index="/store-calendar">营业日历</el-menu-item>
        </el-sub-menu>

        <el-sub-menu index="booking">
          <template #title>订座 · 入座</template>
          <el-menu-item index="/pricing">价格管理</el-menu-item>
          <el-menu-item index="/seats">座位管理</el-menu-item>
          <el-menu-item index="/reservations">预约订单</el-menu-item>
          <el-menu-item index="/locks">蓝牙锁管理</el-menu-item>
        </el-sub-menu>

        <el-sub-menu index="packages">
          <template #title>套餐 · 卡券</template>
          <el-menu-item index="/card-purchase-orders">套餐购买</el-menu-item>
          <el-menu-item index="/period-cards">期限卡</el-menu-item>
          <el-menu-item index="/deal-mappings">团购映射</el-menu-item>
          <el-menu-item index="/exchange-records">兑换记录</el-menu-item>
          <el-menu-item index="/coupons">优惠券</el-menu-item>
        </el-sub-menu>

        <el-sub-menu index="users">
          <template #title>用户 · 资产</template>
          <el-menu-item index="/users">用户管理</el-menu-item>
          <el-menu-item index="/wallet-logs">钱包流水</el-menu-item>
          <el-menu-item index="/point-logs">积分流水</el-menu-item>
          <el-menu-item index="/invites">邀请记录</el-menu-item>
        </el-sub-menu>

        <el-sub-menu index="study">
          <template #title>学习助手</template>
          <el-menu-item index="/study-data">学习数据</el-menu-item>
          <el-menu-item index="/knowledge">AI 知识库</el-menu-item>
        </el-sub-menu>

        <el-sub-menu index="system">
          <template #title>系统</template>
          <el-menu-item index="/system-status">系统状态</el-menu-item>
          <el-menu-item index="/operation-logs">操作日志</el-menu-item>
          <el-menu-item index="/admins">管理员</el-menu-item>
        </el-sub-menu>
      </el-menu>
    </el-aside>
    <el-container>
      <el-header class="header">
        <span>自习室运营管理系统</span>
        <el-button type="danger" link @click="logout">退出</el-button>
      </el-header>
      <el-main><router-view /></el-main>
    </el-container>
  </el-container>
</template>

<script setup lang="ts">
import { useRoute, useRouter } from 'vue-router'

const route = useRoute()
const router = useRouter()

function logout() {
  localStorage.removeItem('admin_token')
  router.push('/login')
}
</script>

<style scoped>
.layout { min-height: 100vh; }
.aside { background: #1a1a1a; }
.logo { color: #FFD000; font-size: 18px; font-weight: bold; padding: 20px; text-align: center; }
.header { display: flex; justify-content: space-between; align-items: center; background: #fff; border-bottom: 1px solid #eee; }
:deep(.el-sub-menu__title) { color: #ccc !important; }
</style>
