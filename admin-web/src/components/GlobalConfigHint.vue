<template>
  <el-alert
    v-if="show"
    type="warning"
    :closable="false"
    show-icon
    title="全站配置：此处修改对所有门店生效。"
    style="margin-bottom: 16px"
  />
</template>

<script setup lang="ts">
import { isHqAdmin } from '../utils/adminAuth'

const show = !isHqAdmin()
</script>
