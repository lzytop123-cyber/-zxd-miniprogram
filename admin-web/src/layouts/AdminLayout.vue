<template>
  <el-container class="layout">
    <el-aside width="220px" class="aside">
      <div class="logo">知行岛后台</div>
      <el-menu :default-active="route.path" router background-color="#1a1a1a" text-color="#fff" active-text-color="#FFD000">
        <el-menu-item index="/dashboard">数据总览</el-menu-item>
        <el-menu-item index="/reservations">订单管理</el-menu-item>
        <el-menu-item index="/locks">蓝牙锁管理</el-menu-item>
        <el-menu-item index="/deal-mappings">团购映射</el-menu-item>
        <el-menu-item index="/coupons">优惠券</el-menu-item>
        <el-menu-item index="/seats">座位管理</el-menu-item>
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
</style>
