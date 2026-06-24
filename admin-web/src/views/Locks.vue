<template>

  <el-card>

    <template #header>

      <div class="header">

        <span>蓝牙门锁</span>

        <el-button type="primary" @click="dialogVisible = true">添加门锁</el-button>

      </div>

    </template>



    <el-alert

      v-for="a in alerts"

      :key="a.id"

      :title="a.message"

      type="warning"

      show-icon

      closable

      class="alert-item"

      @close="readAlert(a.id)"

    />



    <el-table :data="list" stripe>

      <el-table-column prop="id" label="ID" width="60" />

      <el-table-column prop="lock_name" label="名称" />

      <el-table-column prop="lock_id" label="锁ID" />

      <el-table-column prop="mac_address" label="MAC" />

      <el-table-column prop="battery_level" label="电量" width="100">

        <template #default="{ row }">

          <el-tag :type="batteryType(row.battery_level)">

            {{ row.battery_level ?? '-' }}%

          </el-tag>

        </template>

      </el-table-column>

      <el-table-column prop="status" label="状态" width="80">

        <template #default="{ row }">

          <el-tag :type="row.status === 1 ? 'success' : 'danger'">

            {{ row.status === 1 ? '正常' : '停用' }}

          </el-tag>

        </template>

      </el-table-column>

      <el-table-column label="操作" width="120">

        <template #default="{ row }">

          <el-button link type="primary" @click="refreshBattery(row.id)">刷新电量</el-button>

        </template>

      </el-table-column>

    </el-table>



    <el-dialog v-model="dialogVisible" title="添加门锁" width="480px">

      <el-form :model="form" label-width="80px">

        <el-form-item label="门店ID"><el-input v-model.number="form.store_id" /></el-form-item>

        <el-form-item label="名称"><el-input v-model="form.lock_name" /></el-form-item>

        <el-form-item label="锁ID"><el-input v-model="form.lock_id" /></el-form-item>

        <el-form-item label="MAC"><el-input v-model="form.mac_address" /></el-form-item>

        <el-form-item label="lockData"><el-input v-model="form.lock_data" type="textarea" /></el-form-item>

      </el-form>

      <template #footer>

        <el-button @click="dialogVisible = false">取消</el-button>

        <el-button type="primary" @click="createLock">确定</el-button>

      </template>

    </el-dialog>

  </el-card>

</template>



<script setup lang="ts">

import { onMounted, reactive, ref } from 'vue'

import { ElMessage } from 'element-plus'

import http from '../api/http'



const list = ref<any[]>([])

const alerts = ref<any[]>([])

const dialogVisible = ref(false)

const form = reactive({

  store_id: 1,

  lock_name: '',

  lock_id: '',

  mac_address: '',

  lock_data: '',

})



function batteryType(level: number | null) {

  if (level == null) return 'info'

  if (level < 20) return 'danger'

  if (level < 40) return 'warning'

  return 'success'

}



async function load() {

  const [locksRes, alertsRes] = await Promise.all([

    http.get('/admin/locks'),

    http.get('/admin/locks/alerts'),

  ])

  list.value = locksRes.data

  alerts.value = alertsRes.data

}



async function readAlert(id: number) {

  await http.post(`/admin/locks/alerts/${id}/read`)

  load()

}



async function createLock() {

  await http.post('/admin/locks', form)

  ElMessage.success('添加成功')

  dialogVisible.value = false

  load()

}



async function refreshBattery(id: number) {

  const res = await http.post(`/admin/locks/${id}/refresh-battery`)

  ElMessage.success(`电量: ${res.data.battery_level}%`)

  load()

}



onMounted(load)

</script>



<style scoped>

.header { display: flex; justify-content: space-between; align-items: center; }

.alert-item { margin-bottom: 12px; }

</style>


